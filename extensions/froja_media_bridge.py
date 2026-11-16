from __future__ import annotations

import base64
import json
import math
import random
import wave
from array import array
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 9010
FROJA_URL = f"http://127.0.0.1:{os.environ.get('FROJA_PORT', '3310')}"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "video-editor"
COMFY_OUTPUT = Path(r"G:\ComfyUI_NEW\output\Froja")
COMFY_PYTHON = Path(r"G:\ComfyUI_NEW\.venv\Scripts\python.exe")
FFMPEG = Path(r"G:\WanGP_Private\ffmpeg_bins\ffmpeg.exe")
FFPROBE = Path(r"G:\WanGP_Private\ffmpeg_bins\ffprobe.exe")
MUSETALK = Path(r"G:\WanGP_Private\MuseTalk")
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def reply(handler, data, status=200):
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(raw)


def body(handler):
    return json.loads(handler.rfile.read(int(handler.headers.get("Content-Length", "0"))) or b"{}")


def latest_image():
    items = [p for p in COMFY_OUTPUT.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    if not items:
        raise RuntimeError("Generate or upload an image first.")
    return max(items, key=lambda p: p.stat().st_mtime)


def data_file(value, kinds):
    match = re.match(r"^data:([^;]+);base64,(.+)$", str(value), re.I | re.S)
    if not match:
        return None
    types = {
        "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
        "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav",
        "audio/x-wav": ".wav", "audio/mp4": ".m4a", "audio/ogg": ".ogg",
    }
    mime = match.group(1).lower()
    category = mime.split("/", 1)[0]
    if category not in kinds or mime not in types:
        return None
    raw = base64.b64decode(match.group(2), validate=True)
    if len(raw) > 300 * 1024 * 1024:
        raise ValueError("Media is larger than the 300 MB private limit.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f"upload-{uuid.uuid4().hex}{types[mime]}"
    target.write_bytes(raw)
    return target


def set_job(job_id, **values):
    with LOCK:
        JOBS[job_id].update(values)


def run(command, timeout=1800, cwd=None, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "Media command failed")[-2400:])
    return result


def probe(path):
    result = run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], 30)
    return float(json.loads(result.stdout)["format"]["duration"])


def has_audio_stream(path):
    result = run([
        str(FFPROBE), "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=index", "-of", "json", str(path),
    ], 30)
    return bool(json.loads(result.stdout).get("streams"))

def generate_speech(job_id, text):
    wav = OUTPUT / f"froja-{job_id}-voice.wav"
    script = ROOT / "extensions" / "froja_local_tts.py"
    bootstrap = (
        "import sys,torch,transformers,runpy; from transformers import AlbertModel; "
        f"sys.argv=[r'{script}','--text',sys.argv[1],'--output',sys.argv[2]]; "
        f"runpy.run_path(r'{script}',run_name='__main__')"
    )
    run([str(COMFY_PYTHON), "-c", bootstrap, text, str(wav)], 300)
    return wav


def talking_portrait(job_id, image, speech):
    set_job(job_id, phase="Creating local voice", progress=.14)
    audio = generate_speech(job_id, speech)
    duration = probe(audio)
    base = OUTPUT / f"froja-{job_id}-base.mp4"
    frames = max(25, int(duration * 25 + .5))
    vf = (
        "scale=768:768:force_original_aspect_ratio=increase,crop=768:768,"
        f"zoompan=z='min(zoom+0.00012,1.03)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=768x768:fps=25,format=yuv420p"
    )
    set_job(job_id, phase="Preparing portrait motion", progress=.27)
    run([str(FFMPEG), "-y", "-loop", "1", "-i", str(image), "-t", f"{duration:.3f}", "-vf", vf,
         "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(base)], 180)
    yaml = OUTPUT / f"froja-{job_id}.yaml"
    target_name = f"froja-{job_id}.mp4"
    yaml.write_text(
        f"froja_job:\n  video_path: \"{base.as_posix()}\"\n  audio_path: \"{audio.as_posix()}\"\n"
        f"  result_name: \"{target_name}\"\n  bbox_shift: 0\n", encoding="utf-8"
    )
    set_job(job_id, phase="Animating speech and face", progress=.42)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(MUSETALK) + os.pathsep + str(MUSETALK / "musetalk" / "utils")
    env["PATH"] = str(FFMPEG.parent) + os.pathsep + env.get("PATH", "")
    result_dir = OUTPUT / f"musetalk-{job_id}"
    command = [str(COMFY_PYTHON), str(ROOT / "extensions" / "froja_run_musetalk_windows.py"),
        "--inference_config", str(yaml), "--result_dir", str(result_dir),
        "--unet_model_path", str(MUSETALK / "models" / "musetalkV15" / "unet.pth"),
        "--unet_config", str(MUSETALK / "models" / "musetalkV15" / "musetalk.json"),
        "--whisper_dir", str(MUSETALK / "models" / "whisper"), "--ffmpeg_path", str(FFMPEG.parent),
        "--version", "v15", "--use_float16", "--batch_size", "4"]
    run(command, 1800, str(MUSETALK), env)
    target = result_dir / "v15" / target_name
    if not target.is_file():
        raise RuntimeError("MuseTalk completed without producing the expected video.")
    return target, duration, True


def generate_text_scene(job_id, prompt):
    if not prompt.strip():
        raise ValueError("Describe the video scene first.")
    set_job(job_id, phase="Generating scene from text", progress=.08)
    payload = {
        "checkpoint": "zImageBase_base.safetensors",
        "architecture": "Z-Image",
        "prompt": prompt,
        "negative_prompt": "people, person, woman, man, archer, bow, arrow, warrior, human figure" if "no people" in prompt.lower() else "",
        "steps": 8, "cfg": 1.0, "seed": -1, "width": 768, "height": 512,
        "sampler": "res_multistep", "scheduler": "simple", "loras": [],
    }
    request = urllib.request.Request(
        f"{FROJA_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        started = json.loads(response.read().decode("utf-8"))
    prompt_id = started.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(started.get("error", "Froja image engine did not accept the scene."))
    for attempt in range(180):
        with urllib.request.urlopen(f"{FROJA_URL}/api/jobs/{prompt_id}", timeout=20) as response:
            state = json.loads(response.read().decode("utf-8"))
        if state.get("status") == "failed":
            raise RuntimeError(state.get("error", "Scene generation failed."))
        if state.get("status") == "complete" and state.get("images"):
            target = OUTPUT / f"froja-{job_id}-scene.png"
            with urllib.request.urlopen(FROJA_URL + state["images"][0], timeout=60) as response:
                target.write_bytes(response.read())
            set_job(job_id, phase="Animating generated scene", progress=.30)
            return target
        if attempt % 10 == 0:
            set_job(job_id, phase="Generating scene from text", progress=min(.28, .08 + attempt / 900))
        time.sleep(2)
    raise TimeoutError("The scene image did not finish within six minutes.")

def generate_soundscape(job_id, prompt, duration):
    """Create a fully local, prompt-aware effects track without an API."""
    target = OUTPUT / f"froja-{job_id}-soundscape.wav"
    rate = 48000
    total = int(duration * rate)
    text = prompt.lower()
    dragon_scene = any(word in text for word in ("dragon", "creature", "baby beast"))
    clock_scene = any(word in text for word in ("clock", "timepiece", "mechanical", "gear"))
    knight_scene = any(word in text for word in ("knight", "warhorse", "medieval", "armored horse"))
    rng = random.Random(job_id)
    samples = array("h")

    def envelope(t, start, length):
        if t < start or t >= start + length:
            return 0.0
        x = (t - start) / length
        return min(1.0, x * 12.0) * math.exp(-3.8 * x)

    for index in range(total):
        t = index / rate
        value = 0.012 * math.sin(2 * math.pi * 58 * t) + 0.005 * (rng.random() * 2 - 1)
        if clock_scene:
            tick = t % 1.0
            if tick < 0.035:
                value += 0.32 * math.sin(2 * math.pi * 1700 * t) * math.exp(-90 * tick)
        if knight_scene:
            # Strong layered winter wind with a slowly shifting low-frequency body.
            value += 0.018 * (rng.random() * 2 - 1) * (0.65 + 0.35 * math.sin(2 * math.pi * 0.17 * t))
            value += 0.012 * math.sin(2 * math.pi * 86 * t)
            # Three slow, weighty hoof impacts and compressed-snow crunches.
            for step in (0.85, 3.10, 5.55):
                e = envelope(t, step, 0.48)
                value += e * (0.28 * math.sin(2 * math.pi * 72 * t) + 0.15 * (rng.random() * 2 - 1))
                e2 = envelope(t, step + 0.16, 0.40)
                value += e2 * 0.10 * (rng.random() * 2 - 1)
            # Small irregular metal plate and harness movements.
            for clink, frequency in ((1.28, 1280), (2.42, 980), (3.56, 1420), (4.82, 1120), (6.22, 1510)):
                e = envelope(t, clink, 0.16)
                value += e * 0.09 * math.sin(2 * math.pi * frequency * t)
        if dragon_scene:
            # Curious presentation chirp near the opening.
            e = envelope(t, 0.42, 0.34)
            value += e * 0.22 * math.sin(2 * math.pi * (720 + 620 * (t - 0.42)) * t)
            # Three small crunchy candy bites during 2-4 seconds.
            for bite in (2.05, 2.72, 3.38):
                e = envelope(t, bite, 0.24)
                value += e * (0.22 * (rng.random() * 2 - 1) + 0.10 * math.sin(2 * math.pi * 210 * t))
            # Pastel magical shimmer begins after swallowing.
            for start_chime, frequency in ((4.02, 1046), (4.22, 1318), (4.44, 1568), (4.68, 2093)):
                e = envelope(t, start_chime, 0.9)
                value += e * 0.12 * math.sin(2 * math.pi * frequency * t)
            # Tiny upward hiccup followed by a satisfied chirp.
            e = envelope(t, 5.12, 0.22)
            value += e * 0.30 * math.sin(2 * math.pi * (430 + 1300 * max(0, t - 5.12)) * t)
            e = envelope(t, 5.48, 0.30)
            value += e * 0.17 * math.sin(2 * math.pi * 920 * t)
        # Gentle fade at both ends and safe limiting.
        fade = min(1.0, t / 0.18, max(0.0, (duration - t) / 0.25))
        samples.append(int(max(-0.92, min(0.92, value * fade)) * 32767))

    with wave.open(str(target), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())
    return target
def ltx2b_real_video(job_id, prompt, profile):
    """Run native LTX-Video 2B multi-frame diffusion through local ComfyUI."""
    profiles = {
        "safe": (512, 320, 49, 12, 24.0),
        "balanced": (640, 384, 73, 16, 24.0),
        "experimental": (768, 480, 97, 20, 24.0),
    }
    width, height, frames, steps, fps = profiles.get(profile, profiles["safe"])
    set_job(job_id, phase="Loading LTX Video 2B", progress=.06)
    try:
        free = urllib.request.Request("http://127.0.0.1:8188/free", data=json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(free, timeout=30).read()
    except Exception:
        pass
    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ltx-video-2b-v0.9.5.safetensors"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn_scaled.safetensors", "type": "ltxv", "device": "default"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "worst quality, inconsistent motion, distorted anatomy, extra limbs, morphing, frozen subject"}},
        "5": {"class_type": "LTXVConditioning", "inputs": {"positive": ["3", 0], "negative": ["4", 0], "frame_rate": fps}},
        "6": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": width, "height": height, "length": frames, "batch_size": 1}},
        "7": {"class_type": "LTXVScheduler", "inputs": {"steps": steps, "max_shift": 2.05, "base_shift": 0.95, "stretch": True, "terminal": 0.1, "latent": ["6", 0]}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": int(time.time_ns() % (2**63 - 1))}},
        "10": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["5", 0], "negative": ["5", 1], "cfg": 3.0}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["10", 0], "sampler": ["8", 0], "sigmas": ["7", 0], "latent_image": ["6", 0]}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["1", 2]}},
        "13": {"class_type": "CreateVideo", "inputs": {"images": ["12", 0], "fps": fps, "bit_depth": 8}},
        "14": {"class_type": "SaveVideo", "inputs": {"video": ["13", 0], "filename_prefix": f"Froja/LTX2B/{job_id}", "format": "mp4", "codec": "h264"}},
    }
    request = urllib.request.Request("http://127.0.0.1:8188/prompt", data=json.dumps({"prompt": workflow, "client_id": "froja-ltx2b"}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        started = json.loads(response.read().decode("utf-8"))
    if started.get("node_errors"):
        raise RuntimeError("LTX workflow validation failed: " + json.dumps(started["node_errors"]))
    prompt_id = started.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(started.get("error", "LTX Video did not accept the workflow."))
    for attempt in range(600):
        with urllib.request.urlopen(f"http://127.0.0.1:8188/history/{prompt_id}", timeout=20) as response:
            history = json.loads(response.read().decode("utf-8"))
        record = history.get(prompt_id)
        if record:
            status = record.get("status", {})
            if status.get("status_str") != "success":
                raise RuntimeError("LTX Video failed: " + json.dumps(status))
            item = record["outputs"]["14"]["images"][0]
            source = Path(r"G:\ComfyUI_NEW\output") / item.get("subfolder", "") / item["filename"]
            if not source.is_file():
                raise RuntimeError("LTX completed but its MP4 could not be found.")
            raw_target = OUTPUT / f"froja-{job_id}-ltx2b-raw.mp4"
            shutil.copy2(source, raw_target)
            duration = probe(raw_target)
            soundtrack = generate_soundscape(job_id, prompt, duration)
            target = OUTPUT / f"froja-{job_id}-ltx2b.mp4"
            set_job(job_id, phase="Adding synchronized local sound", progress=.94)
            run([str(FFMPEG), "-y", "-i", str(raw_target), "-i", str(soundtrack), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(target)], 180)
            return target, probe(target), True
        if attempt % 5 == 0:
            set_job(job_id, phase="Generating real LTX motion", progress=min(.90, .12 + attempt / 750))
        time.sleep(2)
    raise TimeoutError("LTX Video did not finish within twenty minutes.")

def motion_video(job_id, image, prompt, profile, audio=None):
    duration = {"safe": 4, "balanced": 6, "experimental": 8}.get(profile, 4)
    frames = duration * 30
    target = OUTPUT / f"froja-{job_id}.mp4"
    action = any(word in prompt.lower() for word in ("action", "run", "jump", "fight", "kick", "fast", "impact"))
    if action:
        vf = ("scale=1840:1035:force_original_aspect_ratio=increase,crop=1840:1035,"
              f"zoompan=z='1+0.40*on/{frames-1}':x='(iw-iw/zoom)*(0.50+0.13*sin(on/8))':"
              f"y='(ih-ih/zoom)*(0.48+0.10*cos(on/11))':d={frames}:s=1280x720:fps=30,"
              "eq=contrast=1.09:saturation=1.13,unsharp=5:5:.45:5:5:0,format=yuv420p")
    else:
        vf = ("scale=1760:990:force_original_aspect_ratio=increase,crop=1760:990,"
              f"zoompan=z='1+0.24*on/{frames-1}':x='(iw-iw/zoom)*(0.46+0.08*sin(on/18))':"
              f"y='(ih-ih/zoom)*(0.50+0.055*cos(on/23))':d={frames}:s=1280x720:fps=30,"
              "eq=contrast=1.045:saturation=1.06,unsharp=5:5:.25:5:5:0,format=yuv420p")
    set_job(job_id, phase="Creating local soundscape", progress=.32)
    soundtrack = audio or generate_soundscape(job_id, prompt, duration)
    set_job(job_id, phase="Rendering cinematic motion", progress=.46)
    command = [str(FFMPEG), "-y", "-loop", "1", "-i", str(image), "-stream_loop", "-1", "-i", str(soundtrack),
               "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
               "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest",
               "-movflags", "+faststart", str(target)]
    run(command, 240)
    return target, duration, True
def edit_video(job_id, request):
    source = data_file(request.get("source", ""), {"video"})
    if not source:
        raise ValueError("Choose a source video for the editor.")
    audio = data_file(request.get("audio", ""), {"audio"})
    start = max(0.0, float(request.get("trim_start", 0)))
    end = max(0.0, float(request.get("trim_end", 0)))
    speed = max(.5, min(2.0, float(request.get("speed", 1))))
    preset = str(request.get("aspect", "original"))
    sizes = {"youtube": (1280, 720), "tiktok": (720, 1280), "instagram": (1080, 1080), "facebook": (1280, 720)}
    target = OUTPUT / f"froja-edit-{job_id}.mp4"
    command = [str(FFMPEG), "-y", "-ss", str(start), "-i", str(source)]
    if audio:
        command += ["-i", str(audio)]
    if end > start:
        command += ["-t", str(end - start)]
    filters = []
    if preset in sizes:
        w, h = sizes[preset]
        filters.append(f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}")
    filters += [f"setpts=PTS/{speed}", "format=yuv420p"]
    command += ["-vf", ",".join(filters), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
    if audio:
        command += ["-map", "0:v:0", "-map", "1:a:0", "-af", f"atempo={speed}", "-c:a", "aac", "-shortest"]
    else:
        command += ["-af", f"atempo={speed}", "-c:a", "aac"]
    command += ["-movflags", "+faststart", str(target)]
    set_job(job_id, phase="Editing and exporting", progress=.32)
    run(command, 600)
    return target, probe(target), has_audio_stream(target)


def process(job_id, request):
    try:
        mode = str(request.get("mode", "image"))
        source = data_file(request.get("source", ""), {"image"})
        audio = data_file(request.get("audio", ""), {"audio"})
        prompt = str(request.get("prompt", "")).strip()
        speech = str(request.get("speech", "")).strip()
        if mode == "edit":
            target, duration, has_audio = edit_video(job_id, request)
        elif speech:
            if not source:
                raise ValueError("Choose the portrait image that should speak. Froja will not reuse an older image automatically.")
            target, duration, has_audio = talking_portrait(job_id, source, speech)
        elif mode == "text" and str(request.get("engine", "ltx2b")) == "ltx2b":
            target, duration, has_audio = ltx2b_real_video(job_id, prompt, str(request.get("profile", "safe")))
        elif mode == "text":
            scene = generate_text_scene(job_id, prompt)
            target, duration, has_audio = motion_video(job_id, scene, prompt, str(request.get("profile", "safe")), audio)
        else:
            if not source:
                raise ValueError("Choose the source image for Image to Video.")
            target, duration, has_audio = motion_video(job_id, source, prompt, str(request.get("profile", "safe")), audio)
        set_job(job_id, status="complete", phase="Complete", progress=1, output=str(target),
                video_url=f"/api/private-video/files/{job_id}", duration=duration, has_audio=has_audio)
    except Exception as exc:
        set_job(job_id, status="failed", phase="Failed", progress=0, error=str(exc))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[Froja Media]", fmt % args)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/status":
            ready = all(item.is_file() for item in (FFMPEG, FFPROBE, COMFY_PYTHON))
            return reply(self, {"online": True, "ready": ready, "engine": "Froja Local Media",
                "capabilities": ["text-to-motion", "image-to-video", "talking-portrait", "local-tts", "video-editor", "social-export"]})
        if path == "/library":
            files = sorted(OUTPUT.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)[:100]
            return reply(self, {"items": [{"name": p.name, "path": str(p), "size": p.stat().st_size,
                "created": p.stat().st_mtime} for p in files]})
        if path.startswith("/jobs/"):
            key = path.rsplit("/", 1)[-1]
            with LOCK:
                item = dict(JOBS.get(key, {"status": "missing", "error": "Unknown job"}))
            return reply(self, item, 200 if item["status"] != "missing" else 404)
        if path.startswith("/files/"):
            key = path.rsplit("/", 1)[-1]
            with LOCK:
                target = Path(str(JOBS.get(key, {}).get("output", "")))
            if not target.is_file() or OUTPUT.resolve() not in target.resolve().parents:
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
        if self.path in {"/generate", "/edit"}:
            request = body(self)
            if self.path == "/edit":
                request["mode"] = "edit"
            key = uuid.uuid4().hex
            with LOCK:
                JOBS[key] = {"job_id": key, "status": "queued", "phase": "Queued", "progress": 0, "created": time.time()}
            threading.Thread(target=process, args=(key, request), daemon=True).start()
            return reply(self, {"job_id": key, "status": "queued"})
        if self.path == "/cancel":
            request = body(self); key = str(request.get("job_id", ""))
            with LOCK:
                if key in JOBS: JOBS[key].update(status="cancelled", phase="Cancelled")
            return reply(self, {"ok": True})
        self.send_error(404)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    print(f"Froja Local Media bridge: http://127.0.0.1:{PORT}")
    print("Text motion, talking portraits, local speech, editing and social exports are enabled.")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
