# TiH IIITA — Gesture Recognition System

Real-time hand gesture recognition using Raspberry Pi 4, flex sensors, MediaPipe, and a React web dashboard.

---

## 📦 What This Project Does

- **Raspberry Pi** captures hand movements via camera and flex sensors
- **MediaPipe** detects hand landmarks from the camera stream
- **FastAPI** receives flex sensor data from the Pi
- **React Frontend** displays everything in a web dashboard
- **Any device** (laptop, phone, tablet) on the same network can open the dashboard

---

## 🖥️ System Requirements



### Laptop / PC

- Python 3.9 or higher → https://www.python.org/downloads/
- Node.js 16+ and npm → https://nodejs.org/
- Git Bash (Windows) → https://git-scm.com/downloads

### Raspberry Pi 4

- Raspberry Pi OS installed
- Pi Camera Module connected
- Flex sensors connected via MCP3008 ADC

---

## 🆕 Setting Up on a New Laptop (Fresh Start)

Follow these steps in order — only needed once per laptop.

### Step 1 — Install Python

1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or higher
3. Run installer
4. ⚠️ IMPORTANT: Check ✅ **"Add Python to PATH"** before clicking Install
5. Verify:

```bash
python --version
# Should show: Python 3.11.x
```

### Step 2 — Install Node.js

1. Go to https://nodejs.org/
2. Download LTS version
3. Install with default settings
4. Verify:

```bash
node --version
npm --version
```

### Step 3 — Install Git Bash (Windows only)

1. Go to https://git-scm.com/downloads
2. Download and install with default settings
3. Open "Git Bash" from Start Menu for all commands below

### Step 4 — Download the Project

```bash
# Option A — If you have the ZIP file:
# Extract the ZIP to a folder e.g. D:\TiH_Project

# Option B — If using Git:
git clone <repo-url>
cd TiH_IIITA_Project-main
```

### Step 5 — Make script executable

```bash
chmod +x start_all.sh
```

### Step 6 — Open Windows Firewall ports (Windows only)

Open **PowerShell as Administrator** and run:

```powershell
netsh advfirewall firewall add rule name="FastAPI 8000" dir=in action=allow protocol=TCP localport=8000
netsh advfirewall firewall add rule name="MediaPipe 5001" dir=in action=allow protocol=TCP localport=5001
netsh advfirewall firewall add rule name="Frontend 3000" dir=in action=allow protocol=TCP localport=3000
```

> ✅ This is a one-time step. Rules persist after reboot.

### Step 7 — First Run (installs all dependencies automatically)

```bash
./start_all.sh http://<PI_IP>:8080/video
```

First run will automatically install all Python and npm packages.
This takes 5-10 minutes depending on internet speed.

**That's it! The project is set up.** Future runs are instant.

---

## 🟢 How to Run Every Day

### Step 1 — Find Pi's IP address

Connect to Pi via PuTTY and run:

```bash
hostname -I
```

Note the IP — e.g. `192.168.137.38`

### Step 2 — Start everything on Laptop

Open Git Bash in the project folder:

```bash
./start_all.sh http://<PI_IP>:8080/video
```

Example:

```bash
./start_all.sh http://192.168.137.38:8080/video
```

Wait for this message:

```
✅ All services are running!
  flex backend      http://localhost:8000
  mediapipe backend http://localhost:5001
  frontend (web)    http://localhost:3000
  frontend (phone)  http://192.168.x.x:3000  ← open this on phone
```

### Step 3 — Start everything on Pi

In PuTTY:

```bash
/home/bdalab/start_pi.sh
```

### Step 4 — Open the web app

- **Laptop browser:** http://localhost:3000
- **Phone/tablet:** http://\<LAPTOP_IP\>:3000 (shown in terminal above)

### Step 5 — Stop everything

Press `Ctrl + C` in the Git Bash window.
Press `Ctrl + C` in PuTTY.

---

## 🔄 When Network Changes

### What happens when network changes?

- Pi gets a new IP address
- Laptop gets a new IP address
- Both must be on the **same network**

### Checklist for network change:

```
□ 1. Pi is connected to the new network (see below)
□ 2. Laptop is connected to the same network
□ 3. Find Pi's new IP → hostname -I (on Pi)
□ 4. Run on laptop:
       ./start_all.sh http://<NEW_PI_IP>:8080/video
□ 5. Run on Pi:
       /home/bdalab/start_pi.sh
□ 6. Open browser: http://localhost:3000
```

> ✅ No other changes needed — script auto-detects new laptop IP and updates everything automatically.

---

## 📡 Connecting Pi to a New WiFi Network

Pi needs to know the new network's credentials before it can connect.

### Method 1 — Add via PuTTY (Best — do this in advance)

While Pi is connected to current network:

```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
```

Add all networks you'll ever use:

```
country=IN
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="College_WiFi"
    psk="College_Password"
    key_mgmt=WPA-PSK
    priority=3
}

network={
    ssid="Home_WiFi"
    psk="Home_Password"
    key_mgmt=WPA-PSK
    priority=2
}

network={
    ssid="My_Phone_Hotspot"
    psk="Hotspot_Password"
    key_mgmt=WPA-PSK
    priority=1
}
```

Save: `Ctrl+X` → `Y` → Enter

Apply:

```bash
sudo wpa_cli -i wlan0 reconfigure
```

> 💡 Pi will automatically connect to whichever network is available — no changes needed when switching!

### Method 2 — SD Card Edit (When Pi has no network at all)

1. Power off Pi
2. Remove SD card → insert into laptop
3. Open `boot` drive
4. Create file named `wpa_supplicant.conf`:

```
country=IN
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="Your_WiFi_Name"
    psk="Your_WiFi_Password"
    key_mgmt=WPA-PSK
}
```

5. Also create an empty file named `ssh` (no extension) to enable SSH
6. Reinsert SD card → power on Pi
7. Pi connects automatically

### Method 3 — Phone Hotspot (Quick Emergency Option)

1. Turn on phone hotspot
2. Make sure hotspot name/password matches what's in Pi's `wpa_supplicant.conf`
3. Pi auto-connects within 30 seconds
4. Check Pi IP in phone → Settings → Hotspot → Connected devices

---

## 🔍 Finding Pi's IP on a New Network

| Method         | Command / Steps                                   |
| -------------- | ------------------------------------------------- |
| On Pi directly | `hostname -I`                                     |
| From laptop    | `arp -a` (look for Pi's MAC)                      |
| Phone hotspot  | Settings → Hotspot → Connected devices            |
| Router page    | Open `192.168.1.1` in browser → connected devices |

---

## 🔌 Connecting to Pi via PuTTY

1. Open PuTTY
2. **Host Name:** Pi's IP (e.g. `192.168.137.38`)
3. **Port:** `22`
4. **Connection type:** `SSH`
5. Click **Open**
6. Login: `bdalab` / your password

---

## 📋 Quick Command Reference

### Laptop (Git Bash)

```bash
# Run project (replace with current Pi IP)
./start_all.sh http://192.168.137.38:8080/video

# Reinstall all dependencies (if something breaks)
./start_all.sh --force-install http://192.168.137.38:8080/video

# View logs
tail -f logs/flex.log
tail -f logs/mediapipe.log
tail -f logs/frontend.log

# Find laptop IP
ipconfig | findstr "IPv4"        # Windows
hostname -I                       # Linux/Mac
```

### Pi (PuTTY)

```bash
# Start all Pi services
/home/bdalab/start_pi.sh

# Find Pi IP
hostname -I

# Test if laptop FastAPI is reachable from Pi
curl http://<LAPTOP_IP>:8000

# Test if camera is working
curl -I http://localhost:8080/video
```

### Windows Firewall (PowerShell Admin)

```powershell
# Add rules (run once per laptop)
netsh advfirewall firewall add rule name="FastAPI 8000" dir=in action=allow protocol=TCP localport=8000
netsh advfirewall firewall add rule name="MediaPipe 5001" dir=in action=allow protocol=TCP localport=5001
netsh advfirewall firewall add rule name="Frontend 3000" dir=in action=allow protocol=TCP localport=3000
```

---

## 🔧 Troubleshooting

### Problem: MediaPipe not starting (port 5001 connection refused)

```bash
cat logs/mediapipe.log

# Run manually to see full error
cd MediaPipe
CAMERA_STREAM_URL=http://<PI_IP>:8080/video ../.venv/Scripts/python app.py
```

Fix: Make sure Pi camera is running first (`start_pi.sh` on Pi).

### Problem: Flex sensor cannot reach FastAPI (timeout)

```bash
# Test from Pi
curl http://<LAPTOP_IP>:8000
```

Fix: Add Windows Firewall rules (see above).

### Problem: Phone shows "cannot reach backend"

Fix: Re-run `start_all.sh` — it auto-updates `config.js` with correct laptop IP.

### Problem: Camera stream not working

```bash
# Test from laptop
curl -I http://<PI_IP>:8080/video
```

Fix: Run `start_pi.sh` on Pi. Make sure Pi and laptop are on same network.

### Problem: Dependencies not installing (network timeout)

College network blocks package downloads.
Fix: Use mobile hotspot for first-time install only.

### Problem: python3 not found on Windows

Fix: Install Python from https://www.python.org/downloads/
Check ✅ "Add Python to PATH" during install. Then restart Git Bash.

### Problem: venv using wrong Python version

```bash
rm -rf .venv .start_all_setup_done
./start_all.sh --force-install http://<PI_IP>:8080/video
```

---

## 🌐 Port Reference

| Service              | Port | Who uses it               |
| -------------------- | ---- | ------------------------- |
| React Frontend       | 3000 | Laptop browser + Phone    |
| FastAPI (Flex data)  | 8000 | Pi sends data here        |
| MediaPipe (Gestures) | 5001 | Frontend connects here    |
| Pi Camera Stream     | 8080 | MediaPipe reads from here |

---

## 🔑 Default Settings

| Item              | Value                                         |
| ----------------- | --------------------------------------------- |
| Pi SSH username   | `bdalab`                                      |
| Pi SSH port       | `22`                                          |
| Pi startup script | `/home/bdalab/start_pi.sh`                    |
| Pi camera script  | `/home/bdalab/pycam/script.py`                |
| Pi flex script    | `/home/bdalab/flex_monitoring/data_stream.py` |

---

## 👥 Project Info

- **Institute:** IIITA — Indian Institute of Information Technology Allahabad
- **Project:** TiH Gesture Recognition System
- **Hardware:** Raspberry Pi 4, IMX500 Camera, MCP3008 ADC, 5x Flex Sensors
- **Stack:** Python, FastAPI, Flask-SocketIO, MediaPipe, React, Socket.IO
