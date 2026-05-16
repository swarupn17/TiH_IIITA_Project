docker run -p 5001:5001 -e STREAM_URL=http://host.docker.internal:8080/video mediapipe-backend



Camera Run command:

cd MediaPipe
source .venv/bin/activate
CAMERA_STREAM_URL=http://10.60.126.38:8080/video python app.py

### CSV storage

MediaPipe data is included in the combined continuous CSV flow driven from the frontend.
The combined per-user file is written under `flex/data/<client_id>/continuous.csv`.