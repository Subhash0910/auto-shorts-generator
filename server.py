from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
import os
import threading
import json
from datetime import datetime

from trending_content import get_content
from app import ShortsGenerator, cleanup_video_files
from youtube_shorts_uploader import YouTubeShortsUploader

app = Flask(__name__, static_folder='frontend/dist', static_url_path='')
CORS(app)

API_KEY = os.environ.get("GROQ_API_KEY", "")
JOBS = {}  # job_id -> status dict


def _run_pipeline_job(job_id, content_type="skeleton", auto_upload=False):
    """Background thread: generate content → video → (upload)"""
    try:
        JOBS[job_id]["status"] = "generating_script"
        content = get_content(API_KEY, content_type=content_type)
        JOBS[job_id]["content"] = content
        JOBS[job_id]["status"] = "rendering_video"

        generator = ShortsGenerator()
        output_path = f"output_{job_id}.mp4"
        final_path = generator.generate_video(content, output_path=output_path)

        if not final_path:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = "Video generation failed"
            return

        JOBS[job_id]["video_path"] = final_path
        JOBS[job_id]["status"] = "done"

        if auto_upload:
            JOBS[job_id]["status"] = "uploading"
            uploader = YouTubeShortsUploader(
                client_secrets_file='client-secret.json',
                target_channel_id=os.environ.get("YOUTUBE_CHANNEL_ID", ""),
                api_key=API_KEY
            )
            video_id = uploader.upload_short(final_path, content)
            if video_id:
                JOBS[job_id]["youtube_url"] = f"https://youtube.com/shorts/{video_id}"
                JOBS[job_id]["status"] = "uploaded"
                cleanup_video_files(final_path)
            else:
                JOBS[job_id]["status"] = "upload_failed"

    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)
        print(f"Job {job_id} error: {e}")


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.json or {}
    content_type = data.get("content_type", "skeleton")  # skeleton | trending | challenge
    auto_upload = data.get("auto_upload", False)
    job_id = datetime.now().strftime("%Y%m%d%H%M%S")
    JOBS[job_id] = {"status": "queued", "job_id": job_id, "content_type": content_type}
    thread = threading.Thread(
        target=_run_pipeline_job,
        args=(job_id, content_type, auto_upload),
        daemon=True
    )
    thread.start()
    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/download/<job_id>")
def download(job_id):
    job = JOBS.get(job_id)
    if not job or "video_path" not in job:
        return jsonify({"error": "Video not ready"}), 404
    return send_file(job["video_path"], as_attachment=True, download_name="short.mp4")


@app.route("/api/upload/<job_id>", methods=["POST"])
def upload(job_id):
    job = JOBS.get(job_id)
    if not job or "video_path" not in job:
        return jsonify({"error": "Video not ready"}), 404
    try:
        uploader = YouTubeShortsUploader(
            client_secrets_file='client-secret.json',
            target_channel_id=os.environ.get("YOUTUBE_CHANNEL_ID", ""),
            api_key=API_KEY
        )
        video_id = uploader.upload_short(job["video_path"], job["content"])
        if video_id:
            url = f"https://youtube.com/shorts/{video_id}"
            job["youtube_url"] = url
            job["status"] = "uploaded"
            return jsonify({"success": True, "url": url})
        return jsonify({"success": False, "error": "Upload returned no video_id"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history")
def history():
    log_file = "upload_history.json"
    if os.path.exists(log_file):
        with open(log_file) as f:
            return jsonify(json.load(f))
    return jsonify([])


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "groq_key_set": bool(API_KEY)})


# ─── Frontend Catch-all ───────────────────────────────────────────────────────
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    static = app.static_folder
    if static and path and os.path.exists(os.path.join(static, path)):
        return send_from_directory(static, path)
    if static and os.path.exists(os.path.join(static, 'index.html')):
        return send_from_directory(static, 'index.html')
    return jsonify({"message": "auto-shorts-generator API running"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
