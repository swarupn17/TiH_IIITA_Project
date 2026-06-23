#!/usr/bin/env python3
"""
Optimized Low-Latency Camera Streaming for Gesture Recognition
Designed for MediaPipe hand detection with minimal delay.

Run on Raspberry Pi:
    python3 stream_camera.py

MediaPipe URL:
    http://PI_IP:8080/video
"""

import io
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import struct

# ============================================
# CONFIGURATION - Tune for your setup
# ============================================
PORT = 8080
WIDTH = 640          # Good balance for hand detection
HEIGHT = 480
FRAMERATE = 30       # Target FPS
JPEG_QUALITY = 70      # Lower = faster, 60-80 is good for gestures
BUFFER_COUNT = 2     # Minimal buffering (2-4)
SKIP_FRAMES = False  # Skip frames if client is slow

# ============================================

# Try picamera2 first (Raspberry Pi)
try:
    from picamera2 import Picamera2
    import libcamera
    USE_PICAMERA2 = True
except ImportError:
    USE_PICAMERA2 = False
    import cv2


class FrameBuffer:
    """Ultra-low latency frame buffer - always serves latest frame"""
    def __init__(self):
        self.frame = None
        self.lock = threading.Lock()
        self.new_frame = threading.Event()
        self.frame_count = 0
        self.start_time = time.time()
    
    def update(self, frame_data):
        with self.lock:
            self.frame = frame_data
            self.frame_count += 1
        self.new_frame.set()
    
    def get(self, timeout=1.0):
        """Get latest frame, skip old ones"""
        if self.new_frame.wait(timeout):
            self.new_frame.clear()
            with self.lock:
                return self.frame
        return None
    
    def get_fps(self):
        elapsed = time.time() - self.start_time
        return self.frame_count / elapsed if elapsed > 0 else 0


frame_buffer = FrameBuffer()


class StreamHandler(BaseHTTPRequestHandler):
    """Optimized HTTP handler for MJPEG streaming"""
    
    protocol_version = 'HTTP/1.1'
    
    def do_GET(self):
        if self.path in ['/', '/index.html']:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            fps = frame_buffer.get_fps()
            self.wfile.write(f'''
                <html>
                <head><title>Pi Gesture Camera</title></head>
                <body style="background:#1a1a2e;color:#fff;font-family:Arial;text-align:center;padding:20px;">
                <h1>🤖 Gesture Recognition Camera</h1>
                <p>FPS: {fps:.1f} | Resolution: {WIDTH}x{HEIGHT}</p>
                <img src="/video" style="border:3px solid #00d9ff;border-radius:10px;max-width:100%;">
                <p style="margin-top:20px;">
                    <b>Stream URL:</b> <code>http://YOUR_PI_IP:{PORT}/video</code>
                </p>
                </body></html>
            '''.encode())
            
        elif self.path in ['/video', '/stream', '/?action=stream']:
            self.send_response(200)
            self.send_header('Age', '0')
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            try:
                while True:
                    frame = frame_buffer.get(timeout=2.0)
                    if frame is None:
                        continue
                    
                    # Send frame with minimal overhead
                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                    self.wfile.write(f'Content-Length: {len(frame)}\r\n\r\n'.encode())
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
                    
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                print(f'Stream error: {e}')
                
        elif self.path == '/status':
            # Status endpoint for health checks
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            fps = frame_buffer.get_fps()
            self.wfile.write(f'{{"fps":{fps:.1f},"width":{WIDTH},"height":{HEIGHT}}}'.encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Disable logging for speed


class ThreadedServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 10


def start_picamera2():
    """Optimized Picamera2 capture for low latency"""
    import numpy as np
    
    picam2 = Picamera2()
    
    # Configure for low latency
    config = picam2.create_video_configuration(
        main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
        buffer_count=BUFFER_COUNT,
        controls={
            "FrameRate": FRAMERATE,
            "ExposureTime": 20000,  # Fixed exposure for consistency
            "AnalogueGain": 2.0,
        },
        queue=False  # Don't queue frames - always get latest
    )
    
    # Disable processing for speed
    config["transform"] = libcamera.Transform(hflip=0, vflip=0)
    
    picam2.configure(config)
    picam2.start()
    
    print(f"📷 Picamera2 started: {WIDTH}x{HEIGHT} @ {FRAMERATE}fps")
    
    # Pre-allocate buffer
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    
    while True:
        try:
            # Capture with minimal delay
            frame = picam2.capture_array("main")
            
            # Fast JPEG encode
            _, jpeg = cv2.imencode('.jpg', frame, encode_param)
            frame_buffer.update(jpeg.tobytes())
            
        except Exception as e:
            print(f"Capture error: {e}")
            time.sleep(0.1)


def start_opencv():
    """OpenCV capture (fallback/testing)"""
    cap = cv2.VideoCapture(0)
    
    # Optimize camera settings
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FRAMERATE)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    
    # Disable auto settings for consistency
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # Manual
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)      # Fixed focus
    
    print(f"📷 OpenCV camera started: {WIDTH}x{HEIGHT} @ {FRAMERATE}fps")
    
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    
    while True:
        ret, frame = cap.read()
        if ret:
            # Optional: flip for mirror effect (better for gesture feedback)
            frame = cv2.flip(frame, 1)
            
            _, jpeg = cv2.imencode('.jpg', frame, encode_param)
            frame_buffer.update(jpeg.tobytes())


def main():
    print("=" * 50)
    print("🎥 Gesture Recognition Camera Stream")
    print("=" * 50)
    print(f"Resolution: {WIDTH}x{HEIGHT}")
    print(f"Target FPS: {FRAMERATE}")
    print(f"JPEG Quality: {JPEG_QUALITY}%")
    print("=" * 50)
    
    # Start camera capture thread
    if USE_PICAMERA2:
        import cv2  # Need cv2 for encoding even with picamera2
        capture_thread = threading.Thread(target=start_picamera2, daemon=True)
    else:
        capture_thread = threading.Thread(target=start_opencv, daemon=True)
    capture_thread.start()
    
    # Wait for first frame
    time.sleep(1)
    
    # Start HTTP server
    server = ThreadedServer(('0.0.0.0', PORT), StreamHandler)
    
    # Get local IP
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "YOUR_PI_IP"
    
    print(f"\n✅ Stream ready!")
    print(f"   Local:  http://localhost:{PORT}/video")
    print(f"   Network: http://{local_ip}:{PORT}/video")
    print(f"\n📱 Use this URL in MediaPipe camera config")
    print("Press Ctrl+C to stop\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        server.shutdown()


if __name__ == "__main__":
    main()
