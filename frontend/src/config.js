// ============================================
// BACKEND CONFIGURATION
// Auto-updated by start_all.sh — do not edit manually
// Last updated: Tue, Jun 23, 2026  4:57:46 PM
// Laptop IP: 192.168.137.1
// ============================================
const hostname = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';

// Auto-detected laptop IP — updated every time start_all.sh runs
const LAPTOP_IP = '192.168.137.1';

export const FLEX_API_URL = isLocalhost
  ? 'http://localhost:8000'
  : `http://${LAPTOP_IP}:8000`;

export const MEDIAPIPE_WS_URL = isLocalhost
  ? 'http://localhost:5001'
  : `http://${LAPTOP_IP}:5001`;

export const SOCKET_URL = isLocalhost
  ? 'http://localhost:5001'
  : `http://${LAPTOP_IP}:5001`;

export const getFlexEndpoint = (path) => {
  const cleanPath = path.startsWith('/') ? path : '/' + path;
  return `${FLEX_API_URL}${cleanPath}`;
};

console.log('Backend Config:', {
  flex: FLEX_API_URL,
  mediapipe: MEDIAPIPE_WS_URL,
  socket: SOCKET_URL,
  isLocalhost,
  hostname,
  laptopIP: LAPTOP_IP
});
