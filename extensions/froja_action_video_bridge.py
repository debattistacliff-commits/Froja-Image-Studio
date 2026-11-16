from __future__ import annotations

import base64, json, mimetypes, re, subprocess, threading, time, urllib.parse, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 9010
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "video-editor"
FFMPEG = Path(r"G:\WanGP_Private\ffmpeg_bins\ffmpeg.exe")
COMFY_OUTPUT = Path(r"G:\ComfyUI_NEW\output\Froja")
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def reply(handler, data, status=200):
    raw = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(raw)


def body(handler):
    return json.loads(handler.rfile.read(int(handler.headers.get("Content-Length", "0"))) or b"{}")


def latest_image():
    items = [p for p in COMFY_OUTPUT.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    if not items:
        raise RuntimeError("Generate or upload an image first.")
    return max(items, key=lambda p: p.stat().st_mtime)


def data_file(value, kind):
    match = re.match(r"^data:([^;]+);base64,(.+)$", value, re.I | re.S)
    if not match:
        return None
    types = ({"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"} if kind == "image" else
             {"audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mp4": ".m4a"})
    suffix = types.get(match.group(1).lower())
    if not suffix:
        return None
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f"upload-{uuid.uuid4().hex}{suffix}"
    target.write_bytes(base64.b64decode(match.group(2), validate=True))
    return target


def render(job_id, request):
    try:
        with LOCK:
            JOBS[job_id].update(status="running", phase="Planning action", progress=.08)
        source_value = str(request.get("source", ""))
        image = data_file(source_value, "image") or latest_image()
        audio = data_file(source_value, "audio")
        profile = str(request.get("profile", "safe"))
        duration = {"safe": 4, "balanced": 5, "experimental": 6}.get(profile, 4)
        prompt = str(request.get("prompt", "")).lower()
        action = any(w in prompt for w in ("action", "kick", "strike", "fight", "run", "jump", "ball", "impact", "explosion", "fast"))
        frames = duration * 30
        target = OUTPUT / f"froja-{job_id}.mp4"
        if action:
            vf = (
                "scale=1760:990:force_original_aspect_ratio=increase,crop=1760:990,"
                f"zoompan=z='if(lt(on,{frames}*0.28),1+0.10*on/({frames}*0.28),if(lt(on,{frames}*0.72),1.10+0.34*(on-{frames}*0.28)/({frames}*0.44),1.44-0.10*(on-{frames}*0.72)/({frames}*0.28)))':"
                f"x='(iw-iw/zoom)*(0.48+0.13*sin(on/10))+if(gt(on,{int(frames*.70)}),10*sin(on*2.7),0)':"
                f"y='(ih-ih/zoom)*(0.46+0.10*cos(on/13))+if(gt(on,{int(frames*.70)}),7*cos(on*3.1),0)':"
                f"d={frames}:s=1280x720:fps=30,"
                f"eq=contrast=1.10:saturation=1.16:brightness='if(between(t,{duration*.70:.2f},{duration*.78:.2f}),0.16,0.01*sin(10*t))':eval=frame,"
                "unsharp=5:5:0.55:5:5:0,vignette=PI/5,format=yuv420p"
            )
        else:
            vf = ("scale=1600:900:force_original_aspect_ratio=increase,crop=1600:900,"
                  f"zoompan=z='1+0.12*on/{frames-1}':x='(iw-iw/zoom)*(0.12+0.18*on/{frames-1})':"
                  f"y='(ih-ih/zoom)*(0.48+0.03*sin(on/15))':d={frames}:s=1280x720:fps=30,format=yuv420p")
        command = [str(FFMPEG), "-y", "-i", str(image)]
        if audio:
            command += ["-stream_loop", "-1", "-i", str(audio)]
        elif action:
            command += ["-f", "lavfi", "-i", f"sine=frequency=92:sample_rate=48000:duration={duration}"]
        command += ["-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19"]
        if audio:
            command += ["-c:a", "aac", "-b:a", "160k", "-shortest"]
        elif action:
            command += ["-af", f"volume='0.10+0.22*between(t,{duration*.64:.2f},{duration*.84:.2f})':eval=frame,tremolo=f=9:d=.75,lowpass=f=900,afade=t=in:st=0:d=.20,afade=t=out:st={duration-.45:.2f}:d=.45", "-c:a", "aac", "-b:a", "160k", "-shortest"]
        else:
            command += ["-an"]
        command += ["-movflags", "+faststart", str(target)]
        with LOCK:
            JOBS[job_id].update(phase="Rendering action and sound", progress=.38)
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if result.returncode or not target.is_file():
            raise RuntimeError((result.stderr or "FFmpeg failed")[-1200:])
        with LOCK:
            JOBS[job_id].update(status="complete", phase="Complete", progress=1, output=str(target),
                                video_url=f"/api/private-video/files/{job_id}", width=1280, height=720,
                                duration=duration, has_audio=bool(audio or action), action=action)
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(status="failed", phase="Failed", error=str(exc), progress=0)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[Froja Action Video]", fmt % args)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/status":
            return reply(self, {"online": True, "ready": FFMPEG.is_file(), "engine": "Froja Action Video",
                                "ffmpeg": str(FFMPEG), "capabilities": ["text", "image", "action-motion", "generated-audio", "audio-reference", "mp4"]})
        if path.startswith("/jobs/"):
            key = path.rsplit("/", 1)[-1]
            with LOCK:
                item = dict(JOBS.get(key, {"status": "missing", "error": "Unknown job"}))
            return reply(self, item, 200 if item["status"] != "missing" else 404)
        if path.startswith("/files/"):
            key = path.rsplit("/", 1)[-1]
            with LOCK:
                target = Path(str(JOBS.get(key, {}).get("output", "")))
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
            request = body(self)
            key = uuid.uuid4().hex
            with LOCK:
                JOBS[key] = {"job_id": key, "status": "queued", "phase": "Queued", "progress": 0, "created": time.time()}
            threading.Thread(target=render, args=(key, request), daemon=True).start()
            return reply(self, {"job_id": key, "status": "queued"})
        self.send_error(404)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    print(f"Froja Action Video: http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
