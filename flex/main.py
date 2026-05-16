import csv
import json
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import numpy as np
import os
import joblib
from fastapi.middleware.cors import CORSMiddleware
from collections import deque, Counter
import threading

# ==========================================
# CONFIGURATION
# ==========================================
app = FastAPI()

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model", "final_gesture_model.pkl")
DATA_DIR = os.path.join(BASE_DIR, "data")

print("🔎 Loading model from:", MODEL_PATH)
model = joblib.load(MODEL_PATH)
print("✅ Model loaded")


# Map IDs to Names
GESTURE_MAP = {
    0: 'Call', 1: 'Emergency', 2: 'Food', 3: 'Medicine',
    4: 'No', 5: 'Sleep', 6: 'Stop', 7: 'Washroom',
    8: 'Water', 9: 'Yes'
}

# ==========================================
# BUFFERS (SMOOTHING LOGIC)
# ==========================================
# RAW_BUFFER: Averages the last 20 readings (approx 1 sec) to remove electrical noise.
RAW_BUFFER_SIZE = 20
raw_buffer = deque(maxlen=RAW_BUFFER_SIZE)

# PRED_BUFFER: Takes a majority vote of the last 10 predictions to prevent flickering.
PRED_BUFFER_SIZE = 10
pred_buffer = deque(maxlen=PRED_BUFFER_SIZE)

# Store latest raw data for debugging
latest_values = {}
storage_lock = threading.Lock()

# ==========================================
# INPUT SCHEMA
# ==========================================
class SensorInput(BaseModel):
    timestamp: str
    ch0_raw: int
    ch0_volt: float
    ch1_raw: int
    ch1_volt: float
    ch2_raw: int
    ch2_volt: float
    ch3_raw: int
    ch3_volt: float
    ch4_raw: int
    ch4_volt: float
    target: int  # We accept this but ignore it


class SampleStoreInput(BaseModel):
    client_id: str
    label: str


class CombinedSampleInput(BaseModel):
    client_id: str
    capture_time: str | None = None
    flex_prediction: dict | None = None
    flex_values: dict | None = None
    mediapipe_prediction: dict | None = None
    mediapipe_frame: dict | None = None


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

    with storage_lock:
        with open(csv_path, "a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    return csv_path


def _json_cell(value) -> str:
    return json.dumps(value, ensure_ascii=True, default=str)


def _get_prediction_snapshot():
    if len(raw_buffer) < RAW_BUFFER_SIZE:
        return None

    arr = np.array(raw_buffer, dtype=np.float64)
    mean_features = np.mean(arr, axis=0).reshape(1, -1)
    probs = model.predict_proba(mean_features)[0]
    best_class_id = int(np.argmax(probs))
    confidence = float(probs[best_class_id])

    if confidence < 0.40:
        final_gesture = "Unknown"
        status = "low_confidence"
        final_pred_id = -1
    else:
        pred_buffer.append(best_class_id)
        final_pred_id = Counter(pred_buffer).most_common(1)[0][0]
        final_gesture = GESTURE_MAP.get(final_pred_id, "Unknown")
        status = "confident"

    return {
        "gesture": final_gesture,
        "predicted_class": final_pred_id if confidence >= 0.65 else -1,
        "confidence": round(confidence, 2),
        "status": status,
    }

# ==========================================
# ENDPOINTS
# ==========================================
@app.get("/")
def home():
    return {"status": "Gesture Backend Online", "model": "SVM Pipeline"}

@app.get("/latest")
def get_latest():
    """Returns the latest sensor values for the frontend."""
    if not latest_values:
        return {"status": "no_data", "message": "Waiting for sensor data..."}
    return latest_values

@app.post("/ingest")
def ingest_values(data: SensorInput):
    """Receives 10 features from the ESP32/Hardware."""
    global latest_values, raw_buffer
    latest_values = data.dict()

    # Construct vector in EXACT order of training
    # [Raw0, Volt0, ... Raw4, Volt4]
    raw_vector = [
        data.ch0_raw, data.ch0_volt,
        data.ch1_raw, data.ch1_volt,
        data.ch2_raw, data.ch2_volt,
        data.ch3_raw, data.ch3_volt,
        data.ch4_raw, data.ch4_volt
    ]
    
    raw_buffer.append(raw_vector)
    return {"status": "ok"}

@app.get("/predict")
def predict():
    """Returns the stabilized gesture prediction."""
    prediction = _get_prediction_snapshot()
    if prediction is None:
        return {
            "gesture": "Initializing...",
            "confidence": 0.0,
            "status": "buffering"
        }

    return {
        **prediction,
        "latest_values": latest_values,
        "raw_volts_ch0": latest_values.get("ch0_volt", 0)
    }


@app.post("/store_sample")
def store_sample(payload: SampleStoreInput):
    """Stores the latest Flex sample in a per-user CSV file."""
    if not latest_values:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "No sensor data available yet"},
        )

    prediction = _get_prediction_snapshot()
    if prediction is None:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Not enough buffered data to store a sample"},
        )

    row = {
        **latest_values,
        "client_id": payload.client_id,
        "label": payload.label,
        "source": "flex",
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "prediction": prediction["gesture"],
        "predicted_class": prediction["predicted_class"],
        "confidence": prediction["confidence"],
    }

    csv_path = _append_user_csv(payload.client_id, "flex.csv", row)
    return {
        "status": "success",
        "message": "Flex sample stored",
        "path": csv_path,
        "client_id": payload.client_id,
    }


@app.post("/store_record")
def store_record(payload: CombinedSampleInput):
    """Stores one continuous combined record per user."""
    if not latest_values:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "No sensor data available yet"},
        )

    flex_snapshot = payload.flex_prediction or _get_prediction_snapshot() or {}
    row = {
        "client_id": payload.client_id,
        "captured_at": payload.capture_time or datetime.now(timezone.utc).isoformat(),
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "source": "continuous",
        "flex_timestamp": latest_values.get("timestamp"),
        "flex_ch0_raw": latest_values.get("ch0_raw"),
        "flex_ch0_volt": latest_values.get("ch0_volt"),
        "flex_ch1_raw": latest_values.get("ch1_raw"),
        "flex_ch1_volt": latest_values.get("ch1_volt"),
        "flex_ch2_raw": latest_values.get("ch2_raw"),
        "flex_ch2_volt": latest_values.get("ch2_volt"),
        "flex_ch3_raw": latest_values.get("ch3_raw"),
        "flex_ch3_volt": latest_values.get("ch3_volt"),
        "flex_ch4_raw": latest_values.get("ch4_raw"),
        "flex_ch4_volt": latest_values.get("ch4_volt"),
        "flex_prediction": _json_cell(flex_snapshot),
        "flex_values": _json_cell(payload.flex_values or latest_values),
        "mediapipe_prediction": _json_cell(payload.mediapipe_prediction or {}),
        "mediapipe_frame": _json_cell(payload.mediapipe_frame or {}),
    }

    csv_path = _append_user_csv(payload.client_id, "continuous.csv", row)
    return {
        "status": "success",
        "message": "Continuous record stored",
        "path": csv_path,
        "client_id": payload.client_id,
    }

if __name__ == "__main__":
    import uvicorn
    # Run on 0.0.0.0 so other devices on network can see it
    uvicorn.run(app, host="0.0.0.0", port=8000)