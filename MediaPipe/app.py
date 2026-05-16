import eventlet
eventlet.monkey_patch()  # MUST be first

from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import cv2
import base64
import csv
import json
import threading
from datetime import datetime, timezone
import pickle
import numpy as np
import mediapipe as mp
import os

# --- MEDIAPIPE IMPORTS ---
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# --- CONFIGURATION ---
WEBCAM_INDEX = 0
PKL_MODEL_PATH = "gesture_classifier_rf.pkl"
TASK_MODEL_PATH = "hand_landmarker.task"
# ---------------------
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Global video capture - initialized later
cap = None
cap_lock = threading.Lock()
current_stream_url = os.environ.get('CAMERA_STREAM_URL', 'http://localhost:8080/video')

# Camera rotation settings: 0, 90, 180, 270 degrees
camera_rotation = int(os.environ.get('CAMERA_ROTATION', '0'))
camera_flip_horizontal = os.environ.get('CAMERA_FLIP_H', 'true').lower() == 'true'
camera_flip_vertical = os.environ.get('CAMERA_FLIP_V', 'false').lower() == 'true'

def init_camera(url):
    """Initialize or reinitialize camera with new URL"""
    global cap, current_stream_url
    with cap_lock:
        if cap is not None:
            cap.release()
        print(f"Connecting to stream: {url}")
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            print(f"ERROR: Could not open video stream at {url}")
            return False
        current_stream_url = url
        print("Stream connected.")
        return True

# Try initial connection (won't exit if fails)
print(f"Attempting initial connection to: {current_stream_url}")
if not init_camera(current_stream_url):
    print("WARNING: Initial stream connection failed. Use /set_camera API or Web UI to set correct URL.")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
CORS(app)  # Enable CORS for all routes
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- 1. LOAD YOUR NEW MODELS ---

# Load the Scikit-learn classifier
print(f"Loading classifier from {PKL_MODEL_PATH}...")
if not os.path.exists(PKL_MODEL_PATH):
    print(f"!!!!!!!! FATAL ERROR: Classifier file not found: {PKL_MODEL_PATH}")
    exit()
with open(PKL_MODEL_PATH, 'rb') as f:
    pkl_model = pickle.load(f)
print("Classifier loaded successfully.")

# Load the MediaPipe Hand Landmarker
print(f"Loading MediaPipe model from {TASK_MODEL_PATH}...")
if not os.path.exists(TASK_MODEL_PATH):
    print(f"!!!!!!!! FATAL ERROR: MediaPipe model not found: {TASK_MODEL_PATH}")
    exit()

BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=TASK_MODEL_PATH),
    running_mode=VisionRunningMode.IMAGE,
    num_hands=1)

landmarker = HandLandmarker.create_from_options(options)
print("MediaPipe Hand Landmarker created successfully.")

# --- 2. HELPER FUNCTIONS ---

CLASS_NAMES = [
    'call', 'emergency', 'food', 'medicine', 'no', 
    'sleep', 'stop', 'washroom', 'water', 'yes'
]

def normalize_landmarks(hand_landmarks):
    """Converts 21 landmarks into a 63-element normalized feature vector."""
    coords = np.array([(lm.x, lm.y, lm.z) for lm in hand_landmarks[0]])
    relative_coords = coords - coords[0]
    return relative_coords.flatten()

# Hand connections for drawing (define manually since mp.solutions is deprecated)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),  # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),  # Index
    (0, 9), (9, 10), (10, 11), (11, 12),  # Middle
    (0, 13), (13, 14), (14, 15), (15, 16),  # Ring
    (0, 17), (17, 18), (18, 19), (19, 20),  # Pinky
    (5, 9), (9, 13), (13, 17)  # Palm
]

frame_lock = threading.Lock()
latest_data = {"image": None, "predictions": []}
latest_sample = None
sample_lock = threading.Lock()
thread = None

def encode_frame(frame):
    """Convert frame to base64 string for WebSocket transmission."""
    _, buffer = cv2.imencode('.jpg', frame)
    encoded = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded}"


class SampleStoreInput:
    def __init__(self, client_id, label):
        self.client_id = client_id
        self.label = label


def _sanitize_client_id(client_id: str) -> str:
    cleaned = "".join(ch for ch in client_id.strip() if ch.isalnum() or ch in ("-", "_"))
    return cleaned or "unknown"


def _append_user_csv(client_id: str, filename: str, row: dict) -> str:
    user_id = _sanitize_client_id(client_id)
    user_dir = os.path.join(DATA_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)

    csv_path = os.path.join(user_dir, filename)
    file_exists = os.path.exists(csv_path)
    fieldnames = list(row.keys())

    with sample_lock:
        with open(csv_path, "a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    return csv_path

def video_processing_thread():
    """Background thread to process video frames."""
    global latest_data, latest_sample, cap
    print("Starting video processing thread...")
    
    while True:
        try:
            with cap_lock:
                if cap is None or not cap.isOpened():
                    socketio.sleep(1)
                    continue
                ret, frame = cap.read()
            
            if not ret:
                print("--- Error reading frame. Waiting... ---")
                socketio.sleep(2)
                continue
            
            # Apply rotation based on settings
            if camera_rotation == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif camera_rotation == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif camera_rotation == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            # Apply flips
            if camera_flip_horizontal:
                frame = cv2.flip(frame, 1)
            if camera_flip_vertical:
                frame = cv2.flip(frame, 0)
            
            annotated_frame = frame.copy()
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            
            results = landmarker.detect(mp_image)
            predictions = []

            if results.hand_landmarks:
                hand_landmarks_list = results.hand_landmarks
                
                normalized_data = normalize_landmarks(hand_landmarks_list)
                data_to_predict = normalized_data.reshape(1, -1)
                
                pred_index = pkl_model.predict(data_to_predict)[0]
                label = CLASS_NAMES[pred_index]
                confidence = pkl_model.predict_proba(data_to_predict).max()
                
                h, w, _ = frame.shape
                all_x = [lm.x * w for lm in hand_landmarks_list[0]]
                all_y = [lm.y * h for lm in hand_landmarks_list[0]]
                
                x1 = int(min(all_x)) - 15
                y1 = int(min(all_y)) - 15
                x2 = int(max(all_x)) + 15
                y2 = int(max(all_y)) + 15

                h, w, _ = annotated_frame.shape
                landmark_points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks_list[0]]
                
                # Draw connections
                for connection in HAND_CONNECTIONS:
                    start_idx, end_idx = connection
                    start_point = landmark_points[start_idx]
                    end_point = landmark_points[end_idx]
                    cv2.line(annotated_frame, start_point, end_point, (0, 255, 0), 2)
                
                # Draw landmarks
                for point in landmark_points:
                    cv2.circle(annotated_frame, point, 5, (255, 0, 0), -1)
                
                predictions.append({
                    "label": label,
                    "confidence": round(float(confidence), 2),
                    "bbox": [x1, y1, x2, y2]
                })

                with sample_lock:
                    latest_sample = {
                        "source": "mediapipe",
                        "stored_at": datetime.now(timezone.utc).isoformat(),
                        "prediction": label,
                        "confidence": round(float(confidence), 4),
                        "bbox": [x1, y1, x2, y2],
                        "features": normalized_data.tolist(),
                    }
            else:
                with sample_lock:
                    latest_sample = None

            encoded_frame = encode_frame(annotated_frame)
            data_packet = {"image": encoded_frame, "predictions": predictions}
            
            with frame_lock:
                latest_data = data_packet

            socketio.emit('new_frame', data_packet)
            socketio.sleep(0.03)

        except Exception as e:
            print(f"!!!!!!!! ERROR IN VIDEO THREAD: {e} !!!!!!!!")
            socketio.sleep(2)


# ============================================
# API ENDPOINTS FOR DYNAMIC CAMERA CONFIG
# ============================================

@app.route('/set_camera', methods=['POST'])
def set_camera():
    """Change camera URL at runtime"""
    data = request.get_json()
    new_url = data.get('url')
    
    if not new_url:
        return jsonify({"error": "No URL provided"}), 400
    
    success = init_camera(new_url)
    if success:
        return jsonify({"status": "success", "url": new_url})
    else:
        return jsonify({"error": "Failed to connect to stream"}), 500

@app.route('/camera_status', methods=['GET'])
def camera_status():
    """Check current camera connection status"""
    with cap_lock:
        is_open = cap is not None and cap.isOpened()
    return jsonify({
        "connected": is_open,
        "current_url": current_stream_url,
        "rotation": camera_rotation,
        "flip_horizontal": camera_flip_horizontal,
        "flip_vertical": camera_flip_vertical
    })

@app.route('/set_rotation', methods=['POST'])
def set_rotation():
    """Set camera rotation and flip settings"""
    global camera_rotation, camera_flip_horizontal, camera_flip_vertical
    data = request.get_json()
    
    if 'rotation' in data:
        rot = int(data['rotation'])
        if rot in [0, 90, 180, 270]:
            camera_rotation = rot
    
    if 'flip_horizontal' in data:
        camera_flip_horizontal = bool(data['flip_horizontal'])
    
    if 'flip_vertical' in data:
        camera_flip_vertical = bool(data['flip_vertical'])
    
    return jsonify({
        "status": "success",
        "rotation": camera_rotation,
        "flip_horizontal": camera_flip_horizontal,
        "flip_vertical": camera_flip_vertical
    })

@app.route('/reconnect', methods=['POST'])
def reconnect():
    """Reconnect to the current camera URL"""
    success = init_camera(current_stream_url)
    return jsonify({"status": "success" if success else "failed"})


@app.route('/')
def index():
    """Web UI with camera URL input"""
    return render_template_string("""
    <html>
    <head>
        <title>MediaPipe Gesture Stream</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; background: #1a1a2e; color: #eee; }
            h1 { color: #00d9ff; }
            .control-panel {
                background: #16213e; padding: 20px; border-radius: 10px; margin-bottom: 20px;
            }
            input[type="text"] {
                width: 350px; padding: 10px; font-size: 14px; border: none; border-radius: 5px;
            }
            button {
                padding: 10px 20px; margin-left: 10px; cursor: pointer; border: none;
                border-radius: 5px; font-weight: bold;
            }
            .btn-primary { background: #00d9ff; color: #000; }
            .btn-secondary { background: #ffc107; color: #000; }
            .btn-success { background: #28a745; color: #fff; }
            #status {
                margin-top: 15px; padding: 10px; border-radius: 5px;
                background: #0f3460; display: inline-block;
            }
            .connected { color: #28a745; }
            .disconnected { color: #dc3545; }
            #video { border: 3px solid #00d9ff; border-radius: 10px; }
            #detections {
                background: #16213e; padding: 15px; border-radius: 10px;
                min-height: 50px; font-family: monospace;
            }
        </style>
    </head>
    <body>
        <h1>🤖 MediaPipe Gesture Recognition</h1>
        
        <div class="control-panel">
            <h3>📷 Camera Configuration</h3>
            <input type="text" id="cameraUrl" placeholder="http://RASPBERRY_PI_IP:8080/video">
            <button class="btn-primary" onclick="setCamera()">Set Camera URL</button>
            <button class="btn-secondary" onclick="checkStatus()">Check Status</button>
            <button class="btn-success" onclick="reconnect()">Reconnect</button>
            <div id="status">Status: <span id="statusText">Unknown</span></div>
        </div>
        
        <img id="video" src="" style="width: 640px; height: 480px;">
        
        <h3>🎯 Detections:</h3>
        <pre id="detections">Waiting for hand gestures...</pre>
        
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.js"></script>
        <script>
            const socket = io();
            
            socket.on('connect', () => {
                console.log('Connected to server!');
                checkStatus();
            });
            
            socket.on('new_frame', (data) => {
                document.getElementById('video').src = data.image;
                if (data.predictions.length > 0) {
                    document.getElementById('detections').textContent = JSON.stringify(data.predictions, null, 2);
                } else {
                    document.getElementById('detections').textContent = 'No hand detected';
                }
            });
            
            socket.on('disconnect', () => console.log('Disconnected from server.'));
            
            async function setCamera() {
                const url = document.getElementById('cameraUrl').value;
                if (!url) {
                    alert('Please enter a camera URL');
                    return;
                }
                
                document.getElementById('statusText').textContent = 'Connecting...';
                
                try {
                    const res = await fetch('/set_camera', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({url: url})
                    });
                    const data = await res.json();
                    
                    if (data.status === 'success') {
                        document.getElementById('statusText').innerHTML = '<span class="connected">✅ Connected to: ' + url + '</span>';
                    } else {
                        document.getElementById('statusText').innerHTML = '<span class="disconnected">❌ Failed: ' + data.error + '</span>';
                    }
                } catch (e) {
                    document.getElementById('statusText').innerHTML = '<span class="disconnected">❌ Error: ' + e.message + '</span>';
                }
            }
            
            async function checkStatus() {
                try {
                    const res = await fetch('/camera_status');
                    const data = await res.json();
                    
                    if (data.connected) {
                        document.getElementById('statusText').innerHTML = '<span class="connected">✅ Connected to: ' + data.current_url + '</span>';
                        document.getElementById('cameraUrl').value = data.current_url;
                    } else {
                        document.getElementById('statusText').innerHTML = '<span class="disconnected">❌ Disconnected</span>';
                    }
                } catch (e) {
                    document.getElementById('statusText').innerHTML = '<span class="disconnected">❌ Error</span>';
                }
            }
            
            async function reconnect() {
                document.getElementById('statusText').textContent = 'Reconnecting...';
                try {
                    const res = await fetch('/reconnect', { method: 'POST' });
                    const data = await res.json();
                    checkStatus();
                } catch (e) {
                    document.getElementById('statusText').innerHTML = '<span class="disconnected">❌ Reconnect failed</span>';
                }
            }
            
            // Check status on page load
            checkStatus();
        </script>
    </body>
    </html>
    """)


@app.route('/store_sample', methods=['POST'])
def store_sample():
    """Store the latest MediaPipe sample in a per-user CSV file."""
    data = request.get_json() or {}
    client_id = data.get('client_id', '').strip()
    label = data.get('label', '').strip()

    if not client_id:
        return jsonify({"status": "error", "message": "client_id is required"}), 400

    if not label:
        return jsonify({"status": "error", "message": "label is required"}), 400

    with sample_lock:
        sample = dict(latest_sample) if latest_sample else None

    if not sample:
        return jsonify({"status": "error", "message": "No MediaPipe sample available yet"}), 400

    row = {
        "client_id": client_id,
        "label": label,
        "source": sample.get("source", "mediapipe"),
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "prediction": sample.get("prediction"),
        "confidence": sample.get("confidence"),
        "bbox": json.dumps(sample.get("bbox")),
        "features_json": json.dumps(sample.get("features")),
    }

    csv_path = _append_user_csv(client_id, "mediapipe.csv", row)
    return jsonify({
        "status": "success",
        "message": "MediaPipe sample stored",
        "path": csv_path,
        "client_id": client_id,
    })


@socketio.on('connect')
def handle_connect(auth=None):
    global thread
    print("Client connected")
    
    if thread is None:
        print("Starting background video thread.")
        thread = socketio.start_background_task(target=video_processing_thread)
    
    with frame_lock:
        if latest_data["image"]:
            emit('new_frame', latest_data)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    port_to_use = 5001 
    print(f"Starting Flask-SocketIO server on http://0.0.0.0:{port_to_use}")
    socketio.run(app, host='0.0.0.0', port=port_to_use, debug=False)