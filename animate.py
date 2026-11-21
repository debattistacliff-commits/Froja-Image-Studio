from __future__ import annotations

import io
import json
import math
import random
import shutil
import subprocess
import threading
import uuid
from bisect import bisect_right
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps


DEFAULT_PROMPT = (
    "gentle natural motion: clouds drift, water shimmers, leaves and hair move in a light breeze, "
    "soft light changes, subtle slow camera push-in"
)
REAL_PROMPT = (
    "The person smiles naturally, turns their head slightly and looks back at the camera, with small natural gestures. "
    "The background moves gently: leaves sway, light flickers. Realistic motion, steady camera."
)
REAL_SOUND = "gentle natural ambience matching the scene"
REAL_FPS = 24
REAL_SCALE = 2
REAL_UPSCALE_MODEL = "RealESRGAN_x2plus.pth"
PRESETS = ("orbit", "push-in", "crane", "bullet-time")
ORBIT_PRESETS = ("orbit", "bullet-time")
CAMERA_FPS = 30
LIFE_FPS = 24
CAMERA_DISTANCE = 4.2

_jobs = {}
_jobs_lock = threading.Lock()
_gpu_lock = threading.Lock()
_gpu_owner = None
_gpu_requests = 0


@contextmanager
def gpu_slot(*, reserve=False):
    global _gpu_owner, _gpu_requests
    owner = threading.get_ident()
    with _gpu_lock:
        if _gpu_owner not in (None, owner):
            raise RuntimeError("Animate is using the GPU. Wait for it to finish or press Stop.")
        if reserve:
            if _gpu_requests:
                raise RuntimeError("The image engine is handling another request. Try again in a moment.")
            _gpu_owner = owner
        else:
            _gpu_requests += 1
    try:
        yield
    finally:
        with _gpu_lock:
            if reserve:
                _gpu_owner = None
            else:
                _gpu_requests -= 1


def validate_request(payload: dict, decode_image) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Send an animation request as a JSON object.")
    mode = payload.get("mode")
    if mode not in ("real", "life", "camera"):
        raise ValueError("Choose real, life, or camera mode.")
    preset = payload.get("preset", "orbit")
    if preset not in PRESETS:
        raise ValueError("Choose orbit, push-in, crane, or bullet-time.")
    protect = payload.get("protect", True)
    if not isinstance(protect, bool):
        raise ValueError("Protect must be true or false.")
    default_seconds = {"real": 3, "life": 5, "camera": None if preset in ORBIT_PRESETS else 5}[mode]
    seconds = payload.get("seconds", default_seconds)
    max_seconds = 15 if mode == "camera" else 5
    if (seconds is not None or "seconds" in payload) and (
        type(seconds) not in (int, float) or not 1 <= seconds <= max_seconds
    ):
        raise ValueError(f"Choose a duration between 1 and {max_seconds} seconds.")

    def image_bytes(source, label):
        if not isinstance(source, str) or len(source) > 35 * 1024 * 1024:
            raise ValueError(f"{label} must be a PNG, JPEG, or WebP image up to 25 MB.")
        raw, _ = decode_image(source, label)
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if min(image.size) < 2 or image.width * image.height > 40_000_000:
                    raise ValueError(f"{label} has unsupported dimensions.")
                image.verify()
        except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ValueError(f"{label} could not be read.") from exc
        return raw

    prompt = payload.get("prompt", "")
    words = payload.get("protect_words", "the person")
    if not isinstance(prompt, str) or len(prompt) > 2000:
        raise ValueError("Enter a motion prompt up to 2,000 characters.")
    if mode == "real":
        source = payload.get("image")
        image_bytes(source, "Master picture")
        sound = payload.get("sound", REAL_SOUND)
        if not isinstance(sound, str) or len(sound) > 500:
            raise ValueError("Enter a sound description up to 500 characters.")
        return dict(mode=mode, source=source, seconds=seconds, prompt=prompt.strip() or REAL_PROMPT, sound=sound.strip())
    if not isinstance(words, str) or not words.strip() or len(words) > 500:
        raise ValueError("Enter up to 500 characters describing what to protect.")
    request = dict(
        mode=mode, preset=preset, protect=protect, seconds=seconds,
        prompt=prompt.strip() or DEFAULT_PROMPT, protect_words=words.strip(),
        image=image_bytes(payload.get("image"), "Master picture"), views={},
    )
    if mode == "camera" and preset in ORBIT_PRESETS:
        views = payload.get("views")
        azimuths = payload.get("azimuths")
        if not isinstance(views, list) or not 3 <= len(views) <= 36:
            raise ValueError("Make at least 3 distinct camera views first (up to 36).")
        if not isinstance(azimuths, list) or len(azimuths) != len(views):
            raise ValueError("Send one azimuth for each camera view.")
        if any(type(a) not in (int, float) or not math.isfinite(a) for a in azimuths):
            raise ValueError("Camera azimuths must be finite numbers.")
        angles = [a % 360 for a in azimuths]
        if len(set(angles)) != len(angles):
            raise ValueError("Send one camera view per distinct azimuth.")
        request["views"] = {
            angle: image_bytes(view, f"Camera view {index}")
            for index, (angle, view) in enumerate(zip(angles, views), 1)
        }
        request["views"].setdefault(0, request["image"])
    return request


def camera_path(preset: str, azimuths=(), seconds=None) -> list[dict]:
    def key(t, azimuth=0, elevation=0, distance=CAMERA_DISTANCE, zoom=1):
        return dict(t=round(t, 6), azimuth=azimuth, elevation=elevation, distance=distance, zoom=zoom)

    if preset == "push-in":
        return [key(0), key(seconds or 5, distance=CAMERA_DISTANCE / 1.12, zoom=1.12)]
    if preset == "crane":
        return [key(0, elevation=-12, zoom=1.08), key(seconds or 5, elevation=12, zoom=1.12)]
    if preset not in ORBIT_PRESETS:
        raise ValueError("Unknown camera preset.")
    angles = sorted({0, *(angle % 360 for angle in azimuths)}) + [360]
    duration = 0.6 if preset == "orbit" else 0.28
    t = 0.0
    keys = [key(t)]
    if preset == "bullet-time":
        t = 0.25
        keys.append(key(t))
    for start, end in zip(angles, angles[1:]):
        step = duration * (end - start) / 45
        if preset == "bullet-time" and (start == 0 or end == 360):
            step += 0.15
        t += max(1 / CAMERA_FPS, step)
        keys.append(key(t, azimuth=end))
    if seconds is not None:
        for pose in keys:
            pose["t"] = round(pose["t"] * seconds / t, 6)
    return keys


def blender_script(keys: list[dict]) -> str:
    return f'''import math
from bisect import bisect_right

import bpy
from mathutils import Vector

KEYS = {json.dumps(keys, ensure_ascii=False)}
FPS = {CAMERA_FPS}
TARGET = Vector((0, 0, 0.85))  # Center of a 1.7 m subject standing at the origin.

scene = bpy.context.scene
camera = bpy.data.objects.new("Froja Camera", bpy.data.cameras.new("Froja Camera"))
scene.collection.objects.link(camera)
scene.camera = camera
scene.render.fps = FPS
scene.render.fps_base = 1
scene.frame_start = 1
scene.frame_end = round(KEYS[-1]["t"] * FPS) + 1

times = [key["t"] for key in KEYS]
# Sample the eased spherical path so sparse views still follow a circular arc.
for frame in range(scene.frame_start, scene.frame_end + 1):
    time = min(times[-1], (frame - 1) / FPS)
    index = min(len(KEYS) - 2, bisect_right(times, time) - 1)
    a, b = KEYS[index:index + 2]
    u = (time - a["t"]) / (b["t"] - a["t"])
    mix = u * u * (3 - 2 * u)
    pose = {{name: a[name] + (b[name] - a[name]) * mix
            for name in ("azimuth", "elevation", "distance", "zoom")}}
    azimuth = math.radians(pose["azimuth"])
    elevation = math.radians(pose["elevation"])
    radius = pose["distance"]
    offset = Vector((
        radius * math.cos(elevation) * math.sin(azimuth),
        -radius * math.cos(elevation) * math.cos(azimuth),
        radius * math.sin(elevation),
    ))
    camera.location = TARGET + offset
    camera.rotation_euler = (-offset).to_track_quat('-Z', 'Y').to_euler('XYZ', camera.rotation_euler)
    # Screen zoom includes the dolly's magnification, so compensate the lens for the dolly.
    camera.data.lens = 50 * pose["zoom"] * radius / {CAMERA_DISTANCE}
    camera.keyframe_insert(data_path="location", frame=frame)
    camera.keyframe_insert(data_path="rotation_euler", frame=frame)
    camera.data.keyframe_insert(data_path="lens", frame=frame)

scene.frame_set(scene.frame_start)
'''


def build_ltx_workflow(image_name: str, size: tuple[int, int], seconds: float, prompt: str, job_id: str) -> dict:
    width, height = size
    nodes = {}

    def add(kind, **inputs):
        node_id = str(len(nodes) + 1)
        nodes[node_id] = {"class_type": kind, "inputs": inputs}
        return [node_id, 0]

    image = add("LoadImage", image=image_name)
    model = add("CheckpointLoaderSimple", ckpt_name="ltx-video-2b-v0.9.5.safetensors")
    vae = [model[0], 2]
    clip = add("CLIPLoader", clip_name="t5xxl_fp8_e4m3fn_scaled.safetensors", type="ltxv")
    positive = add("CLIPTextEncode", text=prompt, clip=clip)
    negative = add("CLIPTextEncode", text="flicker, artifacts, distorted face, warped shapes, sudden camera movement", clip=clip)
    video = add(
        "LTXVImgToVideo", positive=positive, negative=negative, vae=vae, image=image,
        width=width, height=height, length=8 * round(seconds * LIFE_FPS / 8) + 1, batch_size=1, strength=1.0,
    )
    conditioned = add("LTXVConditioning", positive=video, negative=[video[0], 1], frame_rate=LIFE_FPS)
    latent = [video[0], 2]
    sampler = add("KSamplerSelect", sampler_name="euler")
    sigmas = add("LTXVScheduler", steps=30, max_shift=2.05, base_shift=0.95, stretch=True, terminal=0.1, latent=latent)
    sampled = add(
        "SamplerCustom", model=model, add_noise=True, noise_seed=random.getrandbits(32), cfg=3,
        positive=conditioned, negative=[conditioned[0], 1], sampler=sampler, sigmas=sigmas, latent_image=latent,
    )
    decoded = add("VAEDecode", samples=sampled, vae=vae)
    output = add("CreateVideo", images=decoded, fps=LIFE_FPS)
    add("SaveVideo", video=output, filename_prefix=f"Froja/Animate/{job_id}", format="mp4", **{"format.codec": "h264"})
    return nodes


class Stopped(Exception):
    pass


class AnimationJob:
    def __init__(self, root: Path, mode: str):
        self.id = uuid.uuid4().hex
        self.folder = root / "animate" / self.id
        self.mode = mode
        self.cancel = threading.Event()
        self.status = "running"
        self.progress = "Starting animation…"
        self.error = None
        self.upscaler = None
        self.upscale_fallback = None

    def check_stop(self):
        if self.cancel.is_set():
            raise Stopped()

    def snapshot(self):
        url = f"/api/animate/{self.id}"
        return dict(
            status=self.status, progress=self.progress, error=self.error,
            video=f"{url}/animation.mp4" if self.status == "complete" else None,
            blender=f"{url}/blender.py" if self.status == "complete" and self.mode == "camera" else None,
            upscaler=self.upscaler, upscale_fallback=self.upscale_fallback,
        )


def get_job(job_id: str) -> AnimationJob | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def stop_job(job: AnimationJob):
    with _jobs_lock:
        if job.status == "running":
            job.progress = "Stopping animation…"
            job.cancel.set()


def start_job(root: Path, request: dict, run_life, run_real) -> AnimationJob | None:
    with _jobs_lock:
        if any(job.status == "running" for job in _jobs.values()):
            return None
        job = AnimationJob(root, request["mode"])
        _jobs[job.id] = job
        worker = threading.Thread(target=_run, args=(job, request, run_life, run_real), daemon=True)
        worker.start()
        return job


def _run(job, request, run_life, run_real):
    try:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg is required for Animate. Froja could not find it on PATH.")
        job.folder.mkdir(parents=True)
        if job.mode == "real":
            run_real(job, ffmpeg, request)
        else:
            source = open_image(request["image"])
            if job.mode == "camera":
                render_camera(job, ffmpeg, source, request)
            else:
                run_life(job, ffmpeg, source, request)
        with _jobs_lock:
            job.check_stop()
            job.progress = "Animation ready."
            job.status = "complete"
    except Stopped:
        with _jobs_lock:
            job.progress = "Animation stopped."
            job.status = "stopped"
    except Exception as exc:
        with _jobs_lock:
            job.error = str(exc)
            job.progress = "Animation failed."
            job.status = "failed"


def open_image(raw: bytes) -> Image.Image:
    with Image.open(io.BytesIO(raw)) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def scaled_size(size: tuple[int, int], long_side: int, multiple: int, minimum: int) -> tuple[int, int]:
    return tuple(max(minimum, round(d * long_side / max(size) / multiple) * multiple) for d in size)


def _ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def render_camera(job, ffmpeg, source, request):
    preset = request["preset"]
    keys = camera_path(preset, request["views"], request["seconds"])
    size = scaled_size(source.size, 1080, 2, 2)
    master = source.resize(size, Image.Resampling.LANCZOS)
    views = {
        angle: ImageOps.fit(open_image(raw), size, Image.Resampling.LANCZOS)
        for angle, raw in request["views"].items()
    }
    total = round(keys[-1]["t"] * CAMERA_FPS)
    times = [k["t"] for k in keys]

    def frames():
        for index in range(total):
            job.check_stop()
            if index % CAMERA_FPS == 0:
                job.progress = f"Rendering camera move… {index + 1}/{total} frames"
            if preset in ORBIT_PRESETS:
                t = index / CAMERA_FPS
                segment = bisect_right(times, t) - 1
                a, b = keys[segment:segment + 2]
                blend = _ease((t - a["t"]) / (b["t"] - a["t"]))
                first, second = views[a["azimuth"]], views[b["azimuth"] % 360]
                yield Image.blend(first, second, blend) if first is not second else first
            else:
                mix = _ease(index / (total - 1))
                start, end = keys
                zoom = start["zoom"] + (end["zoom"] - start["zoom"]) * mix
                w, h = size
                crop_w, crop_h = w / zoom, h / zoom
                left = (w - crop_w) / 2
                top = (h - crop_h) * (1 - mix if preset == "crane" else 0.5)
                yield master.resize(size, Image.Resampling.LANCZOS, (left, top, left + crop_w, top + crop_h))

    encode_frames(job, ffmpeg, size, CAMERA_FPS, frames())
    (job.folder / "camera_path.json").write_text(json.dumps(keys, indent=2) + "\n", encoding="utf-8", newline="\n")


def _ffmpeg(job, ffmpeg, args, frames=None):
    job.check_stop()
    with (job.folder / "ffmpeg.log").open("ab") as log:
        process = subprocess.Popen(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", *args],
            stdin=subprocess.PIPE if frames is not None else subprocess.DEVNULL,
            stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            if frames is not None:
                for frame in frames:
                    job.check_stop()
                    process.stdin.write(frame.tobytes())
                process.stdin.close()
            while process.poll() is None:
                if job.cancel.wait(0.1):
                    raise Stopped()
            if process.returncode:
                raise RuntimeError("FFmpeg could not process the animation. See ffmpeg.log in the output folder.")
        except BrokenPipeError as exc:
            raise RuntimeError("FFmpeg could not encode the animation. See ffmpeg.log in the output folder.") from exc
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()


def encode_frames(job, ffmpeg, size, fps, frames, lossless=False):
    width, height = size
    _ffmpeg(job, ffmpeg, [
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
        "-an", "-c:v", "libx264", "-preset", "veryfast" if lossless else "medium", "-crf", "0" if lossless else "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(job.folder / "animation.mp4"),
    ], frames)


def real_extract_args(source: Path, frame_pattern: Path) -> list[str]:
    return ["-i", str(source), "-map", "0:v:0", "-vf", f"fps={REAL_FPS}:start_time=0",
            "-threads", "2", str(frame_pattern)]


def extract_real_frames(job, ffmpeg, source):
    folder = job.folder / "h3-frames"
    folder.mkdir()
    _ffmpeg(job, ffmpeg, real_extract_args(source, folder / "%05d.png"))
    frames = sorted(folder.glob("*.png"))
    if not frames:
        raise RuntimeError("MiniMax H3 returned a video with no frames.")
    return frames


def real_encode_args(source: Path, output: Path, *, has_audio: bool, upscaled_frames: Path | None = None) -> list[str]:
    args = ["-i", str(source)]
    if upscaled_frames is not None:
        args += ["-framerate", str(REAL_FPS), "-i", str(upscaled_frames), "-map", "1:v:0"]
    else:
        args += ["-map", "0:v:0", "-vf", f"fps={REAL_FPS}:start_time=0,scale=iw*{REAL_SCALE}:ih*{REAL_SCALE}:flags=lanczos"]
    if has_audio:
        args += ["-map", "0:a:0", "-af", "loudnorm=I=-16:TP=-1.5,apad", "-c:a", "aac", "-b:a", "192k",
                 "-ar", "48000", "-shortest"]
    return args + ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                   "-movflags", "+faststart", str(output)]


def finish_real(job, ffmpeg, source, upscale):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("FFprobe is required for Real motion. Froja could not find it on PATH.")
    job.check_stop()
    audio = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(source)], capture_output=True, check=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        upscaled_frames = upscale(job, ffmpeg, source)
        job.upscaler = "RealESRGAN"
    except (OSError, RuntimeError, ValueError) as exc:
        job.check_stop()
        job.upscaler = "FFmpeg Lanczos"
        job.upscale_fallback = str(exc)
        upscaled_frames = None
    job.progress = f"Encoding 2× video with {job.upscaler} and preparing sound…" if audio.stdout.strip() else (
        f"Encoding 2× video with {job.upscaler}…"
    )
    _ffmpeg(job, ffmpeg, real_encode_args(source, job.folder / "animation.mp4",
                                        has_audio=bool(audio.stdout.strip()), upscaled_frames=upscaled_frames))


def finish_life(job, ffmpeg, source, raw_video, mask):
    original_video = job.folder / "ltx.mp4"
    original_video.write_bytes(raw_video)
    if mask is None:
        job.progress = "Preparing video for playback…"
        _ffmpeg(job, ffmpeg, ["-i", str(original_video), "-an", "-c:v", "libx264",
                              "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(job.folder / "animation.mp4")])
        return
    frames_dir = job.folder / "frames"
    frames_dir.mkdir()
    job.progress = "Extracting video frames…"
    _ffmpeg(job, ffmpeg, ["-i", str(original_video), "-threads", "2", str(frames_dir / "%05d.png")])
    frames = sorted(frames_dir.glob("*.png"))
    if not frames:
        raise RuntimeError("LTX returned a video with no frames.")
    size = scaled_size(source.size, min(1080, max(source.size)), 2, 2)
    source = source.resize(size, Image.Resampling.LANCZOS)
    binary = mask.resize(size, Image.Resampling.NEAREST).point(lambda value: 255 if value >= 128 else 0)
    if binary.getextrema() != (0, 255):
        raise RuntimeError("No usable subject outline was found. Try more specific protection words.")
    binary.save(job.folder / "protect-mask.png")
    # Keep a guard around the binary mask for 4:2:0 chroma sampling, then feather outward.
    solid = binary.filter(ImageFilter.MaxFilter(9))
    alpha = ImageChops.lighter(solid, solid.filter(ImageFilter.GaussianBlur(3)))

    def composited():
        for index, frame in enumerate(frames):
            job.check_stop()
            if index % LIFE_FPS == 0:
                job.progress = f"Compositing and encoding… {index + 1}/{len(frames)} frames"
            with Image.open(frame) as image:
                background = image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
            yield Image.composite(source, background, alpha)

    encode_frames(job, ffmpeg, size, LIFE_FPS, composited(), lossless=False)
