# Gesture Recognition Project

This project combines two inputs for gesture recognition:

- A camera stream for hand gestures
- Flex sensor readings for sensor-based gesture input

The project is designed to run on the same network. That means your laptop, Raspberry Pi, and Android phone should all be connected to the same Wi-Fi.

## What You Need

- A laptop or PC
- A Raspberry Pi or another device that can stream the camera
- A device that sends flex sensor readings
- Android phone only if you want to use the mobile app

## Project Parts

- `MediaPipe/` - camera gesture detection backend
- `flex/` - flex sensor backend
- `frontend/` - web app used to view and control the system
- `android-app/` - optional Android app
- `raspi-camera/` - helper scripts for camera streaming on Raspberry Pi

## Important Rule

Make sure every device is on the same Wi-Fi network before you start.

## Simple Setup Steps

### 1. Start the camera stream on Raspberry Pi

If your Raspberry Pi setup uses a folder named `pycam`, go into that folder first. If you are using the files in this repository, use the `raspi-camera/` folder instead.

Run:

```bash
cd pycam
python script.py
```

After this starts, note the camera URL it prints. You will need that URL for the next step.

Example camera URL:

```bash
http://192.168.1.50:8080/video
```

### 2. Start the flex sensor stream on the Raspberry Pi or sensor device

If your setup uses a folder named `flex_monitoring`, open it first. If you are using this repository, the flex code is in the `flex/` folder or in your own flex streaming script.

Run:

```bash
cd flex_monitoring
source venv/bin/activate
python data_stream.py
```

Important:

- Edit `data_stream.py` so it contains the IP address of the FastAPI server.
- This step sends flex readings to the server.

### 3. Start the FastAPI / main project server from the root folder

Go back to the root of the project and run:

```bash
cd TiH_IIITA_Project-main
./start_all.sh CAMERA_URL
```

Replace `CAMERA_URL` with the camera URL you got from the Raspberry Pi.

Example:

```bash
./start_all.sh http://192.168.1.50:8080/video
```

This starts all required services for the project.

The first run may take a little longer because it prepares the environment. Later runs will start faster.

### 4. Open the frontend

After the server starts, open the frontend in your browser.

The frontend is used to:

- set the camera URL
- enter the client id
- start recording
- stop recording
- save the CSV file

### 5. Use the app

Follow this order:

1. Enter the camera URL
2. Enter the client id
3. Start recording
4. Stop recording when done
5. Save CSV

The CSV file for each client is saved in:

```bash
flex/data/<client_id>/continuous.csv
```

## Output Data

Each client gets their own CSV file. It contains the captured gesture data for that client.

## Android App

If you want to use the Android app:

1. Build the app in Android Studio
2. Install it on your phone
3. Connect the phone to the same Wi-Fi network
4. Enter the server URL in the app

The Android app is useful if you want to access the web app from a phone.

## Quick Example Flow

1. Turn on the Raspberry Pi camera stream
2. Turn on the flex sensor stream
3. Run `./start_all.sh CAMERA_URL` from the root folder
4. Open the frontend
5. Enter client id
6. Start recording
7. Stop recording
8. Save CSV

## Troubleshooting

- If the camera does not connect, check that the camera URL is correct.
- If the frontend cannot reach the backends, make sure all devices are on the same Wi-Fi.
- If CSV is not saved, check the `flex/data/` folder for the client folder.
- If you changed the camera or server IP, update the URL in the frontend and restart the services.


## License

MIT License