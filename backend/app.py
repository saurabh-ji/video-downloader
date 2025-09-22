from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from downloader import download_video
import os

app = Flask(__name__)
CORS(app)  # ✅ Allow frontend to call backend

@app.route("/download", methods=["POST"])
def download():
    data = request.json
    url = data.get("url")

    if not url:
        return jsonify({"error": "URL required"}), 400

    try:
        filepath, title = download_video(url)
        return send_file(filepath, as_attachment=True, download_name=f"{title}.mp4")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return "✅ Video Downloader Backend Running on Port 8000 🚀"

if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    app.run(host="0.0.0.0", port=8000)

