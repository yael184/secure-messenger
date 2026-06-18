from flask import Flask, request, jsonify
from flask_cors import CORS
from deepface import DeepFace
import base64
import numpy as np
import cv2

app = Flask(__name__)
CORS(app)

# Each emotion maps to [low, medium, high] intensity emojis.
# The emoji is chosen based on the confidence score (0–100).
EMOJI_MAP = {
    'happy':    ['🙂', '😊', '😄', '😁', '🤩'],
    'sad':      ['😔', '😢', '😭', '💔', '😿'],
    'angry':    ['😤', '😠', '😡', '🤬', '💢'],
    'surprise': ['😮', '😲', '🤯', '😱', '🙀'],
    'fear':     ['😟', '😨', '😰', '😱', '🫣'],
    'neutral':  ['😶', '😐', '🫤', '😑', '🪨'],
    'disgust':  ['😕', '🤢', '🤮', '😖', '🤧'],
    'contempt': ['🙄', '😒', '😏', '😤', '🫠'],
}


def pick_emoji(emotion: str, confidence: float) -> str:
    options = EMOJI_MAP.get(emotion, ['😐'])
    # confidence is 0–100; map it to an index across the options list
    idx = min(int(confidence / 100 * len(options)), len(options) - 1)
    return options[idx]


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({'error': 'Missing image field'}), 400

        img_bytes = base64.b64decode(data['image'])
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            return jsonify({'error': 'Could not decode image'}), 400

        result = DeepFace.analyze(img, actions=['emotion'], enforce_detection=False)
        emotion = result[0]['dominant_emotion']
        confidence = result[0]['emotion'].get(emotion, 0)
        emoji = pick_emoji(emotion, confidence)

        return jsonify({'emotion': emotion, 'emoji': emoji, 'confidence':  float(round(confidence, 1))})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # DeepFace downloads models (~500MB) on first run — this is expected
    print('Starting Emotion Service on http://localhost:5001')
    app.run(port=5001, debug=True)
