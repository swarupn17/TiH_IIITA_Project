#!/usr/bin/env bash
# =============================================================
#  TiH IIITA Gesture Recognition — Unified Startup Script
#
#  Raspberry Pi IP : 10.20.205.38 (default)
#  Camera stream   : http://10.20.205.38:8080/video
#  Flex sensor     : http://10.20.205.38:8080a
#
#  Usage:
#    ./start_all.sh                                    # auto-detects laptop IP
#    ./start_all.sh http://192.168.137.38:8080/video   # override Pi camera URL
#    ./start_all.sh --force-install                    # reinstall all deps
#    ./start_all.sh --help
# =============================================================
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
header()  { echo -e "\n${BOLD}${CYAN}━━━  $*  ━━━${RESET}"; }

# ── Default Raspberry Pi addresses ───────────────────────────
DEFAULT_PI_IP="10.20.205.38"
DEFAULT_PI_PORT="8080"
DEFAULT_CAM_URL="http://${DEFAULT_PI_IP}:${DEFAULT_PI_PORT}/video"

# ── Parse arguments ──────────────────────────────────────────
FORCE_INSTALL=0
CAM_URL=""

for arg in "$@"; do
  case "$arg" in
    --force-install|-f) FORCE_INSTALL=1 ;;
    --help|-h)    
      echo -e "${BOLD}Usage:${RESET} $0 [OPTIONS] [CAMERA_URL]"
      echo ""
      echo "  CAMERA_URL           Override Pi camera URL (default: $DEFAULT_CAM_URL)"
      echo "  --force-install, -f  Re-install all Python & npm dependencies"
      echo "  --help,          -h  Show this help"
      echo ""
      echo -e "${BOLD}Services started:${RESET}"
      echo "  • flex      FastAPI flex-sensor backend  → http://localhost:8000"
      echo "  • mediapipe Flask-SocketIO hand-gesture  → http://localhost:5001"
      echo "  • frontend  React web app                → http://localhost:3000"
      exit 0
      ;;
    http://*|https://*) CAM_URL="$arg" ;;
    *) warn "Unknown argument: $arg (ignored)" ;;
  esac
done

# ── Banner ────────────────────────────────────────────────────
echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   TiH IIITA — Gesture Recognition System    ║"
echo "  ║   Flex  •  MediaPipe  •  React Frontend     ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Root dir ─────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# ── Resolve camera URL ───────────────────────────────────────
if [ -z "$CAM_URL" ]; then
  CAM_URL="$DEFAULT_CAM_URL"
  info "Using default camera URL: ${CYAN}$CAM_URL${RESET}"
fi
PI_BASE_URL="$(echo "$CAM_URL" | sed 's|/video||')"
success "Camera stream : $CAM_URL"
success "Flex Pi base  : $PI_BASE_URL"

# ── Auto-detect laptop IP ─────────────────────────────────────
header "Detecting Laptop IP"

LAPTOP_IP=""
PI_NETWORK=""

LAPTOP_IP=""
PI_HOST=$(echo "$CAM_URL" | sed 's|http://||' | sed 's|:.*||' | sed 's|/.*||')
info "Getting Pi IP via SSH..."
PI_IP=$(ssh -i ~/.ssh/pi_key -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes "bdalab@${PI_HOST}" "hostname -I 2>/dev/null | awk '{print \$1}'" 2>/dev/null | tr -d '\r\n' || echo "")
if [ -n "$PI_IP" ]; then
  PI_NETWORK=$(echo "$PI_IP" | cut -d'.' -f1-3)
  info "Pi IP: ${CYAN}${PI_IP}${RESET} Network: ${CYAN}${PI_NETWORK}.x${RESET}"
  if command -v ipconfig.exe >/dev/null 2>&1; then
    LAPTOP_IP=$(ipconfig.exe 2>/dev/null | grep "IPv4" | grep "${PI_NETWORK}\." | awk '{print $NF}' | tr -d '\r' | head -1)
  fi
fi
if [ -z "$LAPTOP_IP" ]; then
  if command -v ipconfig.exe >/dev/null 2>&1; then
    LAPTOP_IP=$(ipconfig.exe 2>/dev/null | grep "IPv4" | grep -v "127.0.0.1" | awk '{print $NF}' | tr -d '\r' | head -1)
  else
    LAPTOP_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
  fi
fi
if [ -z "$LAPTOP_IP" ]; then
  LAPTOP_IP="localhost"
  warn "Could not detect laptop IP"
else
  success "Laptop IP detected: ${CYAN}$LAPTOP_IP${RESET}"
fi

# ── Update frontend config.js with current laptop IP ─────────
header "Updating Frontend Config"

CONFIG_FILE="$ROOT_DIR/frontend/src/config.js"

cat > "$CONFIG_FILE" << CONFIGEOF
// ============================================
// BACKEND CONFIGURATION
// Auto-updated by start_all.sh — do not edit manually
// Last updated: $(date)
// Laptop IP: ${LAPTOP_IP}
// ============================================
const hostname = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';

// Auto-detected laptop IP — updated every time start_all.sh runs
const LAPTOP_IP = '${LAPTOP_IP}';

export const FLEX_API_URL = isLocalhost
  ? 'http://localhost:8000'
  : \`http://\${LAPTOP_IP}:8000\`;

export const MEDIAPIPE_WS_URL = isLocalhost
  ? 'http://localhost:5001'
  : \`http://\${LAPTOP_IP}:5001\`;

export const SOCKET_URL = isLocalhost
  ? 'http://localhost:5001'
  : \`http://\${LAPTOP_IP}:5001\`;

export const getFlexEndpoint = (path) => {
  const cleanPath = path.startsWith('/') ? path : '/' + path;
  return \`\${FLEX_API_URL}\${cleanPath}\`;
};

console.log('Backend Config:', {
  flex: FLEX_API_URL,
  mediapipe: MEDIAPIPE_WS_URL,
  socket: SOCKET_URL,
  isLocalhost,
  hostname,
  laptopIP: LAPTOP_IP
});
CONFIGEOF

success "config.js updated with laptop IP: $LAPTOP_IP"

# ── Detect OS & set correct paths ────────────────────────────
header "Checking System"

if command -v python3 >/dev/null 2>&1 && python3 --version 2>&1 | grep -q "Python 3"; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1 && python --version 2>&1 | grep -q "Python 3"; then
  PYTHON_CMD="python"
else
  error "Python 3 not found! Install from https://www.python.org/downloads/"
  exit 1
fi
success "Python: $PYTHON_CMD ($($PYTHON_CMD --version 2>&1))"

if ! command -v npm >/dev/null 2>&1; then
  error "npm not found! Install Node.js from https://nodejs.org"
  exit 1
fi
success "npm: $(npm --version)"

# ── Directory setup ──────────────────────────────────────────
mkdir -p logs
mkdir -p flex/data

# ── Python virtualenv ────────────────────────────────────────
header "Python Virtual Environment"

if [ ! -d ".venv" ]; then
  info "Creating virtualenv ..."
  "$PYTHON_CMD" -m venv .venv
  success "Virtualenv created"
else
  success "Virtualenv exists"
fi

# Windows = Scripts/, Linux/Mac = bin/
if [ -f "$ROOT_DIR/.venv/Scripts/python.exe" ] || [ -f "$ROOT_DIR/.venv/Scripts/python" ]; then
  VENV_PY="$ROOT_DIR/.venv/Scripts/python"
  VENV_PIP="$ROOT_DIR/.venv/Scripts/pip"
else
  VENV_PY="$ROOT_DIR/.venv/bin/python"
  VENV_PIP="$ROOT_DIR/.venv/bin/pip"
fi

# ── One-time dependency install ───────────────────────────────
SETUP_MARKER=".start_all_setup_done"

if [ $FORCE_INSTALL -eq 1 ] || [ ! -f "$SETUP_MARKER" ]; then
  header "Installing Dependencies"

  info "Upgrading pip ..."
  "$VENV_PIP" install --upgrade pip wheel --quiet

  if [ -f "MediaPipe/requirements.txt" ]; then
    info "Installing MediaPipe requirements ..."
    "$VENV_PIP" install -r MediaPipe/requirements.txt --quiet
    success "MediaPipe deps installed"
  fi

  if [ -f "flex/requirements.txt" ]; then
    info "Installing flex requirements ..."
    "$VENV_PIP" install -r flex/requirements.txt --quiet
    success "Flex deps installed"
  fi

  if [ ! -d "frontend/node_modules" ] || [ $FORCE_INSTALL -eq 1 ]; then
    info "Installing frontend npm packages ..."
    cd frontend && npm install --silent && cd "$ROOT_DIR"
    success "Frontend npm packages installed"
  else
    success "Frontend node_modules already present"
  fi

  touch "$SETUP_MARKER"
  success "Setup complete!"
else
  success "Dependencies already installed. Use --force-install to redo."
fi

# ── Start services ────────────────────────────────────────────
header "Starting All Services"

# 1. Flex — FastAPI on port 8000
info "Starting flex backend (FastAPI) → http://localhost:8000 ..."
cd "$ROOT_DIR"
"$VENV_PY" flex/main.py > logs/flex.log 2>&1 &
PID_FLEX=$!
success "flex started (PID $PID_FLEX)"

# ── Wait for FastAPI then start Raspberry Pi services ─────────
info "Waiting for FastAPI backend to be ready ..."
for i in $(seq 1 20); do
  if curl -sf http://localhost:8000/latest >/dev/null 2>&1; then
    success "FastAPI is ready"
    break
  fi
  sleep 1
done

header "Starting Raspberry Pi Services"

ssh -i ~/.ssh/pi_key -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
  "bdalab@${PI_HOST}" \
  "nohup /home/bdalab/start_pi.sh > /home/bdalab/pi_startup.log 2>&1 < /dev/null &" \
  || warn "Could not auto-start Pi services. Run /home/bdalab/start_pi.sh manually."

success "Pi services start command sent"

header "Starting UNO Pulse Pipeline"

ssh -f -i ~/.ssh/pi_key -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
  "bdalab@${PI_HOST}" \
  "DISPLAY=:0 XAUTHORITY=/home/bdalab/.Xauthority /home/bdalab/launch_pulse_gui.sh >/home/bdalab/pulse_pipeline.log 2>&1"

success "UNO Pulse Pipeline start command sent"

# 2. MediaPipe — Flask-SocketIO on port 5001
info "Starting MediaPipe backend (Flask) → http://localhost:5001 ..."
cd "$ROOT_DIR/MediaPipe"
export CAMERA_STREAM_URL="$CAM_URL"
export FLEX_STREAM_URL="$PI_BASE_URL"
"$VENV_PY" app.py > "$ROOT_DIR/logs/mediapipe.log" 2>&1 &
PID_MEDIAPIPE=$!
cd "$ROOT_DIR"
success "mediapipe started (PID $PID_MEDIAPIPE)"

# 3. React frontend — port 3000
info "Starting React frontend → http://localhost:3000 ..."
cd "$ROOT_DIR/frontend"
npm start > "$ROOT_DIR/logs/frontend.log" 2>&1 &
PID_FRONTEND=$!
cd "$ROOT_DIR"
success "frontend started (PID $PID_FRONTEND)"

# ── Wait for frontend then auto-open browser ─────────────────
echo ""
info "Waiting for frontend to be ready (~15s) ..."
for i in $(seq 1 40); do
  if curl -sf http://localhost:3000 >/dev/null 2>&1; then
    success "Frontend is up!"
    if command -v cmd.exe >/dev/null 2>&1; then
      cmd.exe /c start http://localhost:3000 >/dev/null 2>&1 &
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "http://localhost:3000" >/dev/null 2>&1 &
    elif command -v open >/dev/null 2>&1; then
      open "http://localhost:3000" >/dev/null 2>&1 &
    fi
    break
  fi
  sleep 1
done

# ── Summary ───────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════╗"
echo -e "║        ✅  All services are running!            ║"
echo -e "╚══════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${CYAN}flex backend${RESET}       http://localhost:8000"
echo -e "  ${CYAN}mediapipe backend${RESET}  http://localhost:5001"
echo -e "  ${CYAN}frontend (laptop)${RESET}  http://localhost:3000"
echo -e "  ${CYAN}frontend (phone)${RESET}   ${YELLOW}http://${LAPTOP_IP}:3000${RESET}  ← phone mein yeh kholo"
echo ""
echo -e "  ${BOLD}Raspberry Pi:${RESET}"
echo -e "  Camera : ${YELLOW}$CAM_URL${RESET}"
echo -e "  Flex   : ${YELLOW}$PI_BASE_URL${RESET}"
echo ""
echo -e "  ${BOLD}Logs:${RESET}  tail -f logs/flex.log logs/mediapipe.log logs/frontend.log"
echo -e "  ${BOLD}Stop:${RESET}  Press ${RED}Ctrl + C${RESET}"
echo ""

echo "$PID_FLEX $PID_MEDIAPIPE $PID_FRONTEND" > .running_pids

cleanup() {
  echo ""
  warn "Shutting down all services ..."

  # Laptop services
  kill "$PID_FLEX"      2>/dev/null || true
  kill "$PID_MEDIAPIPE" 2>/dev/null || true
  kill "$PID_FRONTEND"  2>/dev/null || true

  echo "Stopping Raspberry Pi + UNO pipeline..."

  ssh -i ~/.ssh/pi_key \
      -o ConnectTimeout=3 \
      -o StrictHostKeyChecking=no \
      "bdalab@${PI_HOST}" \
      "
      /home/bdalab/stop_pulse_pipeline.sh 2>/dev/null || true;

      pkill -f serial_to_kafka.py 2>/dev/null || true;
      pkill -f pulse_data-1.0-SNAPSHOT.jar 2>/dev/null || true;
      pkill -f kafka.Kafka 2>/dev/null || true;
      pkill -f QuorumPeerMain 2>/dev/null || true;

      pkill -f data_stream.py 2>/dev/null || true;
      pkill -f script.py 2>/dev/null || true;
      " \
      2>/dev/null || true

  rm -f .running_pids

  success "All stopped. Goodbye!"
  exit 0
}
trap cleanup INT TERM

wait "$PID_FLEX" "$PID_MEDIAPIPE" "$PID_FRONTEND"