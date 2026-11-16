from __future__ import annotations

import base64
import json
import mimetypes
import re
import subprocess
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 9010
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "video-editor"
FFMPEG = Path(r"G:\WanGP_Private\ffmpeg_bins\ffmpeg.exe")
COMFY_OUTPUT = Path(r"G:\ComfyUI_NEW\output\Froja")
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def reply(handler: BaseHTTPRequestHandler, data: dict, status: int = 200):
    raw = json.dumps(data).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(raw)


def read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    return json.loads(handler.rfile.read(length) or b"{}")


def latest_image() -> Path:
    images = [p for p in COMFY_OUTPUT.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    if not images:
        raise RuntimeError("No Froja image is available. Generate or upload an image first.")
    return max(images, key=lambda p: p.stat().st_mtime)


def save_data_url(value: str, kind: str) -> Path | None:
    if not value.startswith("data:"):
        return None
    match = re.match(r"^data:([^;]+);base64,(.+)$", value, flags=re.I | re.S)
    if not match:
        raise ValueError("The uploaded media could not be read.")
    mime = match.group(1).lower()
    image_types = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
    audio_types = {"audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mp4": ".m4a"}
    allowed = image_types if kind == "image" else audio_types
    if mime not in allowed:
        return None
    raw = base64.b64decode(match.group(2), validate=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f"upload-{uuid.uuid4().hex}{allowed[mime]}"
    target.write_bytes(raw)
    return target


def render(job_id: str, request: dict):
    try:
        with LOCK:
            JOBS[job_id].update(status="running", phase="Preparing media", progress=0.08)
        source_value = str(request.get("source", ""))
        source = save_data_url(source_value, "image") or latest_image()
        audio = save_data_url(source_value, "audio")
        profile = str(request.get("profile", "safe"))
        duration = {"safe": 4, "balanced": 5, "experimental": 6}.get(profile, 4)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        target = OUTPUT / f"froja-{job_id}.mp4"
        frames = duration * 30
        vf = (
            "scale=1600:900:force_original_aspect_ratio=increase,crop=1600:900,"
            f"zoompan=z='1+0.12*on/{frames-1}':x='(iw-iw/zoom)*(0.12+0.18*on/{frames-1})':"
            f"y='(ih-ih/zoom)*(0.48+0.03*sin(on/15))':d={frames}:s=1280x720:fps=30,"
            "eq=brightness='0.012*sin(2*PI*t/3)':eval=frame,format=yuv420p"
        )
        command = [str(FFMPEG), "-y", "-i", str(source)]
        if audio:
            command += ["-stream_loop", "-1", "-i", str(audio)]
        command += ["-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19"]
        if audio:
            command += ["-c:a", "aac", "-b:a", "160k", "-shortest"]
        else:
            command += ["-an"]
        command += ["-movflags", "+faststart", str(target)]
        with LOCK:
            JOBS[job_id].update(phase="Rendering video", progress=0.35)
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if result.returncode or not target.is_file():
            raise RuntimeError((result.stderr or "FFmpeg failed")[-1200:])
        with LOCK:
            JOBS[job_id].update(
                status="complete", phase="Complete", progress=1,
                output=str(target), video_url=f"/api/private-video/files/{job_id}",
                width=1280, height=720, duration=duration, has_audio=bool(audio),
            )
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(status="failed", phase="Failed", error=str(exc), progress=0)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[Froja Video]", fmt % args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/status":
            return reply(self, {
                "online": True, "ready": FFMPEG.is_file(), "engine": "Froja Lightweight Video",
                "ffmpeg": str(FFMPEG), "capabilities": ["text", "image", "audio-reference", "mp4"],
            })
        if parsed.path.startswith("/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            with LOCK:
                item = dict(JOBS.get(job_id, {"status": "missing", "error": "Unknown video job."}))
            return reply(self, item, 200 if item.get("status") != "missing" else 404)
        if parsed.path.startswith("/files/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            with LOCK:
                item = JOBS.get(job_id, {})
            target = Path(str(item.get("output", "")))
            if not target.is_file() or target.parent.resolve() != OUTPUT.resolve():
                return self.send_error(404)
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "video/mp4")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path == "/generate":
            request = read_body(self)
            job_id = uuid.uuid4().hex
            with LOCK:
                JOBS[job_id] = {"job_id": job_id, "status": "queued", "phase": "Queued", "progress": 0, "created": time.time()}
            threading.Thread(target=render, args=(job_id, request), daemon=True).start()
            return reply(self, {"job_id": job_id, "status": "queued"})
        if self.path == "/cancel":
            request = read_body(self)
            job_id = str(request.get("job_id", ""))
            with LOCK:
                if job_id in JOBS:
                    JOBS[job_id].update(status="cancelled", phase="Cancelled")
            return reply(self, {"ok": True})
        self.send_error(404)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    print(f"Froja Lightweight Video bridge: http://127.0.0.1:{PORT}")
    print(f"FFmpeg: {FFMPEG}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
