# Emotion Service

A Flask microservice that detects facial emotions from webcam frames and returns an emoji. Used as an optional companion to the Secure Messenger web UI.

## How It Works

The web UI captures a webcam frame every second and POSTs it here as a base64-encoded JPEG. This service decodes the image, runs facial emotion analysis via [DeepFace](https://github.com/serengil/deepface), and returns the dominant emotion and its corresponding emoji.

## Setup

```bash
cd emotion-service
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
```

> **Note:** DeepFace will download its model weights (~500 MB) on the first run. This is expected.

## Running

```bash
python app.py
```

Service runs at `http://localhost:5001`.

## Endpoints

### `GET /health`
Returns `{ "status": "ok" }` — use this to confirm the service is up.

### `POST /analyze`
Analyzes a webcam frame and returns the detected emotion.

**Request body:**
```json
{ "image": "<base64-encoded JPEG>" }
```

**Response:**
```json
{ "emotion": "happy", "emoji": "😄", "confidence": 87.3 }
```

The emoji is chosen based on confidence (0–100): low confidence returns a subtle emoji, high confidence returns a more expressive one.

**Supported emotions:**

| Emotion   | Low → High intensity                |
|-----------|-------------------------------------|
| happy     | 🙂 😊 😄 😁 🤩                      |
| sad       | 🙁 😢 😭 💔 😿                      |
| angry     | 😤 😠 😡 🤬 💢                      |
| surprise  | 😮 😲 🤯 😱 🫠                      |
| fear      | 😟 😨 😰 😱 🫣                      |
| neutral   | 😶 😑 🫤 😏 🪨                      |
| disgust   | 😕 🤢 🤮 😖 🤧                      |
| contempt  | 🙄 😒 😏 😤 🫠                      |

## Dependencies

| Package         | Purpose                        |
|-----------------|--------------------------------|
| Flask           | HTTP server                    |
| flask-cors      | Allow requests from the web UI |
| deepface        | Facial emotion analysis        |
| opencv-python   | Image decoding                 |
| numpy           | Array handling                 |
| tf-keras        | DeepFace backend               |
