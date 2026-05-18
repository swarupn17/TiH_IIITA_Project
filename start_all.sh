#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

usage() {
  echo "Usage: $0 [CAMERA_URL]"
  echo "If CAMERA_URL is omitted you'll be prompted."
  exit 1
}

FORCE_INSTALL=0
CAM_URL=""
if [ "${1-}" = "--force-install" ] || [ "${1-}" = "-f" ]; then
  FORCE_INSTALL=1
  CAM_URL="${2-}"
else
  CAM_URL="${1-}"
fi

if [ -z "$CAM_URL" ]; then
  read -r -p "Enter camera stream URL (e.g. http://ip:8080/video): " CAM_URL
fi

command -v python3 >/dev/null 2>&1 || { echo "python3 not found. Install Python 3." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm not found. Install Node.js/npm." >&2; exit 1; }

mkdir -p logs

SETUP_MARKER=".start_all_setup_done"

if [ ! -d ".venv" ]; then
  echo "Creating Python virtualenv at .venv..."
  python3 -m venv .venv
fi

VENV_PY="$ROOT_DIR/.venv/bin/python"
VENV_PIP="$ROOT_DIR/.venv/bin/pip"

if [ $FORCE_INSTALL -eq 1 ] || [ ! -f "$SETUP_MARKER" ]; then
  echo "Activating virtualenv and installing dependencies (one-time)..."
  "$VENV_PIP" install --upgrade pip wheel
  if [ -f "MediaPipe/requirements.txt" ]; then
    "$VENV_PIP" install -r MediaPipe/requirements.txt
  fi
  if [ -f "flex/requirements.txt" ]; then
    "$VENV_PIP" install -r flex/requirements.txt
  fi

  echo "Installing frontend dependencies (npm install)..."
  if [ ! -d frontend/node_modules ] || [ $FORCE_INSTALL -eq 1 ]; then
    cd frontend
    npm install
    cd "$ROOT_DIR"
  fi

  touch "$SETUP_MARKER"
  echo "One-time setup complete. Future runs will skip installs unless --force-install is used."
else
  echo "Setup already completed. Skipping dependency installation." 
fi

echo "Starting services. Logs -> ./logs/" 

echo "Starting flex backend..."
"$VENV_PY" flex/main.py > logs/flex.log 2>&1 &
PID_FLEX=$!

echo "Starting MediaPipe backend (using CAMERA_STREAM_URL=$CAM_URL)..."
export CAMERA_STREAM_URL="$CAM_URL"
"$VENV_PY" MediaPipe/app.py > logs/mediapipe.log 2>&1 &
PID_MEDIAPIPE=$!

echo "Starting frontend (npm start)..."
cd frontend
npm start > ../logs/frontend.log 2>&1 &
PID_FRONTEND=$!
cd "$ROOT_DIR"

echo "Started processes:"
echo "  flex PID:      $PID_FLEX"
echo "  mediapipe PID: $PID_MEDIAPIPE"
echo "  frontend PID:  $PID_FRONTEND"
echo "Tail logs with: tail -f logs/frontend.log logs/mediapipe.log logs/flex.log"

trap 'echo "Stopping all..."; kill ${PID_FLEX:-} ${PID_MEDIAPIPE:-} ${PID_FRONTEND:-} 2>/dev/null || true; exit 0' INT TERM

wait ${PID_FLEX:-} ${PID_MEDIAPIPE:-} ${PID_FRONTEND:-}
