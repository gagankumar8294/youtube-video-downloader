import sys
import os

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import shutil
import uuid
import glob
import re
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)

# Base directory for downloaded files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Locate ffmpeg
FFMPEG_PATH = None
try:
    import imageio_ffmpeg
    bundled_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if os.path.exists(bundled_ffmpeg):
        FFMPEG_PATH = bundled_ffmpeg
except Exception:
    pass

if not FFMPEG_PATH:
    FFMPEG_PATH = shutil.which("ffmpeg")

print(f"[*] Detected FFmpeg at: {FFMPEG_PATH or 'Not found'}", flush=True)

# In-memory dictionary to store live download progress tasks
download_tasks = {}


def cleanup_old_files():
    """Periodically clean up downloaded files older than 30 minutes to save disk space."""
    while True:
        try:
            now = datetime.now().timestamp()
            for filename in os.listdir(DOWNLOAD_DIR):
                filepath = os.path.join(DOWNLOAD_DIR, filename)
                if os.path.isfile(filepath) and not filename.startswith("."):
                    if now - os.path.getmtime(filepath) > 1800:  # 30 minutes
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass
        except Exception:
            pass
        threading.Event().wait(600)  # Check every 10 minutes


threading.Thread(target=cleanup_old_files, daemon=True).start()


def format_bytes(b):
    if not b:
        return "0 MB"
    b = float(b)
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024.0:
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} TB"


def clean_youtube_url(url):
    """Normalize YouTube URL and remove playlist/tracking bloat to ensure fast lookup."""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    if "watch?v=" in url:
        v_match = re.search(r"v=([a-zA-Z0-9_-]{11})", url)
        if v_match:
            return f"https://www.youtube.com/watch?v={v_match.group(1)}"
    elif "youtu.be/" in url:
        v_match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
        if v_match:
            return f"https://www.youtube.com/watch?v={v_match.group(1)}"
    elif "shorts/" in url:
        v_match = re.search(r"shorts/([a-zA-Z0-9_-]{11})", url)
        if v_match:
            return f"https://www.youtube.com/watch?v={v_match.group(1)}"
    elif "live/" in url:
        v_match = re.search(r"live/([a-zA-Z0-9_-]{11})", url)
        if v_match:
            return f"https://www.youtube.com/watch?v={v_match.group(1)}"

    return url


def format_duration(seconds):
    if not seconds:
        return "Unknown"
    seconds = int(seconds)
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    # Return 204 No Content to prevent console 404 errors
    return ("", 204)


@app.route("/api/info", methods=["POST"])
def get_video_info():
    data = request.get_json(silent=True) or {}
    raw_url = data.get("url", "").strip()

    if not raw_url:
        return jsonify({"error": "Please enter a valid YouTube URL."}), 400

    url = clean_youtube_url(raw_url)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching info for: {url}", flush=True)

    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "restrictfilenames": True,
        "windowsfilenames": True,
    }
    if FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = FFMPEG_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return jsonify({"error": "Could not retrieve video details."}), 404

            formats = info.get("formats", [])

            target_buckets = [
                (2160, "2160p (4K UHD)", 1800),
                (1440, "1440p (2K QHD)", 1200),
                (1080, "1080p (Full HD)", 900),
                (720, "720p (HD)", 600),
                (480, "480p (SD)", 400),
                (360, "360p (SD)", 300),
            ]

            available_res = []
            for res_val, label, min_h in target_buckets:
                has_match = any(
                    (f.get("height") and f.get("height") >= min_h and f.get("vcodec") != "none") or
                    (f.get("format_note") and f"{res_val}p" in str(f.get("format_note")))
                    for f in formats
                )
                if has_match:
                    available_res.append({"value": res_val, "label": label})

            if not available_res:
                available_res = [
                    {"value": 1080, "label": "1080p (Full HD)"},
                    {"value": 720, "label": "720p (HD)"},
                    {"value": 360, "label": "360p (SD)"}
                ]

            video_data = {
                "id": info.get("id"),
                "title": info.get("title", "Untitled Video"),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader", "Unknown Channel"),
                "duration": format_duration(info.get("duration")),
                "views": f"{info.get('view_count', 0):,}" if info.get("view_count") else "N/A",
                "available_resolutions": available_res,
            }
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully fetched: {video_data['title']}", flush=True)
            return jsonify({"success": True, "video": video_data})
    except Exception as e:
        err_msg = str(e)
        print(f"[!] Error fetching {url}: {err_msg}", flush=True)
        if "is not a valid URL" in err_msg:
            clean_err = "Invalid YouTube URL. Please check the link and try again."
        elif "Sign in to confirm" in err_msg:
            clean_err = "YouTube bot protection triggered. Please try another video."
        else:
            clean_err = f"Could not load video: {err_msg[:120]}"
        return jsonify({"error": clean_err}), 400


def background_downloader(task_id, url, download_type, quality, audio_format):
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{task_id}_%(title).100B.%(ext)s")

    def progress_hook(d):
        task = download_tasks.get(task_id)
        if not task:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0

            pct = round((downloaded / total) * 100, 1) if total > 0 else 0.0
            task["status"] = "downloading"
            task["percent"] = min(pct, 98.0)
            task["speed"] = format_bytes(speed) + "/s" if speed else ""
            task["eta"] = f"{int(eta)}s remaining" if eta else ""
            task["downloaded"] = format_bytes(downloaded)
            task["total"] = format_bytes(total)
        elif d.get("status") == "finished":
            task["status"] = "converting"
            task["percent"] = 99.0
            task["eta"] = "Merging streams with FFmpeg..."

    def postprocessor_hook(d):
        task = download_tasks.get(task_id)
        if task:
            task["status"] = "converting"
            task["percent"] = 99.5
            task["eta"] = "Finalizing file with FFmpeg..."

    ydl_opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "restrictfilenames": True,
        "windowsfilenames": True,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
    }

    if FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = FFMPEG_PATH

    if download_type == "audio":
        if audio_format == "m4a":
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
        else:
            bitrate = "320" if "320" in audio_format else "192"
            if FFMPEG_PATH:
                ydl_opts["format"] = "bestaudio/best"
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": bitrate,
                }]
            else:
                ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
    else:
        # Video download
        if FFMPEG_PATH:
            ydl_opts["format"] = (
                f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={quality}]+bestaudio/"
                f"best[height<={quality}]/best"
            )
            ydl_opts["merge_output_format"] = "mp4"
        else:
            ydl_opts["format"] = f"best[height<={quality}][ext=mp4]/best[ext=mp4]/best"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        matched_files = [
            f for f in glob.glob(os.path.join(DOWNLOAD_DIR, f"{task_id}_*"))
            if not any(f.endswith(ext) for ext in [".part", ".ytdl", ".aria2", ".temp"])
            and os.path.isfile(f)
        ]
        if not matched_files:
            download_tasks[task_id]["status"] = "error"
            download_tasks[task_id]["error"] = "Download completed but file was not found."
            return

        downloaded_filepath = matched_files[0]
        filename = os.path.basename(downloaded_filepath).replace(f"{task_id}_", "")

        download_tasks[task_id]["status"] = "finished"
        download_tasks[task_id]["percent"] = 100.0
        download_tasks[task_id]["filename"] = filename
        download_tasks[task_id]["download_url"] = f"/api/get-file/{task_id}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Task {task_id} completed: {filename}", flush=True)
    except Exception as e:
        download_tasks[task_id]["status"] = "error"
        download_tasks[task_id]["error"] = str(e)
        print(f"[!] Task {task_id} error: {e}", flush=True)


@app.route("/api/download-start", methods=["POST"])
def start_download():
    data = request.get_json(silent=True) or {}
    raw_url = data.get("url", "").strip()
    download_type = data.get("type", "video")
    quality = data.get("quality", "1080")
    audio_format = data.get("audio_format", "mp3_192")

    if not raw_url:
        return jsonify({"error": "Missing URL"}), 400

    url = clean_youtube_url(raw_url)
    task_id = uuid.uuid4().hex[:10]

    download_tasks[task_id] = {
        "status": "starting",
        "percent": 0.0,
        "speed": "",
        "eta": "Connecting...",
        "downloaded": "0 MB",
        "total": "0 MB",
        "filename": "",
        "download_url": "",
        "error": None,
    }

    t = threading.Thread(
        target=background_downloader,
        args=(task_id, url, download_type, quality, audio_format),
        daemon=True,
    )
    t.start()

    return jsonify({"success": True, "task_id": task_id})


@app.route("/api/progress/<task_id>")
def get_progress(task_id):
    clean_id = re.sub(r"[^a-zA-Z0-9]", "", task_id)
    task = download_tasks.get(clean_id)
    if not task:
        return jsonify({"status": "not_found", "error": "Task not found"}), 404
    return jsonify(task)


@app.route("/api/get-file/<file_id>")
def get_file(file_id):
    clean_id = re.sub(r"[^a-zA-Z0-9]", "", file_id)
    matched_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{clean_id}_*"))

    if not matched_files:
        return "File not found or expired", 404

    target_file = matched_files[0]
    display_name = os.path.basename(target_file).replace(f"{clean_id}_", "")

    return send_file(
        target_file,
        as_attachment=True,
        download_name=display_name
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    is_cloud = os.environ.get("PORT") is not None
    host = "0.0.0.0" if is_cloud else "127.0.0.1"
    url = f"http://{host}:{port}"

    print("\n" + "=" * 55)
    print("  🚀 YouTube Downloader Web App Running!")
    print(f"  👉 Listening at: {url}")
    print("=" * 55 + "\n", flush=True)

    if not is_cloud:
        import webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    app.run(host=host, port=port, threaded=True, debug=False)

