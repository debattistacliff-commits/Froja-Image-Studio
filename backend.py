from __future__ import annotations

import json
import base64
import io
import mimetypes
import os
import random
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
OUTPUTS = ROOT / "outputs"
LOGS = ROOT / "logs"
TRAINING_SESSION_FILE = ROOT / "data" / "training-session.json"
PINNED_LORAS_FILE = ROOT / "data" / "pinned-loras.json"
PINNED_CHECKPOINTS_FILE = ROOT / "data" / "pinned-checkpoints.json"


def load_local_config() -> dict:
    config_path = Path(os.environ.get("FROJA_CONFIG", ROOT / "config" / "config.local.json"))
    if not config_path.is_file():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8-sig"))  # also accepts files saved by Notepad/PowerShell with a BOM
    except Exception as exc:
        raise RuntimeError(f"Froja could not read {config_path}: {exc}") from exc


def configured_path(value: str | None, fallback: Path) -> Path:
    if not value:
        return fallback
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    return path if path.is_absolute() else ROOT / path


def venv_python(root: Path) -> Path:
    windows = root / ".venv" / "Scripts" / "python.exe"
    unix = root / ".venv" / "bin" / "python"
    return windows if os.name == "nt" else unix


def url_port(url: str, fallback: int) -> str:
    return str(urllib.parse.urlparse(url).port or fallback)


LOCAL_CONFIG = load_local_config()
MATERIAL_LIBRARY = configured_path(LOCAL_CONFIG.get("material_library"), ROOT / "materials" / "library")
COMFY_ROOT = configured_path(os.environ.get("FROJA_COMFY_ROOT") or LOCAL_CONFIG.get("comfy_root"), ROOT / "ComfyUI")
COMFY_PYTHON = configured_path(LOCAL_CONFIG.get("comfy_python"), venv_python(COMFY_ROOT))
COMFY_URL = os.environ.get("FROJA_COMFY_URL") or LOCAL_CONFIG.get("comfy_url", "http://127.0.0.1:9000")
EXTENSION_COMFY_URL = os.environ.get("FROJA_EXTENSION_COMFY_URL") or LOCAL_CONFIG.get("extension_comfy_url", "http://127.0.0.1:9001")
SENSENOVA_URL = os.environ.get("FROJA_SENSENOVA_URL") or LOCAL_CONFIG.get("sensenova_url", "http://127.0.0.1:8192")
SENSENOVA_MODEL_PATH = configured_path(os.environ.get("FROJA_SENSENOVA_MODEL_PATH") or LOCAL_CONFIG.get("sensenova_model_path"), COMFY_ROOT / "models" / "sensenova" / "SenseNova-U1.5-8B-MoT-Preview")
SENSENOVA_GGUF = os.environ.get("FROJA_SENSENOVA_GGUF") or LOCAL_CONFIG.get("sensenova_gguf", "SenseNova-U1.5-8B-MoT-Preview-Q4_0-v2.gguf")
KREA_FAST_MODEL = os.environ.get("FROJA_KREA_FAST_MODEL") or LOCAL_CONFIG.get("krea_fast_model", "krea2_turbo-Q4_K_S.gguf")
KREA_FAST_LORA = os.environ.get("FROJA_KREA_FAST_LORA") or LOCAL_CONFIG.get("krea_fast_lora", "krea2_turbo_4step_rank_64_lora_chk00026000_comfyui.safetensors")
KREA_FAST_CLIP = os.environ.get("FROJA_KREA_FAST_CLIP") or LOCAL_CONFIG.get("krea_fast_clip", "qwen3vl_4b_fp8_scaled.safetensors")
JOYAI_ROOT = configured_path(os.environ.get("FROJA_JOYAI_ROOT") or LOCAL_CONFIG.get("joyai_root"), ROOT / "ComfyUI_JoyAI")
JOYAI_PYTHON = venv_python(JOYAI_ROOT)
JOYAI_URL = os.environ.get("FROJA_JOYAI_URL") or LOCAL_CONFIG.get("joyai_url", "http://127.0.0.1:9002")
WANGP_URL = os.environ.get("FROJA_WANGP_URL") or LOCAL_CONFIG.get("wangp_url", "http://127.0.0.1:9010")
WANGP_ROOT = configured_path(os.environ.get("FROJA_WANGP_ROOT") or LOCAL_CONFIG.get("wangp_root"), ROOT / "private" / "WanGP")
WANGP_ENABLED = str(os.environ.get("FROJA_WANGP_ENABLED", LOCAL_CONFIG.get("wangp_enabled", False))).lower() in {"1", "true", "yes", "on"}
OLLAMA_URL = os.environ.get("FROJA_OLLAMA_URL") or LOCAL_CONFIG.get("ollama_url", "http://127.0.0.1:11434")
EXTRA_PATHS = configured_path(LOCAL_CONFIG.get("extra_model_paths_config"), ROOT / "config" / "comfy-extra-model-paths.yaml")
EXTENSIONS_DIR = ROOT / "extensions"
COMFY_OUTPUT = COMFY_ROOT / "output"

DEFAULT_MODEL_ROOTS = {
    "checkpoints": [COMFY_ROOT / "models" / "checkpoints", ROOT / "models" / "checkpoints"],
    "loras": [COMFY_ROOT / "models" / "loras", ROOT / "models" / "loras"],
    "vae": [COMFY_ROOT / "models" / "vae", ROOT / "models" / "vae"],
    "embeddings": [COMFY_ROOT / "models" / "embeddings", ROOT / "models" / "embeddings"],
}
configured_roots = LOCAL_CONFIG.get("model_roots", {})
MODEL_ROOTS = {
    # Always scan the active ComfyUI folders first.  Configured libraries are
    # additive rather than replacing them, so duplicate filenames resolve to
    # the model used by the running ComfyUI engine.
    kind: [*defaults, *[configured_path(value, ROOT / "models" / kind) for value in configured_roots.get(kind, [])]]
    for kind, defaults in DEFAULT_MODEL_ROOTS.items()
}
SPECIAL_DIFFUSION_ROOT = configured_path(
    LOCAL_CONFIG.get("diffusion_models_root"), COMFY_ROOT / "models" / "diffusion_models"
)
MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".gguf"}
PREVIEW_EXTENSIONS = [".preview.png", ".preview.jpeg", ".preview.jpg", ".png", ".jpg", ".jpeg", ".webp"]
model_cache: dict[str, list[dict]] = {}
cache_lock = threading.Lock()
request_log_lock = threading.Lock()
comfy_process: subprocess.Popen | None = None
comfy_start_error = ""
extension_comfy_process: subprocess.Popen | None = None
sensenova_process: subprocess.Popen | None = None
joyai_process: subprocess.Popen | None = None
llada_jobs: dict[str, dict] = {}
llada_jobs_lock = threading.Lock()


def llada_status() -> dict:
    model_dir = ROOT / "experiments" / "llada-models"
    names = [
        "LLaDA-Image-Turbo-INT8.safetensors",
        "LLaDA-Image-Turbo-text_encoder-Q4_K_M.gguf",
        "LLaDa_VAE.safetensors",
    ]
    files = {name: model_dir / name for name in names}
    installed = all(path.is_file() for path in files.values())
    return {
        "installed": installed,
        "model": "LLaDA-Image Turbo · INT8 + Q4",
        "files": [{"name": name, "size": path.stat().st_size if path.is_file() else 0} for name, path in files.items()],
        "experimental": True,
        "recommended_size": "512x512",
        "recommended_steps": 1,
    }


def run_llada_job(job_id: str, prompt: str, width: int, height: int, steps: int):
    output = (ROOT / "test-output" / f"llada_{job_id}.png").resolve()
    log_path = LOGS / f"llada-{job_id}.log"
    LOGS.mkdir(exist_ok=True)
    command = [
        str(COMFY_PYTHON), str(ROOT / "scripts" / "llada_smoke_test.py"),
        "--prompt", prompt, "--width", str(width), "--height", str(height),
        "--steps", str(steps), "--offload", "model_cpu_offload", "--output", str(output),
    ]
    try:
        with log_path.open("w", encoding="utf-8") as stream:
            process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=3600)
        if process.returncode != 0 or not output.is_file():
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
            raise RuntimeError(tail or f"LLaDA stopped with exit code {process.returncode}.")
        with llada_jobs_lock:
            llada_jobs[job_id].update(status="complete", output=str(output))
    except Exception as exc:
        with llada_jobs_lock:
            llada_jobs[job_id].update(status="failed", error=str(exc))


def read_json_body(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    return json.loads(handler.rfile.read(length) or b"{}")


def build_dataset_zip(payload: dict) -> bytes:
    """Build a LoRA-ready archive in memory; source images are never modified."""
    items = payload.get("items") or []
    if not isinstance(items, list) or not 1 <= len(items) <= 200:
        raise ValueError("Choose between 1 and 200 dataset images.")
    size = int(payload.get("size") or 0)
    if size not in {0, 512, 768, 1024}:
        raise ValueError("Dataset size must be original, 512, 768, or 1024 pixels.")
    crop = bool(payload.get("crop", True))
    trigger = re.sub(r"\s+", " ", str(payload.get("trigger", "")).strip())
    archive = io.BytesIO()
    manifest = {"format": "froja-lora-dataset-v1", "trigger": trigger, "size": size or "original", "crop": crop, "items": []}
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for index, item in enumerate(items, 1):
            data_url = str(item.get("image", ""))
            match = re.match(r"^data:image/(?:png|jpeg|jpg|webp);base64,(.+)$", data_url, re.I | re.S)
            if not match:
                raise ValueError(f"Image {index} is not a supported local image.")
            raw = base64.b64decode(match.group(1), validate=True)
            if len(raw) > 25 * 1024 * 1024:
                raise ValueError(f"Image {index} exceeds the 25 MB safety limit.")
            with Image.open(io.BytesIO(raw)) as opened:
                processed = ImageOps.exif_transpose(opened).convert("RGB")
                if size:
                    processed = ImageOps.fit(processed, (size, size), Image.Resampling.LANCZOS) if crop else processed.copy()
                    if not crop: processed.thumbnail((size, size), Image.Resampling.LANCZOS)
                output = io.BytesIO(); processed.save(output, "PNG", optimize=True); width, height = processed.size
            stem = f"{index:05d}"
            caption = re.sub(r"\s+", " ", str(item.get("caption", "")).strip())
            text = ", ".join(part for part in (trigger, caption) if part)
            bundle.writestr(f"images/{stem}.png", output.getvalue()); bundle.writestr(f"images/{stem}.txt", text + "\n")
            manifest["items"].append({"image": f"images/{stem}.png", "caption": f"images/{stem}.txt", "width": width, "height": height})
        bundle.writestr("dataset.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        bundle.writestr("README.txt", "Froja LoRA dataset\nEach PNG has a matching UTF-8 TXT caption. Original source images were not changed.\n")
    return archive.getvalue()

# ---------------------------------------------------------------------------
# System monitor: CPU, RAM, GPU (temperature, load, VRAM), drives, plus plain-language advice.
# ---------------------------------------------------------------------------
try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - psutil is optional
    psutil = None

_SYSTEM_CACHE: dict = {"at": 0.0, "data": None}
_BOARD_TEMP_CACHE: dict = {"at": 0.0, "value": None}


def _gpu_status() -> list[dict]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,fan.speed",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return []
    gpus = []
    for line in out.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue
        def num(v):
            try:
                return float(v)
            except ValueError:
                return None
        gpus.append({"name": parts[0], "temp": num(parts[1]), "load": num(parts[2]), "vram_used_mb": num(parts[3]),
                     "vram_total_mb": num(parts[4]), "power_w": num(parts[5]), "fan": num(parts[6])})
    return gpus


def _cpu_temperature() -> dict:
    """Real CPU package temperature from LibreHardwareMonitor's web server (if running), else the board sensor."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8085/data.json", timeout=0.8) as response:
            tree = json.loads(response.read())
        best = None
        stack = [tree]
        while stack:
            node = stack.pop()
            stack.extend(node.get("Children", []))
            text, value = str(node.get("Text", "")), str(node.get("Value", ""))
            if "°C" in value and ("CPU Package" in text or (best is None and "Core" in text and "Max" in text)):
                try:
                    best = float(value.replace("°C", "").replace(",", ".").strip())
                except ValueError:
                    pass
        if best is not None:
            return {"value": best, "source": "cpu"}
    except Exception:
        pass
    now = time.time()
    if now - _BOARD_TEMP_CACHE["at"] > 30:
        _BOARD_TEMP_CACHE["at"] = now
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "(Get-CimInstance Win32_PerfFormattedData_Counters_ThermalZoneInformation | Measure-Object Temperature -Maximum).Maximum"],
                                 capture_output=True, text=True, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            kelvin = float(out.stdout.strip())
            _BOARD_TEMP_CACHE["value"] = round(kelvin - 273.15, 1) if kelvin > 200 else None
        except Exception:
            _BOARD_TEMP_CACHE["value"] = None
    return {"value": _BOARD_TEMP_CACHE["value"], "source": "board" if _BOARD_TEMP_CACHE["value"] is not None else "none"}


def system_advice(data: dict) -> list[dict]:
    """Plain-language warnings for the person using Froja."""
    advice = []
    ram = data.get("ram") or {}
    if ram.get("percent", 0) >= 90:
        advice.append({"level": "warn", "text": f"Memory (RAM) is {ram['percent']:.0f}% full. Close other programs before loading big models, or they may fail to load."})
    for gpu in data.get("gpus", []):
        if gpu.get("temp") is not None and gpu["temp"] >= 83:
            advice.append({"level": "danger", "text": f"The graphics card is hot ({gpu['temp']:.0f}°C). Let it cool down, check the fans and airflow."})
        elif gpu.get("temp") is not None and gpu["temp"] >= 76:
            advice.append({"level": "warn", "text": f"The graphics card is warm ({gpu['temp']:.0f}°C). That is fine while generating; keep an eye on it."})
    cpu = data.get("cpu") or {}
    if cpu.get("temp_source") == "cpu" and cpu.get("temp") is not None and cpu["temp"] >= 90:
        advice.append({"level": "danger", "text": f"The CPU is very hot ({cpu['temp']:.0f}°C). Check the cooler."})
    for drive in data.get("drives", []):
        if drive["free_gb"] < 15 or drive["percent"] >= 95:
            advice.append({"level": "danger", "text": f"Drive {drive['name']} is almost full ({drive['free_gb']:.0f} GB free). New pictures, videos or models may fail to save."})
        elif drive["percent"] >= 88:
            advice.append({"level": "warn", "text": f"Drive {drive['name']} is getting full ({drive['free_gb']:.0f} GB free)."})
    if cpu.get("temp_source") != "cpu":
        advice.append({"level": "info", "text": "For the real CPU temperature, run LibreHardwareMonitor with its Remote Web Server on port 8085. Froja then reads it automatically."})
    return advice


def system_status() -> dict:
    now = time.time()
    if _SYSTEM_CACHE["data"] is not None and now - _SYSTEM_CACHE["at"] < 2:
        return _SYSTEM_CACHE["data"]
    data: dict = {"cpu": {}, "ram": {}, "gpus": _gpu_status(), "drives": []}
    temp = _cpu_temperature()
    data["cpu"]["temp"], data["cpu"]["temp_source"] = temp["value"], temp["source"]
    if psutil is not None:
        data["cpu"]["load"] = psutil.cpu_percent(interval=None)
        data["cpu"]["cores"] = psutil.cpu_count(logical=True)
        vm = psutil.virtual_memory()
        data["ram"] = {"used_gb": round(vm.used / 2**30, 1), "total_gb": round(vm.total / 2**30, 1), "percent": vm.percent}
        for part in psutil.disk_partitions(all=False):
            if "cdrom" in part.opts or not part.fstype:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except Exception:
                continue
            data["drives"].append({"name": part.mountpoint.rstrip("\\"), "free_gb": round(usage.free / 2**30, 1),
                                   "total_gb": round(usage.total / 2**30, 1), "percent": usage.percent})
    data["advice"] = system_advice(data)
    _SYSTEM_CACHE.update(at=now, data=data)
    return data


# ---------------------------------------------------------------------------
# Optional MiniMax H3 video engine (text/picture -> video with sound).
# Off by default. Started only for a job, stopped again afterwards, so a 12 GB PC stays light.
# Needs the ComfyUI-MiniMax-H3-Turbo custom node and the model files listed in MINIMAX_VIDEO_FILES.
# ---------------------------------------------------------------------------
MINIMAX_VIDEO_URL = LOCAL_CONFIG.get("minimax_video_url", "http://127.0.0.1:9020")
MINIMAX_VIDEO_FILES = {
    "video model": ("diffusion_models", "minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
    "text encoder": ("text_encoders", "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
    "video VAE": ("vae", "minimax_h3_video_vae_fp16.safetensors"),
    "audio VAE": ("vae", "minimax_h3_audio_vae_fp32.safetensors"),
    "turbo LoRA": ("loras", "minimax_h3_turbo_v4_step600_ema.safetensors"),
}
MINIMAX_SIZES = {  # ~0.2 MP on 12 GB; more on bigger cards
    "safe": {"16:9": (640, 352), "9:16": (352, 640), "1:1": (448, 448)},
    "good": {"16:9": (832, 480), "9:16": (480, 832), "1:1": (576, 576)},
    "best": {"16:9": (1024, 576), "9:16": (576, 1024), "1:1": (704, 704)},
}
minimax_video_process = None
minimax_jobs: dict = {}
minimax_lock = threading.Lock()


def minimax_video_enabled() -> bool:
    return str(load_local_config().get("minimax_video_enabled", False)).lower() in {"1", "true", "yes", "on"}


def set_minimax_video_enabled(enabled: bool) -> None:
    config_path = Path(os.environ.get("FROJA_CONFIG", ROOT / "config" / "config.local.json"))
    data = load_local_config()
    data["minimax_video_enabled"] = bool(enabled)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def minimax_gpu_tier(vram_gb) -> dict:
    """What a graphics card can do with MiniMax H3 video, in plain words."""
    if not vram_gb:
        return {"tier": "unknown", "label": "Graphics card not detected", "max_seconds": 0, "supported": False}
    if vram_gb >= 22:
        return {"tier": "best", "label": f"Recommended on your {vram_gb:.0f} GB card", "max_seconds": 5, "supported": True}
    if vram_gb >= 15.5:
        return {"tier": "good", "label": f"Works well on your {vram_gb:.0f} GB card", "max_seconds": 4, "supported": True}
    if vram_gb >= 11.5:
        return {"tier": "safe", "label": f"Safe mode on your {vram_gb:.0f} GB card: small and slow (about 7 minutes for 3 seconds)", "max_seconds": 3, "supported": True}
    return {"tier": "none", "label": f"Not supported on a {vram_gb:.0f} GB card (12 GB or more needed)", "max_seconds": 0, "supported": False}


def minimax_frames(seconds: float) -> int:
    """MiniMax H3 needs 17k+5 frames at 24 fps."""
    k = max(1, round((seconds * 24 - 5) / 17))
    return 17 * k + 5


def minimax_missing_files() -> list:
    models = COMFY_ROOT / "models"
    missing = [label for label, (folder, name) in MINIMAX_VIDEO_FILES.items() if not (models / folder / name).exists()]
    if not (COMFY_ROOT / "custom_nodes" / "ComfyUI-MiniMax-H3-Turbo").exists():
        missing.append("ComfyUI-MiniMax-H3-Turbo custom node")
    return missing


def minimax_request(path: str, data=None, timeout=10):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(MINIMAX_VIDEO_URL + path, data=body, headers={"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


def minimax_ready() -> bool:
    try:
        minimax_request("/system_stats", timeout=2)
        return True
    except Exception:
        return False


def start_minimax_engine() -> bool:
    global minimax_video_process
    if minimax_ready():
        return True
    if not COMFY_PYTHON.exists():
        return False
    LOGS.mkdir(exist_ok=True)
    stdout = open(LOGS / "minimax-video.log", "a", encoding="utf-8")
    stderr = open(LOGS / "minimax-video-error.log", "a", encoding="utf-8")
    args = [str(COMFY_PYTHON), str(COMFY_ROOT / "main.py"), "--listen", "127.0.0.1", "--port", url_port(MINIMAX_VIDEO_URL, 9020),
            "--disable-all-custom-nodes", "--whitelist-custom-nodes", "ComfyUI-GGUF", "ComfyUI-MiniMax-H3-Turbo",
            "--preview-method", "none"]
    if EXTRA_PATHS.exists():
        args += ["--extra-model-paths-config", str(EXTRA_PATHS)]
    minimax_video_process = subprocess.Popen(args, cwd=COMFY_ROOT, stdout=stdout, stderr=stderr,
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(150):
        if minimax_ready():
            return True
        if minimax_video_process.poll() is not None:
            return False
        time.sleep(2)
    return False


def stop_minimax_engine() -> None:
    global minimax_video_process
    if minimax_video_process and minimax_video_process.poll() is None:
        minimax_video_process.terminate()
        try:
            minimax_video_process.wait(timeout=20)
        except Exception:
            minimax_video_process.kill()
    minimax_video_process = None


def minimax_status() -> dict:
    gpus = _gpu_status()
    vram = (gpus[0]["vram_total_mb"] or 0) / 1024 if gpus else None
    missing = minimax_missing_files()
    return {"enabled": minimax_video_enabled(), "installed": not missing, "missing": missing,
            "running": minimax_ready(), "gpu": gpus[0]["name"] if gpus else None, **minimax_gpu_tier(vram),
            "busy": any(job["status"] == "running" for job in minimax_jobs.values())}


def minimax_workflow(prompt: str, width: int, height: int, frames: int, image_name, seed: int, prefix: str) -> dict:
    i2v = {"clip": ["3", 0], "vae": ["4", 0], "prompt": prompt, "width": width, "height": height, "length": frames}
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": MINIMAX_VIDEO_FILES["video model"][1], "weight_dtype": "default"}},
        "2": {"class_type": "MiniMaxH3TurboLoRA", "inputs": {"model": ["1", 0], "lora_name": MINIMAX_VIDEO_FILES["turbo LoRA"][1], "strength": 1.0, "low_vram": True}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": MINIMAX_VIDEO_FILES["text encoder"][1], "type": "minimax", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": MINIMAX_VIDEO_FILES["video VAE"][1]}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": MINIMAX_VIDEO_FILES["audio VAE"][1]}},
        "8": {"class_type": "MiniMaxH3ImageToVideo", "inputs": i2v},
        "9": {"class_type": "BasicGuider", "inputs": {"model": ["2", 0], "conditioning": ["8", 0]}},
        "10": {"class_type": "BasicScheduler", "inputs": {"model": ["2", 0], "scheduler": "simple", "steps": 6, "denoise": 1.0}},
        "11": {"class_type": "MiniMaxH3TurboSampler", "inputs": {}},
        "12": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["12", 0], "guider": ["9", 0], "sampler": ["11", 0], "sigmas": ["10", 0], "latent_image": ["8", 1]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["4", 0]}},
        "15": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["13", 0], "vae": ["5", 0]}},
        "16": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "audio": ["15", 0], "fps": 24}},
        "17": {"class_type": "SaveVideo", "inputs": {"video": ["16", 0], "filename_prefix": prefix, "format": "auto", "codec": "auto"}},
    }
    if image_name:
        wf["6"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
        i2v["first_frame"] = ["6", 0]
    return wf


def _minimax_save_source(data_url: str, job_id: str, width: int, height: int) -> str:
    match = re.match(r"^data:image/(?:png|jpeg|jpg|webp);base64,(.+)$", data_url or "", re.I | re.S)
    if not match:
        raise ValueError("Choose a starting picture (PNG, JPEG or WebP).")
    with Image.open(io.BytesIO(base64.b64decode(match.group(1)))) as opened:
        picture = ImageOps.fit(ImageOps.exif_transpose(opened).convert("RGB"), (width, height), Image.Resampling.LANCZOS)
    name = f"froja_minimax_{job_id}.png"
    (COMFY_ROOT / "input").mkdir(parents=True, exist_ok=True)
    picture.save(COMFY_ROOT / "input" / name)
    return name


def _minimax_run(job_id: str, payload: dict) -> None:
    job = minimax_jobs[job_id]
    try:
        job.update(phase="Freeing memory from the picture engines", progress=0.02)
        release_engine_memory("main", "extension", "joyai", "sensenova", "ollama")
        job.update(phase="Starting the video engine", progress=0.05)
        if not start_minimax_engine():
            raise RuntimeError("The MiniMax video engine could not start. See logs/minimax-video-error.log.")
        if job["status"] == "cancelled":
            return
        status = minimax_status()
        sizes = MINIMAX_SIZES.get(status["tier"], MINIMAX_SIZES["safe"])
        aspect = str(payload.get("aspect", "16:9"))
        if aspect not in sizes:  # "original": follow the starting picture's shape
            aspect = "16:9"
            match = re.match(r"^data:image/[a-z]+;base64,(.+)$", str(payload.get("source", "")), re.I | re.S)
            if payload.get("mode") == "image" and match:
                with Image.open(io.BytesIO(base64.b64decode(match.group(1)))) as probe:
                    ratio = probe.width / max(1, probe.height)
                aspect = "16:9" if ratio > 1.3 else "9:16" if ratio < 0.77 else "1:1"
        width, height = sizes[aspect]
        seconds = min(float(payload.get("seconds") or status["max_seconds"] or 3), float(status["max_seconds"] or 3))
        frames = minimax_frames(seconds)
        image_name = None
        if payload.get("mode") == "image":
            image_name = _minimax_save_source(str(payload.get("source", "")), job_id, width, height)
        prompt = str(payload.get("prompt", "")).strip()
        if payload.get("audio"):
            prompt += f" Sound: {str(payload['audio']).strip()}"
        wf = minimax_workflow(prompt, width, height, frames, image_name, random.randint(1, 2**31), f"video/Froja_MiniMax_{job_id}")
        result = minimax_request("/prompt", {"prompt": wf, "client_id": "froja-minimax"}, timeout=60)
        if "prompt_id" not in result:
            raise RuntimeError(f"The video recipe was rejected: {str(result)[:300]}")
        job.update(prompt_id=result["prompt_id"], phase="Generating video and sound", width=width, height=height, frames=frames)
        expected = 150 + frames * (5.0 if status["tier"] == "safe" else 2.5)
        start = time.time()
        while True:
            time.sleep(3)
            if job["status"] == "cancelled":
                return
            history = minimax_request(f"/history/{result['prompt_id']}", timeout=10).get(result["prompt_id"])
            if not history:
                job["progress"] = min(0.95, 0.08 + (time.time() - start) / expected * 0.87)
                continue
            messages = history.get("status", {}).get("messages", [])
            errors = [m[1] for m in messages if m and m[0] == "execution_error"]
            if errors:
                raise RuntimeError(str(errors[0].get("exception_message", "Video generation failed."))[:400])
            for node in history.get("outputs", {}).values():
                for key in ("images", "videos", "gifs"):
                    for item in node.get(key, []):
                        source = COMFY_ROOT / "output" / item.get("subfolder", "") / item["filename"]
                        if source.suffix.lower() in {".mp4", ".webm", ".mov"} and source.exists():
                            target_dir = OUTPUTS / "minimax-video"
                            target_dir.mkdir(parents=True, exist_ok=True)
                            target = target_dir / f"{job_id}{source.suffix.lower()}"
                            shutil.copyfile(source, target)
                            job.update(status="complete", phase="Complete", progress=1.0, file=str(target),
                                       video_url=f"/api/minimax-video/files/{job_id}", seconds_taken=round(time.time() - job["started"]))
                            return
            raise RuntimeError("The engine finished but no video file was found.")
    except Exception as exc:
        job.update(status="failed", phase="Failed", error=str(exc))
    finally:
        if not any(j["status"] == "running" for k, j in minimax_jobs.items() if k != job_id):
            stop_minimax_engine()  # give the memory back to the picture engines


def start_minimax_job(payload: dict) -> dict:
    status = minimax_status()
    if not status["enabled"]:
        raise PermissionError("MiniMax H3 video is switched off. Switch it on in the Video Studio first.")
    if status["missing"]:
        raise FileNotFoundError("MiniMax H3 video is not installed. Missing: " + ", ".join(status["missing"]))
    if not status["supported"]:
        raise RuntimeError(status["label"])
    if not str(payload.get("prompt", "")).strip():
        raise ValueError("Describe the video you want to create.")
    with minimax_lock:
        if status["busy"]:
            raise RuntimeError("A MiniMax video is already being made. Only one at a time keeps your computer safe.")
        job_id = "mm-" + uuid.uuid4().hex[:12]
        minimax_jobs[job_id] = {"status": "running", "phase": "Queued", "progress": 0.0, "started": time.time()}
    threading.Thread(target=_minimax_run, args=(job_id, payload), daemon=True).start()
    return {"job_id": job_id}


def cancel_minimax_job(job_id: str) -> dict:
    job = minimax_jobs.get(job_id)
    if not job:
        return {"error": "Unknown job"}
    job.update(status="cancelled", phase="Cancelled")
    try:
        minimax_request("/interrupt", {}, timeout=5)
    except Exception:
        pass
    return {"ok": True}


PBR_TECHNICAL_MAPS = {"ao", "arm", "disp", "displacement", "rough", "roughness", "nor", "normal", "gl", "dx",
                      "metal", "metallic", "metalness", "height", "bump", "spec", "specular", "mask", "opacity", "orm"}
PBR_AMBIGUOUS_WORDS = {"metal", "metallic", "rough", "height", "mask"}  # also real material names ("brushed metal")
PBR_COLOUR_MAPS = {"diff", "diffuse", "albedo", "basecolor", "basecolour", "col", "color", "colour"}


def material_display_name(stem: str) -> str | None:
    """Readable name for a material image, or None when it is a technical PBR map (AO, roughness, normal...)."""
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)  # GothicCommode -> Gothic Commode
    words = [w for w in re.split(r"[_\-\s]+", spaced) if w]
    tagged = False
    while words and re.fullmatch(r"\d+k", words[-1].lower()):
        words.pop()  # resolution tag such as 4k
        tagged = True
    if len(words) > 1 and words[-1].lower() in {"gl", "dx"}:
        words.pop()  # nor_gl / nor_dx
    last = words[-1].lower() if words else ""
    if len(words) > 1 and last in PBR_TECHNICAL_MAPS and (tagged or last not in PBR_AMBIGUOUS_WORDS):
        return None
    if len(words) > 1 and words[-1].lower() in PBR_COLOUR_MAPS:
        words.pop()
    return " ".join(w if w.isupper() else w.capitalize() for w in words) or stem


def scan_material_library() -> dict:
    MATERIAL_LIBRARY.mkdir(parents=True, exist_ok=True)
    items = []
    seen = set()
    for path in sorted(MATERIAL_LIBRARY.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        relative = path.relative_to(MATERIAL_LIBRARY).as_posix()
        metadata = {}
        sidecar = path.with_suffix(".json")
        if sidecar.is_file():
            try:
                metadata = json.loads(sidecar.read_text(encoding="utf-8"))
            except Exception:
                metadata = {}
        clean = material_display_name(path.stem)
        if clean is None and not metadata.get("name"):
            continue  # technical texture map, not a material to show
        name = str(metadata.get("name") or clean)
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        prompt = str(metadata.get("prompt") or f"realistic {name.lower()} material, preserve its colour, texture, surface finish and weathering")
        items.append({"name": name, "prompt": prompt, "source": str(metadata.get("source") or "Local material library"), "relative": relative, "preview": "/api/material-image?path=" + urllib.parse.quote(relative)})
    return {"folder": str(MATERIAL_LIBRARY), "items": items}


def open_material_library() -> dict:
    MATERIAL_LIBRARY.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.Popen(["explorer.exe", str(MATERIAL_LIBRARY)], close_fds=True)
    elif shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", str(MATERIAL_LIBRARY)], close_fds=True)
    return {"ok": True, "folder": str(MATERIAL_LIBRARY)}

def load_training_session() -> dict:
    try:
        return json.loads(TRAINING_SESSION_FILE.read_text(encoding="utf-8")) if TRAINING_SESSION_FILE.is_file() else {"session": "", "results": []}
    except Exception:
        return {"session": "", "results": []}


def save_training_session(payload: dict) -> dict:
    results = payload.get("results") or []
    if not isinstance(results, list) or len(results) > 24:
        raise ValueError("Training sessions support up to 24 reviewed images.")
    clean = []
    for item in results:
        image = str(item.get("image", ""))
        if not (image.startswith("/api/comfy-image?") or image.startswith("data:image/")):
            raise ValueError("Training session contains an unsupported image reference.")
        clean.append({key: item.get(key, "") for key in ("id", "image", "name", "position", "environment", "prompt", "approved")})
    record = {"session": str(payload.get("session", "My_Training_Set_001"))[:100], "concept": str(payload.get("concept", ""))[:4000], "type": str(payload.get("type", "Character"))[:30], "results": clean, "updated": time.time()}
    TRAINING_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRAINING_SESSION_FILE.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "count": len(clean), "session": record["session"]}

def open_generated_output(image_url: str) -> dict:
    """Open the fixed ComfyUI output tree and select the requested generated image when possible."""
    target = None
    parsed = urllib.parse.urlparse(image_url)
    if parsed.path == "/api/comfy-image":
        query = urllib.parse.parse_qs(parsed.query)
        filename = Path(query.get("filename", [""])[0]).name
        subfolder = query.get("subfolder", [""])[0].replace("\\", "/").strip("/")
        candidate = (COMFY_OUTPUT / subfolder / filename).resolve()
        output_root = COMFY_OUTPUT.resolve()
        if filename and (candidate == output_root or output_root in candidate.parents) and candidate.is_file():
            target = candidate
    COMFY_OUTPUT.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        if target:
            subprocess.Popen(["explorer.exe", f"/select,{target}"], close_fds=True)
        else:
            subprocess.Popen(["explorer.exe", str(COMFY_OUTPUT)], close_fds=True)
    elif shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", str(target.parent if target else COMFY_OUTPUT)], close_fds=True)
    return {"ok": True, "selected": bool(target), "folder": str(COMFY_OUTPUT), "file": str(target or "")}


def json_response(handler: SimpleHTTPRequestHandler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def comfy_request(path: str, data: dict | None = None, timeout=10):
    encoded = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        COMFY_URL + path,
        data=encoded,
        headers={"Content-Type": "application/json"} if encoded else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(raw or "{}")
        except json.JSONDecodeError:
            details = {}
        messages = []
        for node in details.get("node_errors", {}).values():
            for error in node.get("errors", []):
                message = str(error.get("details") or error.get("message") or "").strip()
                if message and message not in messages:
                    messages.append(message)
        summary = "; ".join(messages) or details.get("error", {}).get("message") or raw.strip() or str(exc)
        raise RuntimeError(f"ComfyUI rejected the workflow: {summary}") from exc

def extension_comfy_request(path: str, data: dict | None = None, timeout=15):
    encoded = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        EXTENSION_COMFY_URL + path,
        data=encoded,
        headers={"Content-Type": "application/json"} if encoded else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


def sensenova_request(path: str, data: dict | None = None, timeout=30):
    encoded = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        SENSENOVA_URL + path,
        data=encoded,
        headers={"Content-Type": "application/json"} if encoded else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


def sensenova_ready() -> bool:
    try:
        sensenova_request("/system_stats", timeout=2)
        return True
    except Exception:
        return False


def krea_fast_status() -> dict:
    model_path = COMFY_ROOT / "models" / "diffusion_models" / KREA_FAST_MODEL
    lora_path = COMFY_ROOT / "models" / "loras" / KREA_FAST_LORA
    clip_path = COMFY_ROOT / "models" / "text_encoders" / KREA_FAST_CLIP
    vae_path = COMFY_ROOT / "models" / "vae" / "qwen_image_vae.safetensors"
    files = {"model": model_path, "lora": lora_path, "text_encoder": clip_path, "vae": vae_path}
    return {
        "ready": comfy_ready(),
        "installed": all(path.is_file() for path in files.values()),
        "experimental": True,
        "model": "Krea 2 Turbo Q4 · Distilled 4-Step",
        "checkpoint": KREA_FAST_MODEL,
        "lora": KREA_FAST_LORA,
        "files": {
            name: {"found": path.is_file(), "size": path.stat().st_size if path.is_file() else 0}
            for name, path in files.items()
        },
    }


def build_krea_fast_workflow(payload: dict) -> dict:
    prompt = re.sub(r"\s+", " ", str(payload.get("prompt") or "").strip())
    if not prompt:
        raise ValueError("Write a prompt before generating.")
    width = max(512, min(1280, int(payload.get("width") or 768)))
    height = max(512, min(1280, int(payload.get("height") or 768)))
    width -= width % 16
    height -= height % 16
    seed = int(payload.get("seed", -1))
    if seed < 0:
        seed = random.randrange(0, 2**63 - 1)
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": KREA_FAST_MODEL}},
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["1", 0], "lora_name": KREA_FAST_LORA, "strength_model": 1.0,
        }},
        "3": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": KREA_FAST_CLIP, "type": "krea2", "device": "default",
        }},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["3", 0]}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {
            "width": width, "height": height, "batch_size": 1,
        }},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["2", 0], "seed": seed, "steps": 4, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
            "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0],
        }},
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["8", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {
            "filename_prefix": "Froja/KreaFast4Step", "images": ["9", 0],
        }},
    }


def sensenova_status() -> dict:
    gguf_path = COMFY_ROOT / "models" / "gguf" / SENSENOVA_GGUF
    node_path = COMFY_ROOT / "custom_nodes" / "ComfyUI-SenseNova-U1"
    return {
        "ready": sensenova_ready(),
        "installed": SENSENOVA_MODEL_PATH.is_dir() and gguf_path.is_file() and node_path.is_dir(),
        "model": "SenseNova U1.5 8B MoT Preview Q4_0 v2",
        "model_path": str(SENSENOVA_MODEL_PATH),
        "gguf": str(gguf_path),
        "gguf_size": gguf_path.stat().st_size if gguf_path.is_file() else 0,
        "experimental": True,
        "minimum_resolution": "2048x2048",
    }


def start_sensenova() -> bool:
    global sensenova_process
    if sensenova_ready():
        return True
    status = sensenova_status()
    if not status["installed"] or not COMFY_PYTHON.exists():
        return False
    LOGS.mkdir(exist_ok=True)
    stdout = open(LOGS / "sensenova-comfy.log", "a", encoding="utf-8")
    stderr = open(LOGS / "sensenova-comfy-error.log", "a", encoding="utf-8")
    args = [
        str(COMFY_PYTHON), str(COMFY_ROOT / "main.py"),
        "--listen", "127.0.0.1", "--port", url_port(SENSENOVA_URL, 8192),
        "--disable-all-custom-nodes",
        "--whitelist-custom-nodes", "ComfyUI-GGUF", "ComfyUI-SenseNova-U1",
    ]
    if EXTRA_PATHS.is_file():
        args.extend(["--extra-model-paths-config", str(EXTRA_PATHS)])
    sensenova_process = subprocess.Popen(args, cwd=COMFY_ROOT, stdout=stdout, stderr=stderr)
    for _ in range(120):
        if sensenova_ready():
            return True
        if sensenova_process.poll() is not None:
            return False
        time.sleep(1)
    return False


def build_sensenova_workflow(payload: dict) -> dict:
    prompt = re.sub(r"\s+", " ", str(payload.get("prompt", "")).strip())
    if not prompt:
        raise ValueError("Write a prompt before generating.")
    profiles = {"smoke": 1, "draft": 8, "quality": 24}
    profile = str(payload.get("profile", "draft"))
    steps = profiles.get(profile, 8)
    allowed_resolutions = {"2048x2048|1:1", "2304x1728|4:3", "1728x2304|3:4", "2560x1440|16:9", "1440x2560|9:16"}
    resolution = str(payload.get("resolution", "2048x2048|1:1"))
    if resolution not in allowed_resolutions:
        resolution = "2048x2048|1:1"
    seed = int(payload.get("seed", -1))
    if seed < 0:
        seed = random.randint(0, 2**31 - 1)
    return {
        "1": {"class_type": "SenseNovaU1LocalLoader", "inputs": {
            "model_path": str(SENSENOVA_MODEL_PATH), "sensenova_u1_src": "", "device": "cuda",
            "dtype": "bfloat16", "attn_backend": "sdpa", "device_map": "none", "max_memory": "",
            "vram_mode": "balanced", "gguf_checkpoint": SENSENOVA_GGUF,
            "fast_vram_fraction": "0.9", "fast_vram_headroom_gib": "2.0",
            "fast_activation_reserve_gib": "4.0", "fast_vram_budget_gib": "0.0",
        }},
        "2": {"class_type": "SenseNovaU1LocalTextToImage", "inputs": {
            "u1_model": ["1", 0], "prompt": prompt, "resolution": resolution,
            "cfg_scale": 4.0, "cfg_norm": "none", "timestep_shift": 3.0,
            "cfg_interval_start": 0.0, "cfg_interval_end": 1.0, "num_steps": steps,
            "batch_size": 1, "seed": seed, "think_mode": bool(payload.get("think_mode", False)),
        }},
        "3": {"class_type": "SaveImage", "inputs": {
            "images": ["2", 0], "filename_prefix": f"Froja/SenseNova/sensenova_{profile}",
        }},
    }

def joyai_request(path: str, data: dict | None = None, timeout=30):
    encoded = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        JOYAI_URL + path,
        data=encoded,
        headers={"Content-Type": "application/json"} if encoded else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


def wangp_request(path: str, data: dict | None = None, timeout=15):
    """Talk to the optional private WanGP bridge without embedding WanGP in Froja."""
    encoded = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        WANGP_URL + path,
        data=encoded,
        headers={"Content-Type": "application/json"} if encoded else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


def wangp_status() -> dict:
    configured = WANGP_ENABLED and WANGP_ROOT.is_dir()
    if not configured:
        return {"enabled": WANGP_ENABLED, "configured": False, "online": False, "private": True}
    try:
        status = wangp_request("/status", timeout=2)
        return {**status, "enabled": True, "configured": True, "online": True, "private": True}
    except Exception:
        return {"enabled": True, "configured": True, "online": False, "private": True}


def save_joyai_upload(data_url: str) -> str:
    match = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", data_url, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Smart Edit needs a PNG, JPEG, or WebP image.")
    raw = base64.b64decode(match.group(2), validate=True)
    if len(raw) > 25 * 1024 * 1024:
        raise ValueError("The Smart Edit image is larger than 25 MB.")
    extension = "jpg" if match.group(1).lower() in ("jpeg", "jpg") else match.group(1).lower()
    relative = f"FrojaJoyAI/source-{uuid.uuid4().hex}.{extension}"
    destination = JOYAI_ROOT / "input" / Path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return relative.replace("\\", "/")


def sketch3d_status() -> dict:
    quality_model = COMFY_ROOT / "models" / "checkpoints" / "hunyuan_3d_v2.1.safetensors"
    mini_model = COMFY_ROOT / "models" / "checkpoints" / "hunyuan3d-dit-v2_fp16.safetensors"
    tripo_node = COMFY_ROOT / "custom_nodes" / "ComfyUI-Flowty-TripoSR"
    tripo_model = COMFY_ROOT / "models" / "checkpoints" / "model.ckpt"
    selected = quality_model if quality_model.is_file() else mini_model
    ready = selected.is_file()
    return {
        "ready": ready,
        "engine": "Hunyuan3D 2.1 Quality" if ready else "Hunyuan3D setup required",
        "model": f"{selected.name} | {selected.stat().st_size / 1073741824:.1f} GB" if ready else "Hunyuan3D model not installed",
        "model_name": selected.name if ready else "",
        "quality_engine": ready,
        "fallback_ready": tripo_node.is_dir() and tripo_model.is_file(),
        "fallback_engine": "TripoSR",
        "exports": ["GLB", "OBJ fallback"],
        "vram_profile": "12 GB safe shape generation",
    }


def build_sketch3d_mesh_workflow(payload: dict) -> dict:
    status = sketch3d_status()
    if not status["ready"]:
        raise RuntimeError("The local Hunyuan3D quality mesh model is not installed completely.")
    source = save_face_upload(str(payload.get("source_image", "")), "sketch3d")
    resolution = max(1024, min(4096, int(payload.get("latent_resolution", 3072))))
    octree = max(128, min(384, int(payload.get("octree_resolution", 256))))
    seed = int(payload.get("seed", -1))
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": source}},
        "2": {"class_type": "ImageOnlyCheckpointLoader", "inputs": {"ckpt_name": status["model_name"]}},
        "3": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["2", 0], "shift": 1.0}},
        "4": {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": ["2", 1], "image": ["1", 0], "crop": "none"}},
        "5": {"class_type": "Hunyuan3Dv2Conditioning", "inputs": {"clip_vision_output": ["4", 0]}},
        "6": {"class_type": "EmptyLatentHunyuan3Dv2", "inputs": {"resolution": resolution, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["3", 0], "seed": seed, "steps": 30, "cfg": 5.0, "sampler_name": "euler", "scheduler": "normal", "positive": ["5", 0], "negative": ["5", 1], "latent_image": ["6", 0], "denoise": 1.0}},
        "8": {"class_type": "VAEDecodeHunyuan3D", "inputs": {"samples": ["7", 0], "vae": ["2", 2], "num_chunks": 8000, "octree_resolution": octree}},
        "9": {"class_type": "VoxelToMesh", "inputs": {"voxel": ["8", 0], "algorithm": "surface net", "threshold": 0.6}},
        "10": {"class_type": "SaveGLB", "inputs": {"mesh": ["9", 0], "filename_prefix": "Froja/Sketch3D/Hunyuan3D"}},
    }

def build_joyai_workflow(payload: dict) -> dict:
    source = save_joyai_upload(str(payload.get("source_image", "")))
    instruction = str(payload.get("instruction", "")).strip()
    if not instruction:
        raise ValueError("Describe the change you want JoyAI to make.")
    negative = str(payload.get("negative_prompt", "")).strip()
    steps = max(4, min(40, int(payload.get("steps", 20))))
    seed = int(payload.get("seed", -1))
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": source}},
        "3": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "joyai_image_edit_int8_convrot.safetensors", "weight_dtype": "default",
        }},
        "4": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "qwen3vl_8b_joyimage_edit_int8_convrot.safetensors", "type": "joyimage", "device": "cpu",
        }},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "6": {"class_type": "TextEncodeJoyImageEdit", "inputs": {
            "clip": ["4", 0], "prompt": instruction, "vae": ["5", 0], "images": {"image1": ["1", 0]},
        }},
        "7": {"class_type": "TextEncodeJoyImageEdit", "inputs": {
            "clip": ["4", 0], "prompt": negative, "vae": ["5", 0], "images": {"image1": ["1", 0]},
        }},
        "8": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "9": {"class_type": "CFGNorm", "inputs": {"model": ["3", 0], "strength": 1.0, "pre_cfg": True}},
        "10": {"class_type": "KSampler", "inputs": {
            "model": ["9", 0], "seed": seed, "steps": steps, "cfg": 4.0,
            "sampler_name": "euler", "scheduler": "normal", "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["8", 0], "denoise": 1.0,
        }},
        "11": {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["5", 0]}},
        "12": {"class_type": "SaveImage", "inputs": {
            "filename_prefix": "Froja/JoyAI/smart-edit", "images": ["11", 0],
        }},
    }


def save_face_upload(data_url: str, label: str) -> str:
    match = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", data_url, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError(f"{label} must be a PNG, JPEG, or WebP image.")
    raw = base64.b64decode(match.group(2), validate=True)
    if len(raw) > 25 * 1024 * 1024:
        raise ValueError(f"{label} is larger than 25 MB.")
    extension = "jpg" if match.group(1).lower() in ("jpeg", "jpg") else match.group(1).lower()
    relative = f"FrojaFace/{label.lower()}-{uuid.uuid4().hex}.{extension}"
    destination = COMFY_ROOT / "input" / Path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return relative.replace("\\", "/")


def build_face_swap_workflow(payload: dict) -> dict:
    source = save_face_upload(str(payload.get("source_image", "")), "source")
    target = save_face_upload(str(payload.get("target_image", "")), "target")
    mode = str(payload.get("mode", "exact"))
    face_count = max(1, min(4, int(payload.get("face_count", 1))))
    mapping = str(payload.get("mapping", "same"))
    source_start = max(0, int(payload.get("source_face", 0)))
    target_start = max(0, int(payload.get("target_face", 0)))
    source_index = ",".join(str(source_start if mapping == "same" else source_start + i) for i in range(face_count))
    target_index = ",".join(str(target_start + i) for i in range(face_count))
    restoration = str(payload.get("restoration", "codeformer-v0.1.0.pth"))
    allowed_restoration = {"none", "codeformer-v0.1.0.pth", "GFPGANv1.3.pth", "GFPGANv1.4.pth", "GPEN-BFR-512.onnx"}
    if restoration not in allowed_restoration:
        restoration = "codeformer-v0.1.0.pth"
    visibility = max(0.1, min(1.0, float(payload.get("visibility", 0.85))))
    if mode == "pose":
        return {
            "1": {"class_type": "LoadImage", "inputs": {"image": source}},
            "2": {"class_type": "LoadImage", "inputs": {"image": target}},
            "3": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "juggernautXL_ragnarokBy_1659952.safetensors"}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 1], "text": "photorealistic portrait, preserve the target pose, head angle, expression, lighting, hair, clothing and background; apply the reference person's facial identity naturally"}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 1], "text": "distorted face, duplicate face, extra person, changed pose, changed background, plastic skin, blur"}},
            "6": {"class_type": "InstantIDModelLoader", "inputs": {"instantid_file": "ip-adapter.bin"}},
            "7": {"class_type": "InstantIDFaceAnalysis", "inputs": {"provider": "CUDA"}},
            "8": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": "instantid\\diffusion_pytorch_model.safetensors"}},
            "9": {"class_type": "ApplyInstantID", "inputs": {"instantid": ["6", 0], "insightface": ["7", 0], "control_net": ["8", 0], "image": ["1", 0], "image_kps": ["2", 0], "model": ["3", 0], "positive": ["4", 0], "negative": ["5", 0], "weight": 0.82, "start_at": 0.0, "end_at": 0.9}},
            "10": {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["3", 2]}},
            "11": {"class_type": "KSampler", "inputs": {"model": ["9", 0], "seed": random.randint(0, 2**32 - 1), "steps": 24, "cfg": 5.0, "sampler_name": "dpmpp_2m_sde", "scheduler": "karras", "positive": ["9", 1], "negative": ["9", 2], "latent_image": ["10", 0], "denoise": 0.38}},
            "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 2]}},
            "13": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/FaceStudioPose", "images": ["12", 0]}},
        }
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": source}},
        "2": {"class_type": "LoadImage", "inputs": {"image": target}},
        "3": {"class_type": "ReActorFaceSwap", "inputs": {
            "enabled": True,
            "input_image": ["2", 0],
            "source_image": ["1", 0],
            "swap_model": "inswapper_128.onnx",
            "facedetection": "retinaface_resnet50",
            "face_restore_model": restoration,
            "face_restore_visibility": visibility,
            "codeformer_weight": 0.5,
            "detect_gender_input": "no",
            "detect_gender_source": "no",
            "input_faces_index": target_index,
            "source_faces_index": source_index,
            "console_log_level": 1,
        }},
        "4": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/FaceStudio", "images": ["3", 0]}},
    }


def build_character_transform_workflow(payload: dict) -> dict:
    source = save_face_upload(str(payload.get("source_image", "")), "transform-source")
    reference_data = str(payload.get("reference_image", ""))
    environment_data = str(payload.get("environment_image", ""))
    reference = save_face_upload(reference_data, "transform-reference") if reference_data else ""
    environment = save_face_upload(environment_data, "transform-environment") if environment_data else ""
    instruction = str(payload.get("instruction", "")).strip()
    preserve = str(payload.get("preserve", "face identity, expression, camera framing, lighting, background and every element not explicitly requested to change")).strip()
    transparent = bool(payload.get("transparent", False))
    if not instruction:
        raise ValueError("Describe the transformation you want.")
    width = max(512, min(1536, int(payload.get("width", 1024)))) // 16 * 16
    height = max(512, min(1536, int(payload.get("height", 1024)))) // 16 * 16
    prompt = (
        "<image1> is the original image and primary edit target. "
        + ("<image2> is the body, pose, clothing, face, object, or visual reference to integrate. " if reference else "")
        + ("<image3> is the environment or background reference to integrate naturally. " if environment else "")
        + f"Transformation: {instruction}. Preserve exactly: {preserve}. "
        + ("Return an RGBA PNG with a true transparent alpha background. " if transparent else "")
        + "Create one coherent finished image, not a collage or reference sheet. Match perspective, anatomy, scale, contact, shadows, lighting and material interaction. Change only what the transformation requires."
    )
    nodes = {
        "1": {"class_type": "LoadImage", "inputs": {"image": source}},
        "4": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default"}},
        "5": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_8b_int8_convrot.safetensors", "type": "qwen_image", "device": "default"}},
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
        "7": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["5", 0], "vae": ["6", 0], "prompt": prompt, "negative_prompt": "", "resolution": max(width, height), "images.image_1": ["1", 0]}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "seed": random.randint(0, 2**32 - 1), "steps": 25, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["7", 2], "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["6", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/QwenImage21Edit", "images": ["9", 0]}},
    }
    if reference:
        nodes["2"] = {"class_type": "LoadImage", "inputs": {"image": reference}}
        nodes["7"]["inputs"]["images.image_2"] = ["2", 0]
    if environment:
        nodes["3"] = {"class_type": "LoadImage", "inputs": {"image": environment}}
        nodes["7"]["inputs"]["images.image_3"] = ["3", 0]
    return nodes


def build_image_tool_workflow(payload: dict) -> dict:
    mode = str(payload.get("mode", "img2img"))
    if mode not in {"img2img", "inpaint", "controlnet", "krea2-reference"}:
        raise ValueError("Unknown image tool mode.")
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("Enter a prompt for this image workflow.")
    source = save_face_upload(str(payload.get("source_image", "")), mode)
    width = max(256, min(2048, int(payload.get("width", 768))))
    height = max(256, min(2048, int(payload.get("height", 768))))
    seed = int(payload.get("seed", -1))
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)
    strength = max(0.0, min(1.0, float(payload.get("strength", 0.65))))
    if mode == "krea2-reference":
        checkpoint = str(payload.get("checkpoint", "")).strip()
        if not checkpoint:
            raise ValueError("Select a Krea-2 checkpoint before running this workflow.")
        checkpoint_lower = checkpoint.lower()
        if not any(tag in checkpoint_lower for tag in ("krea", "darkbeast")):
            raise ValueError("Krea-2 Reference Edit requires a Krea-2 checkpoint.")
        model_loader = "UnetLoaderGGUF" if checkpoint_lower.endswith(".gguf") else "CheckpointLoaderSimple"
        # Ostris' edit nodes attach the source image both to Qwen3-VL
        # conditioning and as reference latents.  This is the pipeline the
        # bundled Krea detail-enhancer LoRA was trained against.
        edit_lora = "krea-detail-enhancer-exp.safetensors"
        workflow = {
            "1": {"class_type": model_loader, "inputs": ({"unet_name": checkpoint} if model_loader == "UnetLoaderGGUF" else {"ckpt_name": checkpoint})},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
            "4": {"class_type": "LoadImage", "inputs": {"image": source}},
            "5": {"class_type": "TextEncodeKrea2OstrisEdit", "inputs": {"clip": ["2", 0], "prompt": prompt, "vae": ["3", 0], "image1": ["4", 0]}},
            "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
            "7": {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"conditioning": ["5", 0], "reference_latents_method": "index_timestep_zero"}},
            "8": {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"conditioning": ["6", 0], "reference_latents_method": "index_timestep_zero"}},
            "9": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "20": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": edit_lora, "strength_model": strength}},
        }
        model_ref = ["20", 0]
        next_id = 21
        for lora in payload.get("loras", [])[:8]:
            if not lora.get("name") or Path(str(lora["name"])).name.lower() == edit_lora.lower():
                continue
            node_id = str(next_id)
            workflow[node_id] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model_ref, "lora_name": lora["name"], "strength_model": float(lora.get("strength", 0.8))}}
            model_ref = [node_id, 0]
            next_id += 1
        workflow.update({
            "10": {"class_type": "Krea2OstrisEditModelPatch", "inputs": {"model": model_ref, "kv_cache": False}},
            "30": {"class_type": "KSampler", "inputs": {"model": ["10", 0], "seed": seed, "steps": 10, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["7", 0], "negative": ["8", 0], "latent_image": ["9", 0], "denoise": 1.0}},
            "31": {"class_type": "VAEDecode", "inputs": {"samples": ["30", 0], "vae": ["3", 0]}},
            "32": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/Krea2Reference", "images": ["31", 0]}},
        })
        return workflow

    workflow = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3_4b_fp8_scaled.safetensors", "type": "lumina2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "10": {"class_type": "LoadImage", "inputs": {"image": source}},
    }
    model_ref = ["1", 0]
    next_id = 20
    for lora in payload.get("loras", [])[:8]:
        if not lora.get("name"):
            continue
        node_id = str(next_id)
        workflow[node_id] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": model_ref, "lora_name": lora["name"], "strength_model": float(lora.get("strength", 0.8)),
        }}
        model_ref = [node_id, 0]
        next_id += 1
    if mode == "controlnet":
        control_mode = str(payload.get("control_mode", "canny"))
        workflow["11"] = {"class_type": "ImageScale", "inputs": {"image": ["10", 0], "upscale_method": "lanczos", "width": width, "height": height, "crop": "center"}}
        if control_mode == "depth":
            workflow["12"] = {"class_type": "DepthAnythingV2Preprocessor", "inputs": {"image": ["11", 0], "ckpt_name": "depth_anything_v2_vitl.pth", "resolution": 768}}
        elif control_mode == "pose":
            workflow["12"] = {"class_type": "DWPreprocessor", "inputs": {"image": ["11", 0], "detect_hand": "enable", "detect_body": "enable", "detect_face": "enable", "resolution": 768, "bbox_detector": "yolox_l.onnx", "pose_estimator": "dw-ll_ucoco_384_bs5.torchscript.pt", "scale_stick_for_xinsr_cn": "disable"}}
        else:
            workflow["12"] = {"class_type": "Canny", "inputs": {"image": ["11", 0], "low_threshold": 0.3, "high_threshold": 0.4}}
        workflow["13"] = {"class_type": "ModelPatchLoader", "inputs": {"name": "Z-Image-Turbo-Fun-Controlnet-Union.safetensors"}}
        workflow["14"] = {"class_type": "QwenImageDiffsynthControlnet", "inputs": {"model": model_ref, "model_patch": ["13", 0], "vae": ["3", 0], "image": ["12", 0], "strength": max(0.0, min(2.0, float(payload.get("control_strength", 1.0))))}}
        workflow["15"] = {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["14", 0], "shift": 3.0}}
        workflow["16"] = {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}}
        latent_ref = ["16", 0]
        model_ref = ["15", 0]
        denoise = 1.0
    else:
        if mode == "inpaint":
            mask = save_face_upload(str(payload.get("mask_image", "")), "mask")
            workflow["11"] = {"class_type": "LoadImageMask", "inputs": {"image": mask, "channel": "red"}}
            workflow["12"] = {"class_type": "VAEEncodeForInpaint", "inputs": {"pixels": ["10", 0], "vae": ["3", 0], "mask": ["11", 0], "grow_mask_by": 8}}
        else:
            workflow["11"] = {"class_type": "ImageScale", "inputs": {"image": ["10", 0], "upscale_method": "lanczos", "width": width, "height": height, "crop": "center"}}
            workflow["12"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["11", 0], "vae": ["3", 0]}}
        sampling_id = str(next_id)
        workflow[sampling_id] = {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": model_ref, "shift": 3.0}}
        model_ref = [sampling_id, 0]
        latent_ref = ["12", 0]
        denoise = strength
    workflow["30"] = {"class_type": "KSampler", "inputs": {"model": model_ref, "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "res_multistep", "scheduler": "simple", "positive": ["4", 0], "negative": ["5", 0], "latent_image": latent_ref, "denoise": denoise}}
    workflow["31"] = {"class_type": "VAEDecode", "inputs": {"samples": ["30", 0], "vae": ["3", 0]}}
    workflow["32"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": f"Froja/{mode}", "images": ["31", 0]}}
    return workflow


# ---------------------------------------------------------------------------
# Relight light stage: lights placed in 3D around the subject -> a light map for IC-Light.
# azimuth: 0 = from the camera (front), 90 = from the right, 180 = from behind, 270 = from the left.
# elevation: -30 (from below) .. 85 (from above).
# ---------------------------------------------------------------------------
def _hex_rgb(value: str) -> tuple:
    value = str(value or "#ffffff").strip().lower()
    if not re.fullmatch(r"#[0-9a-f]{6}", value):
        value = "#ffffff"
    return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))


def clean_lights(lights) -> list:
    """Validate the lights sent by the Relight studio (max 3)."""
    out = []
    for item in (lights if isinstance(lights, list) else [])[:3]:
        if not isinstance(item, dict) or not item.get("on", True):
            continue
        out.append({
            "name": str(item.get("name", "Light"))[:20],
            "azimuth": float(item.get("azimuth", 270)) % 360,
            "elevation": max(-30.0, min(85.0, float(item.get("elevation", 25)))),
            "intensity": max(0.0, min(100.0, float(item.get("intensity", 80)))),
            "color": item.get("color", "#ffffff"),
            "soft": str(item.get("softness", "soft")) != "hard",
        })
    return out


def render_light_map(lights, ambient: float = 15, width: int = 512, height: int = 512) -> "Image.Image":
    """Paint where the light comes from, as IC-Light expects: bright where the light falls, dark elsewhere."""
    import numpy as np
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    u, v = (xx + 0.5) / width, (yy + 0.5) / height
    rgb = np.zeros((height, width, 3), dtype=np.float32)
    rgb += max(0.0, min(100.0, float(ambient))) / 100 * 0.35
    cu, cv = u - 0.5, v - 0.5
    radial = np.sqrt(cu ** 2 + cv ** 2)
    for light in clean_lights(lights):
        az, el = np.radians(light["azimuth"]), np.radians(light["elevation"])
        lx, ly, lz = np.sin(az) * np.cos(el), np.sin(el), np.cos(az) * np.cos(el)
        strength = light["intensity"] / 100
        color = np.array(_hex_rgb(light["color"]), dtype=np.float32)
        sx, sy = 0.5 + 0.48 * lx, 0.5 - 0.48 * ly                      # where the light lands on the picture
        dist = np.sqrt((u - sx) ** 2 + (v - sy) ** 2)
        radius, sharp = (0.62, 1.4) if light["soft"] else (0.38, 3.2)
        pool = np.exp(-((dist / radius) ** 2) * sharp)
        front = max(lz, 0.0)
        glow = pool * (0.55 + 0.45 * front) + front * 0.25            # front lights also lift the whole picture
        if lz < 0:                                                   # behind the subject: a rim on the light's side
            side = np.clip((cu * lx - cv * ly) / (radial + 1e-6), 0, 1) ** 0.7
            rim = np.clip((radial - 0.22) / 0.28, 0, 1) * side
            glow = glow * (1 + lz) + rim * (-lz) * 1.2
        rgb += glow[..., None] * color[None, None, :] * strength
    rgb = np.clip(rgb, 0, 1) ** (1 / 1.1)
    return Image.fromarray((rgb * 255).astype("uint8"))


def light_map_data_url(lights, ambient: float = 15, size: int = 384) -> str:
    buffer = io.BytesIO()
    render_light_map(lights, ambient, size, size).save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def colour_name(value: str) -> str:
    """Plain colour words for a light, e.g. '#ff4fd8' -> 'pink neon'."""
    import colorsys
    r, g, b = _hex_rgb(value)
    h, l, sat = colorsys.rgb_to_hls(r, g, b)
    if sat < 0.25 or l > 0.92:
        return "warm white" if r > b + 0.06 else "cool white" if b > r + 0.06 else "white"
    deg = h * 360
    for limit, name in ((15, "red"), (45, "warm orange"), (65, "golden yellow"), (160, "green"), (200, "cyan"),
                        (255, "blue"), (290, "purple"), (335, "pink neon"), (360, "red")):
        if deg < limit:
            return name
    return "white"


def describe_lights(lights) -> str:
    """Words for the prompt, so the text agrees with the light map."""
    words = []
    for light in clean_lights(lights):
        az = light["azimuth"]
        side = ("front" if az < 30 or az > 330 else "right" if az < 150 else "behind" if az < 210 else "left")
        height = "high above" if light["elevation"] > 50 else "below" if light["elevation"] < -5 else "eye level"
        kind = "soft" if light["soft"] else "hard"
        words.append(f"{kind} {colour_name(light['color'])} {light['name'].lower()} light from the {side} at {height}")
    return ", ".join(words)


def build_relight_workflow(payload: dict) -> dict:
    source = save_face_upload(str(payload.get("source_image", "")), "relight")
    prompt = str(payload.get("prompt", "cinematic natural lighting, realistic illumination")).strip()
    negative = str(payload.get("negative_prompt", "flat lighting, blown highlights, crushed shadows, low quality, distorted")).strip()
    width = max(256, min(1024, int(payload.get("width", 768))))
    height = max(256, min(1024, int(payload.get("height", 768))))
    seed = int(payload.get("seed", -1))
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)
    strength = max(0.35, min(1.0, float(payload.get("strength", 0.8))))
    brightness = max(10, min(100, int(payload.get("brightness", 50))))
    softness = str(payload.get("softness", "soft")).lower()
    if softness not in {"soft", "hard"}:
        softness = "soft"
    color = str(payload.get("color", "#ffffff")).lower()
    if not re.fullmatch(r"#[0-9a-f]{6}", color):
        color = "#ffffff"
    prompt = f"{prompt}, {softness} directional light, light color {color}, brightness {brightness} percent"
    strength = max(0.25, min(1.0, strength * (0.65 + brightness / 200)))
    lights = clean_lights(payload.get("lights"))
    if lights:
        prompt = f"{prompt}, {describe_lights(lights)}"
    lighting = {
        "left": "Left Light", "right": "Right Light", "top": "Top Light",
        "bottom": "Bottom Light", "center": "Circle Light", "front": "Circle Light",
        "back": "None", "ambient": "None",
    }.get(str(payload.get("direction", "left")).lower(), "Left Light")
    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "DreamShaper_8_pruned.safetensors"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": source}},
        "3": {"class_type": "ImageScale", "inputs": {"image": ["2", 0], "upscale_method": "lanczos", "width": width, "height": height, "crop": "center"}},
        "4": {"class_type": "easy icLightApply", "inputs": {"mode": "Foreground", "model": ["1", 0], "image": ["3", 0], "vae": ["1", 2], "lighting": lighting, "source": "Ambient", "remove_bg": False}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "7": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 1], "vae": ["1", 2]}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "seed": seed, "steps": 24, "cfg": 2.0, "sampler_name": "euler", "scheduler": "normal", "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0], "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "ImageBlend", "inputs": {"image1": ["3", 0], "image2": ["9", 0], "blend_factor": strength, "blend_mode": "normal"}},
        "11": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/relight", "images": ["10", 0]}},
    }
    if lights:  # IC-Light starts from OUR light map: the light lands where it was placed in the light stage
        light_map = render_light_map(lights, float(payload.get("ambient", 15)), width, height)
        relative = f"FrojaFace/relight-lightmap-{uuid.uuid4().hex}.png"
        destination = COMFY_ROOT / "input" / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        light_map.save(destination)
        workflow["12"] = {"class_type": "LoadImage", "inputs": {"image": relative}}
        workflow["7"]["inputs"]["pixels"] = ["12", 0]
    return workflow


def build_repair_workflow(payload: dict) -> dict:
    source = save_face_upload(str(payload.get("source_image", "")), "repair")
    mode = str(payload.get("mode", "face")).lower()
    seed = int(payload.get("seed", -1))
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)
    denoise = max(0.15, min(0.75, float(payload.get("strength", 0.4))))
    if mode == "box":
        box = payload.get("box") or {}
        x = max(0.0, min(1.0, float(box.get("x", 0))))
        y = max(0.0, min(1.0, float(box.get("y", 0))))
        w = max(0.01, min(1.0 - x, float(box.get("w", 0))))
        h = max(0.01, min(1.0 - y, float(box.get("h", 0))))
        source_path = COMFY_ROOT / "input" / Path(source)
        with Image.open(source_path) as original:
            image_width, image_height = original.size
        left, top = round(x * image_width), round(y * image_height)
        right, bottom = round((x + w) * image_width), round((y + h) * image_height)
        mask = Image.new("L", (image_width, image_height), 0)
        ImageDraw.Draw(mask).rectangle((left, top, right, bottom), fill=255)
        mask_relative = f"FrojaFace/repair-mask-{uuid.uuid4().hex}.png"
        mask_path = COMFY_ROOT / "input" / Path(mask_relative)
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        mask.save(mask_path)
        prompt = str(payload.get("prompt", "repair the selected area naturally while preserving the surrounding image")).strip()
        negative = str(payload.get("negative_prompt", "deformed, disfigured, extra fingers, missing fingers, extra limbs, bad anatomy, distorted, low quality")).strip()
        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "DreamShaper_8_pruned.safetensors"}},
            "2": {"class_type": "LoadImage", "inputs": {"image": source}},
            "3": {"class_type": "LoadImageMask", "inputs": {"image": mask_relative, "channel": "red"}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
            "6": {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["6", 0], "mask": ["3", 0]}},
            "8": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": seed, "steps": 24, "cfg": 6.0, "sampler_name": "dpmpp_2m", "scheduler": "karras", "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["7", 0], "denoise": denoise}},
            "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
            "10": {"class_type": "FeatherMask", "inputs": {"mask": ["3", 0], "left": 16, "top": 16, "right": 16, "bottom": 16}},
            "11": {"class_type": "ImageCompositeMasked", "inputs": {"destination": ["2", 0], "source": ["9", 0], "x": 0, "y": 0, "resize_source": False, "mask": ["10", 0]}},
            "12": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/repair-box", "images": ["11", 0]}},
        }
    settings = {
        "face": ("bbox/face_yolov8m.pt", 512, 3.0, 10, "natural symmetrical face, detailed eyes, realistic skin, correct facial anatomy"),
        "hands": ("bbox/hand_yolov8s.pt", 640, 2.2, 18, "anatomically correct hands, five natural fingers on each hand, correct joints and grip"),
        "body": ("segm/person_yolov8m-seg.pt", 768, 1.25, 12, "anatomically correct human body, natural posture, balanced limbs, realistic proportions"),
    }
    if mode not in settings:
        raise ValueError("Choose face, hands, or body repair.")
    detector, guide_size, crop_factor, dilation, default_prompt = settings[mode]
    prompt = str(payload.get("prompt", default_prompt)).strip() or default_prompt
    negative = str(payload.get("negative_prompt", "deformed, disfigured, asymmetrical, extra fingers, missing fingers, fused fingers, extra limbs, bad anatomy, distorted face, low quality")).strip()
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "DreamShaper_8_pruned.safetensors"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": source}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "5": {"class_type": "UltralyticsDetectorProvider", "inputs": {"model_name": detector}},
        "6": {"class_type": "FaceDetailer", "inputs": {
            "image": ["2", 0], "model": ["1", 0], "clip": ["1", 1], "vae": ["1", 2],
            "guide_size": guide_size, "guide_size_for": True, "max_size": 1024,
            "seed": seed, "steps": 20, "cfg": 6.0, "sampler_name": "dpmpp_2m", "scheduler": "karras",
            "positive": ["3", 0], "negative": ["4", 0], "denoise": denoise,
            "feather": 12, "noise_mask": True, "force_inpaint": True,
            "bbox_threshold": 0.35, "bbox_dilation": dilation, "bbox_crop_factor": crop_factor,
            "sam_detection_hint": "center-1", "sam_dilation": 0, "sam_threshold": 0.93,
            "sam_bbox_expansion": 0, "sam_mask_hint_threshold": 0.7,
            "sam_mask_hint_use_negative": "False", "drop_size": 10,
            "bbox_detector": ["5", 0], "wildcard": "", "cycle": 1,
        }},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"Froja/repair-{mode}", "images": ["6", 0]}},
    }


def comfy_ready() -> bool:
    try:
        comfy_request("/system_stats", timeout=2)
        return True
    except Exception:
        return False


def local_port_available(host: str, port: int) -> bool:
    """Return whether Windows will allow a new local listener on this port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((host, port))
        return True
    except OSError:
        return False


def extension_comfy_ready() -> bool:
    try:
        extension_comfy_request("/system_stats", timeout=2)
        return True
    except Exception:
        return False


def engine_has_queued_work(requester) -> bool:
    """Return True while an isolated ComfyUI engine is running or holding queued work."""
    try:
        queue = requester("/queue", timeout=5)
        return bool(queue.get("queue_running") or queue.get("queue_pending"))
    except Exception:
        return False


def joyai_ready() -> bool:
    try:
        joyai_request("/system_stats", timeout=2)
        return True
    except Exception:
        return False


def unload_ollama_models() -> list[str]:
    """Ask Ollama to unload its models from the graphics card and RAM (it reloads them by itself when needed)."""
    unloaded = []
    for item in ollama_request("/api/ps", timeout=4).get("models", []):
        name = item.get("name") or item.get("model")
        if not name:
            continue
        try:
            ollama_request("/api/generate", {"model": name, "keep_alive": 0}, timeout=20)
            unloaded.append(name)
        except Exception:
            continue  # one stubborn model must not stop the others being released
    return unloaded


def release_engine_memory(*engines: str) -> None:
    """Best-effort VRAM handoff between Froja's isolated ComfyUI engines (and Ollama)."""
    requests = {
        "main": lambda: comfy_request("/free", {"unload_models": True, "free_memory": True}, timeout=15),
        "extension": lambda: extension_comfy_request("/free", {"unload_models": True, "free_memory": True}, timeout=15),
        "joyai": lambda: joyai_request("/free", {"unload_models": True, "free_memory": True}, timeout=15),
        "sensenova": lambda: sensenova_request("/free", {"unload_models": True, "free_memory": True}, timeout=15),
        "ollama": unload_ollama_models,
    }
    for engine in engines:
        try:
            requests[engine]()
        except Exception:
            # An engine that has not been started has no memory to release.
            pass


def start_joyai() -> bool:
    global joyai_process
    if joyai_ready():
        return True
    if not JOYAI_PYTHON.exists():
        return False
    LOGS.mkdir(exist_ok=True)
    stdout = open(LOGS / "joyai-comfy.log", "a", encoding="utf-8")
    stderr = open(LOGS / "joyai-comfy-error.log", "a", encoding="utf-8")
    joyai_process = subprocess.Popen([
        str(JOYAI_PYTHON), str(JOYAI_ROOT / "main.py"),
        "--listen", "127.0.0.1", "--port", url_port(JOYAI_URL, 9002), "--lowvram",
        "--cpu-vae", "--preview-method", "none", "--cache-none",
        "--disable-async-offload", "--disable-pinned-memory", "--fast-disk",
        "--reserve-vram", "1.5",
    ], cwd=JOYAI_ROOT, stdout=stdout, stderr=stderr)
    for _ in range(90):
        if joyai_ready():
            return True
        if joyai_process.poll() is not None:
            return False
        time.sleep(2)
    return False


def start_extension_comfy() -> bool:
    global extension_comfy_process
    if extension_comfy_ready():
        return True
    if not COMFY_PYTHON.exists():
        return False
    LOGS.mkdir(exist_ok=True)
    face_user = ROOT / "runtime" / "face-user"
    face_user.mkdir(parents=True, exist_ok=True)
    stdout = open(LOGS / "extensions-comfy.log", "a", encoding="utf-8")
    stderr = open(LOGS / "extensions-comfy-error.log", "a", encoding="utf-8")
    args = [
        str(COMFY_PYTHON), str(COMFY_ROOT / "main.py"),
        "--listen", "127.0.0.1", "--port", url_port(EXTENSION_COMFY_URL, 9001), "--lowvram",
        "--user-directory", str(face_user),
        "--database-url", "sqlite:///:memory:",
    ]
    if EXTRA_PATHS.is_file():
        args.extend(["--extra-model-paths-config", str(EXTRA_PATHS)])
    extension_comfy_process = subprocess.Popen(args, cwd=COMFY_ROOT, stdout=stdout, stderr=stderr)
    for _ in range(60):
        if extension_comfy_ready():
            return True
        if extension_comfy_process.poll() is not None:
            return False
        time.sleep(3)
    return False


def ollama_request(path: str, data: dict | None = None, timeout=180):
    encoded = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL + path,
        data=encoded,
        headers={"Content-Type": "application/json"} if encoded else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


def ollama_message_text(result: dict) -> str:
    """Read both classic and reasoning-model Ollama chat responses."""
    message = result.get("message", {}) if isinstance(result, dict) else {}
    content = str(message.get("content") or "").strip()
    if content:
        return content
    # Some multimodal/reasoning builds exhaust their answer budget while
    # placing the useful visual description in `thinking` instead.
    thinking = str(message.get("thinking") or "").strip()
    return re.sub(r"</?think>", "", thinking, flags=re.IGNORECASE).strip()


def extension_manifests() -> list[dict]:
    manifests = []
    if not EXTENSIONS_DIR.exists():
        return manifests
    for path in EXTENSIONS_DIR.glob("*/extension.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            item["folder"] = path.parent.name
            manifests.append(item)
        except Exception:
            continue
    return sorted(manifests, key=lambda item: item.get("name", ""))


def assist_prompt(payload: dict) -> dict:
    prompt = str(payload.get("prompt", "")).strip()
    mode = str(payload.get("mode", "enhance"))
    model = str(payload.get("model", "qwen3.5:4b"))
    if not prompt:
        raise ValueError("Write a short idea first, then ask Froja to develop it.")
    task = (
        "Rewrite the user's text as one polished image-generation prompt. Preserve every requested subject and any "
        "<lora:name:strength> tag. Add concrete composition, camera, lighting, materials, environment and mood details. "
        "Do not add headings, explanations, quotation marks, negative prompts, or model settings. Return only the prompt."
        if mode == "enhance" else
        "Turn the user's idea into one complete image-generation prompt. Preserve any <lora:name:strength> tag. "
        "Specify subject, action, setting, composition, camera viewpoint, lighting, materials, atmosphere and visual quality. "
        "Do not add headings, explanations, quotation marks, negative prompts, or model settings. Return only the prompt."
    )
    result = ollama_request("/api/chat", {
        "model": model,
        "stream": False,
        "think": False,
        "keep_alive": 0,
        "messages": [
            {"role": "system", "content": task},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.65, "num_predict": 420},
    })
    content = str(result.get("message", {}).get("content", "")).strip()
    content = re.sub(r"^```(?:text)?\s*|\s*```$", "", content, flags=re.IGNORECASE).strip()
    if not content:
        raise RuntimeError("Ollama returned an empty prompt.")
    return {"prompt": content, "model": model, "mode": mode}



def compose_reference_prompt(payload: dict) -> dict:
    intention = str(payload.get("intention", "")).strip()
    references = payload.get("references", [])
    model = str(payload.get("model", "qwen3.5:4b"))
    if not intention:
        raise ValueError("Describe what the references should become.")
    usable = []
    for index, item in enumerate(references if isinstance(references, list) else [], 1):
        if not isinstance(item, dict):
            continue
        description = str(item.get("description", "")).strip()
        role = str(item.get("role", f"Reference {index}")).strip()
        influence = int(item.get("influence", 70))
        if description:
            usable.append(f"REFERENCE {index} ROLE: {role}\nINFLUENCE: {influence}%\nVISIBLE CONTENT: {description}")
    if not usable:
        raise ValueError("Analyze at least one reference image first.")
    system = (
        "You are Froja's scene composition director. Build one precise image-generation prompt from independently analyzed "
        "visual references. Assign every reference only to its declared role. Explicitly describe spatial relationships, pose, "
        "body-to-furniture contact, scale, foreground/background placement, lighting integration and material application. "
        "The user intention is authoritative. Preserve character identity from the character reference. Never ask the model "
        "to reproduce a contact sheet, collage, reference board, labels, transparent checkerboard, separate panels, or pasted "
        "cut-outs. Return one fluent positive prompt only, followed by no commentary, headings, settings, or negative prompt."
    )
    content = "\n\n".join(usable) + "\n\nUSER INTENTION:\n" + intention
    result = ollama_request("/api/chat", {
        "model": model, "stream": False, "think": False, "keep_alive": "10m",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        "options": {"temperature": 0.3, "num_predict": 900},
    }, timeout=360)
    prompt = str(result.get("message", {}).get("content", "")).strip().strip('"')
    if not prompt:
        raise RuntimeError("Ollama returned an empty scene plan.")
    return {"prompt": prompt, "model": model, "references": len(usable)}


def read_image_metadata(payload: dict) -> dict:
    """Recover embedded Stable Diffusion/ComfyUI generation data without inference."""
    data_url = str(payload.get("image", ""))
    if not data_url or "," not in data_url:
        raise ValueError("Choose an image first.")
    header, encoded = data_url.split(",", 1)
    if not header.startswith("data:image/"):
        raise ValueError("Choose a PNG, JPEG, or WebP image.")
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) > 25 * 1024 * 1024:
        raise ValueError("The image is larger than 25 MB.")
    with Image.open(io.BytesIO(raw)) as opened:
        info = {str(k): v for k, v in opened.info.items() if isinstance(v, (str, int, float))}
        exif = opened.getexif()
        for tag in (270, 37510):
            value = exif.get(tag)
            if isinstance(value, bytes): value = value.decode("utf-8", "ignore").lstrip("ASCII\x00\x00\x00")
            if value: info.setdefault("description" if tag == 270 else "user_comment", str(value))
        width, height = opened.size
    result = {"found": False, "prompt": "", "negative": "", "model": "", "seed": "", "steps": "", "cfg": "", "sampler": "", "scheduler": "", "width": width, "height": height, "source": "none", "raw": ""}
    parameters = str(info.get("parameters") or info.get("Parameters") or info.get("user_comment") or info.get("description") or "").strip()
    if parameters:
        result.update({"found": True, "source": "Stable Diffusion parameters", "raw": parameters})
        positive, negative, settings = parameters, "", ""
        marker = "Negative prompt:"
        if marker in positive:
            positive, tail = positive.split(marker, 1)
            match = re.search(r"\nSteps:\s*", tail)
            if match: negative, settings = tail[:match.start()], tail[match.start()+1:]
            else: negative = tail
        else:
            match = re.search(r"\nSteps:\s*", positive)
            if match: positive, settings = positive[:match.start()], positive[match.start()+1:]
        result["prompt"] = positive.strip(); result["negative"] = negative.strip()
        pairs = dict((k.strip().lower(), v.strip()) for k, v in re.findall(r"(?:^|,)\s*([^:,]+):\s*([^,]+)", settings))
        result.update({"steps": pairs.get("steps", ""), "sampler": pairs.get("sampler", ""), "scheduler": pairs.get("schedule type", ""), "cfg": pairs.get("cfg scale", ""), "seed": pairs.get("seed", ""), "model": pairs.get("model", "")})
        size = pairs.get("size", "")
        if re.match(r"^\d+x\d+$", size): result["width"], result["height"] = map(int, size.split("x"))
        return result
    prompt_json = info.get("prompt")
    workflow_json = info.get("workflow")
    if prompt_json or workflow_json:
        result.update({"found": True, "source": "ComfyUI workflow", "raw": str(prompt_json or workflow_json)[:12000]})
        try:
            graph = json.loads(str(prompt_json or "{}"))
            for node in graph.values() if isinstance(graph, dict) else []:
                class_type = str(node.get("class_type", "")); inputs = node.get("inputs", {})
                if class_type in {"CLIPTextEncode", "CLIPTextEncodeFlux", "TextEncodeQwenImageEdit"} and inputs.get("text"):
                    text = str(inputs["text"])
                    if not result["prompt"]: result["prompt"] = text
                    elif not result["negative"]: result["negative"] = text
                if "Sampler" in class_type:
                    for source, target in (("seed","seed"),("steps","steps"),("cfg","cfg"),("sampler_name","sampler"),("scheduler","scheduler")):
                        if source in inputs: result[target] = str(inputs[source])
                if class_type == "CheckpointLoaderSimple": result["model"] = str(inputs.get("ckpt_name", ""))
                if class_type in {"UNETLoader", "UnetLoaderGGUF"}: result["model"] = str(inputs.get("unet_name", ""))
        except Exception: pass
        return result
    return result

def image_to_prompt(payload: dict) -> dict:
    data_url = str(payload.get("image", ""))
    model = str(payload.get("model", "qwen3-vl:4b"))
    detail = str(payload.get("detail", "balanced"))
    if not data_url or "," not in data_url:
        raise ValueError("Choose an image before asking Froja to describe it.")
    header, encoded = data_url.split(",", 1)
    if not header.startswith("data:image/"):
        raise ValueError("Choose a PNG, JPEG, or WebP image.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("The uploaded image could not be read.") from exc
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError("The image is larger than 20 MB. Resize it and try again.")
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            analysis_image = ImageOps.exif_transpose(opened).convert("RGB")
            # Large source images can consume the vision model's entire context
            # window before it has room to answer. Resize only the in-memory
            # analysis copy; the user's original file is never changed.
            analysis_image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            analysis_buffer = io.BytesIO()
            analysis_image.save(analysis_buffer, format="JPEG", quality=90, optimize=True)
            analysis_encoded = base64.b64encode(analysis_buffer.getvalue()).decode("ascii")
    except Exception as exc:
        raise ValueError("The uploaded image could not be decoded.") from exc
    focus = {
        "concise": "Keep the prompt concise but specific, around 70 to 110 words.",
        "balanced": "Create a complete prompt around 120 to 180 words.",
        "detailed": "Create a richly detailed prompt around 180 to 260 words.",
    }.get(detail, "Create a complete prompt around 120 to 180 words.")
    instruction = (
        "Study the supplied image and convert what is visibly present into one polished text-to-image generation prompt. "
        "Accurately describe the main subject, appearance, pose, expression, clothing, objects, environment, composition, "
        "camera angle and shot size, lens character, depth of field, lighting direction and quality, color palette, materials, "
        "mood, and visual medium. Preserve unusual details and spatial relationships. Do not guess a real person's identity, "
        "hidden facts, brand, artist, or model. Do not mention that you examined an image. Do not add a negative prompt, "
        "headings, commentary, quotation marks, or generation settings. Return only the reusable positive prompt. " + focus
    )
    result = ollama_request("/api/chat", {
        "model": model,
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "messages": [{"role": "user", "content": instruction, "images": [analysis_encoded]}],
        "options": {"temperature": 0.25, "num_predict": 650},
    }, timeout=360)
    visual_description = ollama_message_text(result)
    if not visual_description:
        raise RuntimeError("The vision model returned an empty description.")
    polish = ollama_request("/api/chat", {
        "model": "qwen3.5:4b",
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "messages": [
            {"role": "system", "content": (
                "Convert the supplied visual description into one fluent positive text-to-image prompt. Retain only visible, "
                "useful details. Organize it as subject and pose, clothing and objects, setting and composition, camera, lighting, "
                "palette, mood, medium and texture. Remove speculation, identity guesses, explanations, repetition and phrases such "
                "as 'the image depicts'. Do not add a negative prompt, headings, quotation marks, bullets, artist names, model names, "
                "settings or invented details. Return one paragraph only. " + focus
            )},
            {"role": "user", "content": visual_description},
        ],
        "options": {"temperature": 0.2, "num_predict": 500},
    }, timeout=240)
    content = ollama_message_text(polish)
    content = re.sub(r"^```(?:text)?\s*|\s*```$", "", content, flags=re.IGNORECASE).strip().strip('"')
    if not content:
        content = visual_description
    return {"prompt": content, "model": model, "writer": "qwen3.5:4b", "detail": detail}


def enhance_image(payload: dict) -> dict:
    data_url = str(payload.get("image", ""))
    if not data_url or "," not in data_url:
        raise ValueError("Choose an image before applying enhancements.")
    header, encoded = data_url.split(",", 1)
    if not header.startswith("data:image/"):
        raise ValueError("Choose a PNG, JPEG, or WebP image.")
    try:
        raw = base64.b64decode(encoded, validate=True)
        from io import BytesIO
        source = Image.open(BytesIO(raw))
        source = ImageOps.exif_transpose(source).convert("RGB")
    except Exception as exc:
        raise ValueError("The uploaded image could not be read.") from exc
    if len(raw) > 25 * 1024 * 1024:
        raise ValueError("The image is larger than 25 MB. Resize it and try again.")

    image = source
    denoise = max(0, min(100, int(payload.get("denoise", 0))))
    dust = max(0, min(100, int(payload.get("dust", 0))))
    sharpen = max(0, min(100, int(payload.get("sharpen", 20))))
    brightness = max(-50, min(50, int(payload.get("brightness", 0))))
    contrast = max(-50, min(50, int(payload.get("contrast", 0))))
    color = max(-50, min(50, int(payload.get("color", 0))))
    scale = max(1, min(4, int(payload.get("scale", 1))))

    if dust:
        cleaned = image.filter(ImageFilter.MedianFilter(size=3 if dust < 70 else 5))
        image = Image.blend(image, cleaned, dust / 130.0)
    if denoise:
        softened = image.filter(ImageFilter.GaussianBlur(radius=0.35 + denoise / 55.0))
        image = Image.blend(image, softened, denoise / 125.0)
    if brightness:
        image = ImageEnhance.Brightness(image).enhance(1.0 + brightness / 100.0)
    if contrast:
        image = ImageEnhance.Contrast(image).enhance(1.0 + contrast / 100.0)
    if color:
        image = ImageEnhance.Color(image).enhance(1.0 + color / 100.0)
    if sharpen:
        image = image.filter(ImageFilter.UnsharpMask(
            radius=0.8 + sharpen / 35.0,
            percent=60 + sharpen * 2,
            threshold=max(1, 8 - sharpen // 15),
        ))
    if scale > 1:
        target_w, target_h = image.width * scale, image.height * scale
        max_ratio = min(1.0, 4096 / max(target_w, target_h), (20_000_000 / (target_w * target_h)) ** 0.5)
        target_w = max(image.width, int(target_w * max_ratio))
        target_h = max(image.height, int(target_h * max_ratio))
        image = image.resize((target_w, target_h), Image.Resampling.LANCZOS)
        if sharpen:
            image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=65, threshold=3))

    output = BytesIO()
    image.save(output, format="JPEG", quality=95, subsampling=0, optimize=True)
    result = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    return {
        "image": result,
        "width": image.width,
        "height": image.height,
        "original_width": source.width,
        "original_height": source.height,
    }


def start_comfy() -> bool:
    global comfy_process, comfy_start_error, COMFY_URL
    comfy_start_error = ""
    if comfy_ready():
        return True
    if not COMFY_PYTHON.exists():
        comfy_start_error = f"ComfyUI Python was not found: {COMFY_PYTHON}"
        return False
    parsed = urllib.parse.urlparse(COMFY_URL)
    host = parsed.hostname or "127.0.0.1"
    configured_port = int(parsed.port or 8222)
    if not local_port_available(host, configured_port):
        # Avoid ranges commonly reserved by Windows/Hyper-V and VPN adapters.
        # A public VPN location never changes localhost routing.
        fallback = next((port for port in (8400, 8488, 8588, 8688, 8788, 8888) if local_port_available(host, port)), None)
        if fallback is None:
            comfy_start_error = "No safe local port is available for the ComfyUI image engine."
            return False
        COMFY_URL = f"http://{host}:{fallback}"
    LOGS.mkdir(exist_ok=True)
    stdout = open(LOGS / "comfy.log", "a", encoding="utf-8")
    stderr = open(LOGS / "comfy-error.log", "a", encoding="utf-8")
    args = [
        str(COMFY_PYTHON), str(COMFY_ROOT / "main.py"),
        "--listen", "127.0.0.1", "--port", url_port(COMFY_URL, 8222),
        "--disable-all-custom-nodes",
        "--whitelist-custom-nodes", "ComfyUI-GGUF",
    ]
    if EXTRA_PATHS.is_file():
        args.extend(["--extra-model-paths-config", str(EXTRA_PATHS)])
    try:
        comfy_process = subprocess.Popen(args, cwd=COMFY_ROOT, stdout=stdout, stderr=stderr)
    except Exception as exc:
        comfy_start_error = f"ComfyUI could not be launched: {exc}"
        return False
    for _ in range(90):
        if comfy_ready():
            return True
        if comfy_process.poll() is not None:
            comfy_start_error = f"ComfyUI exited during startup (code {comfy_process.returncode}). See logs/comfy-error.log."
            return False
        time.sleep(1)
    comfy_start_error = f"ComfyUI did not become ready at {COMFY_URL} within 90 seconds."
    return False


def find_preview(path: Path) -> str | None:
    base = path.with_suffix("")
    candidates = [Path(str(base) + ext) for ext in PREVIEW_EXTENSIONS]
    # Forge/Civitai helpers also save galleries as model_0.png, model_1.jpg,
    # etc. Use the first numbered image when no conventional sidecar exists.
    for extension in (".png", ".jpg", ".jpeg", ".webp"):
        candidates.append(Path(str(base) + "_0" + extension))
    for candidate in candidates:
        if candidate.exists():
            return urllib.parse.quote(str(candidate))
    return None


def safetensor_is_adapter(path: Path) -> bool:
    """Read only the safetensors header and identify LoRA/adapter files safely."""
    if path.suffix.lower() != ".safetensors":
        return False
    try:
        with path.open("rb") as stream:
            length = int.from_bytes(stream.read(8), "little")
            if length <= 0 or length > 32 * 1024 * 1024:
                return False
            header = json.loads(stream.read(length))
        metadata = header.get("__metadata__", {}) if isinstance(header, dict) else {}
        architecture_name = str(metadata.get("modelspec.architecture", "")).lower()
        if "lora" in architecture_name or "adapter" in architecture_name or metadata.get("ss_network_module"):
            return True
        keys = [str(key).lower() for key in header if key != "__metadata__"]
        sample = keys[:200]
        return bool(sample) and sum("lora_" in key or ".lora" in key for key in sample) >= min(4, len(sample))
    except Exception:
        return False

def safetensor_is_complete(path: Path) -> bool:
    """Reject truncated or malformed safetensors before they reach ComfyUI."""
    if path.suffix.lower() != ".safetensors":
        return True
    try:
        file_size = path.stat().st_size
        with path.open("rb") as stream:
            header_length = int.from_bytes(stream.read(8), "little")
            if header_length <= 0 or header_length > 32 * 1024 * 1024:
                return False
            header = json.loads(stream.read(header_length))
        data_end = 0
        for name, tensor in header.items():
            if name == "__metadata__":
                continue
            offsets = tensor.get("data_offsets") if isinstance(tensor, dict) else None
            if not isinstance(offsets, list) or len(offsets) != 2:
                return False
            start, end = int(offsets[0]), int(offsets[1])
            if start < 0 or end < start:
                return False
            data_end = max(data_end, end)
        return 8 + header_length + data_end <= file_size
    except Exception:
        return False

def model_is_auxiliary(path: Path) -> bool:
    """Reject auxiliary networks accidentally stored in checkpoint folders."""
    if path.resolve() == (COMFY_ROOT / "models" / "checkpoints" / "model.ckpt").resolve():
        return True
    name = path.name.lower().replace("-", "_")
    auxiliary_tokens = (
        "controlnet", "control_net", "control_lora", "t2i_adapter",
        "ipadapter", "ip_adapter", "clip_vision",
    )
    if any(token in name for token in auxiliary_tokens):
        return True
    if path.suffix.lower() != ".safetensors":
        return False
    try:
        with path.open("rb") as stream:
            length = int.from_bytes(stream.read(8), "little")
            if length <= 0 or length > 32 * 1024 * 1024:
                return False
            header = json.loads(stream.read(length))
        keys = [str(key).lower() for key in header if key != "__metadata__"][:800]
        return any(
            key.startswith("control_model.")
            or ".controlnet_" in key
            or key.startswith("controlnet.")
            for key in keys
        )
    except Exception:
        return False
def safetensor_architecture(path: Path) -> str | None:
    """Identify split diffusion models from tensor keys when filenames are ambiguous."""
    if path.suffix.lower() != ".safetensors":
        return None
    try:
        with path.open("rb") as stream:
            length = int.from_bytes(stream.read(8), "little")
            if length <= 0 or length > 32 * 1024 * 1024:
                return None
            header = json.loads(stream.read(length))
        metadata = header.get("__metadata__", {}) if isinstance(header, dict) else {}
        metadata_text = " ".join(str(value).lower() for value in metadata.values())
        keys = [str(key).lower() for key in header if key != "__metadata__"]
        sample = keys[:800]
        if any(tag in metadata_text for tag in ("z image", "z-image", "z_image", "zimage")):
            return "Z-Image"
        if any("cap_embedder" in key for key in sample) and any("context_refiner" in key for key in sample):
            return "Z-Image"
        if "flux" in str(metadata.get("modelspec.architecture", "")).lower():
            return "Flux"
        if any(".double_blocks." in key and (".img_attn." in key or ".txt_attn." in key) for key in sample):
            return "Flux"
        if '"type": "unetloader"' in metadata_text and any("double_blocks" in key for key in sample):
            return "Flux"
    except Exception:
        return None
    return None

def architecture(name: str) -> str:
    value = name.lower()
    if any(tag in value for tag in ("minimax_h3_image", "minimax-h3-image", "minimaxh3image")):
        return "MiniMax-H3-Image"
    if "moss_image" in value or "mossimage" in value or "moss-image" in value:
        return "MOSS-Image"
    if "ace_step" in value or "acestep" in value:
        return "ACE Audio"
    if "zimage" in value or "z_image" in value or "z-image" in value:
        return "Z-Image"
    if any(tag in value for tag in ("qwen_image_2.1", "qwen-image-2.1", "qwenimage2.1")):
        return "Qwen-Image-2.1"
    # DarkBeast is a Krea-2 derivative, but many published files omit
    # "krea" from their filename.  Treat it as Krea-2 so it receives the
    # required Qwen3-VL encoder and Qwen Image VAE rather than an SDXL graph.
    if "krea2" in value or "krea-2" in value or "krea_2" in value or "darkbeast" in value:
        return "Krea-2"
    if "mage_flow" in value or "mage-flow" in value:
        return "Mage-Flow"
    if any(tag in value for tag in ("flux-2-klein", "flux2-klein", "flux2klein")):
        # On this 12 GB installation only the Q4 GGUF variant passed the safe
        # loading criteria. Keep full safetensors, AIO and 9B files visible but
        # disabled instead of risking another hard process termination.
        return "Flux2-Klein" if value.endswith(".gguf") and "9b" not in value and "aio" not in value else "Flux2-Large"
    if "flux" in value:
        return "Flux"
    if "illustrious" in value or "pony" in value or "xl" in value:
        return "SDXL"
    if "qwen" in value:
        return "Qwen"
    return "Checkpoint"


def lora_metadata(path: Path) -> dict:
    candidates = [
        path.with_suffix(".json"),
        Path(str(path.with_suffix("")) + ".cm-info.json"),
        path.with_suffix(".txt"),
    ]
    triggers: list[str] = []
    base_model = None
    model_id = None
    version_id = None
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            if candidate.suffix.lower() == ".txt":
                text = candidate.read_text(encoding="utf-8", errors="ignore").strip()
                if text:
                    triggers.extend(part.strip() for part in text.split(",") if part.strip())
                continue
            data = json.loads(candidate.read_text(encoding="utf-8", errors="ignore"))
            lowered = {str(key).lower(): value for key, value in data.items()}
            raw = lowered.get("activation text") or lowered.get("trainedwords") or lowered.get("trigger_words") or lowered.get("trigger words")
            if isinstance(raw, list):
                triggers.extend(str(item).strip() for item in raw if str(item).strip())
            elif isinstance(raw, str) and raw.strip():
                triggers.extend(part.strip() for part in raw.split(",") if part.strip())
            base_model = base_model or lowered.get("basemodel") or lowered.get("base_model")
            model_id = model_id or lowered.get("modelid")
            version_id = version_id or lowered.get("versionid") or lowered.get("modelversionid")
        except Exception:
            continue
    unique = list(dict.fromkeys(triggers))
    return {"triggers": unique[:24], "base_model": base_model, "model_id": model_id, "version_id": version_id}


def scan_models(kind: str, force=False) -> list[dict]:
    with cache_lock:
        if kind in model_cache and not force:
            return model_cache[kind]
    items = []
    seen: dict[tuple[str, int], dict] = {}
    roots = list(MODEL_ROOTS.get(kind, []))
    if kind == "loras":
        roots.extend(root for root in MODEL_ROOTS.get("checkpoints", []) if root not in roots)
    checkpoint_roots = set(MODEL_ROOTS.get("checkpoints", []))
    for root in roots:
        if not root.exists():
            continue
        is_active_comfy_library = root == COMFY_ROOT / "models" / kind
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in MODEL_EXTENSIONS:
                continue
            if not safetensor_is_complete(path):
                continue
            misplaced_adapter = root in checkpoint_roots and safetensor_is_adapter(path)
            if kind == "checkpoints" and (misplaced_adapter or model_is_auxiliary(path)):
                continue
            if kind == "loras" and root in checkpoint_roots and not misplaced_adapter:
                continue
            key = (path.name.lower(), path.stat().st_size)
            if key in seen:
                # The active ComfyUI copy may not carry the Forge/Civitai
                # sidecar. Preserve the active model path, but borrow the
                # matching preview from another linked library.
                if not seen[key].get("preview"):
                    seen[key]["preview"] = find_preview(path)
                continue
            relative = str(path.relative_to(root)).replace("/", "\\")
            item = {
                "name": path.name,
                "relative": relative,
                "path": str(path),
                # Do not use resolve() here: users may junction their active
                # ComfyUI folder to a second drive, which would otherwise make
                # an active model appear as an unrelated external library.
                "source": "ComfyUI" if is_active_comfy_library else "External library",
                "size": path.stat().st_size,
                "architecture": "Z-Image LoRA" if kind == "loras" and (misplaced_adapter or "_FrojaLinked" in path.parts) else (safetensor_architecture(path) or architecture(path.name)),
                "preview": find_preview(path),
            }
            if kind == "loras":
                item.update(lora_metadata(path))
            items.append(item)
            seen[key] = item
    # Split-model engines live outside checkpoints. Expose only the compact
    # families for which Froja has a tested, native workflow, without flooding
    # the checkpoint picker with unrelated video and utility UNETs.
    if kind == "checkpoints" and SPECIAL_DIFFUSION_ROOT.exists():
        for path in SPECIAL_DIFFUSION_ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in MODEL_EXTENSIONS:
                continue
            if not safetensor_is_complete(path):
                continue
            architecture_name = architecture(path.name)
            if architecture_name not in {"Krea-2", "Flux2-Klein", "Mage-Flow", "Qwen-Image-2.1", "MOSS-Image", "MiniMax-H3-Image"}:
                continue
            key = (path.name.lower(), path.stat().st_size)
            if key in seen:
                if not seen[key].get("preview"):
                    seen[key]["preview"] = find_preview(path)
                continue
            item = {
                "name": path.name,
                "relative": path.name,
                "path": str(path),
                "source": "ComfyUI Diffusion",
                "size": path.stat().st_size,
                "architecture": architecture_name,
                "preview": find_preview(path),
            }
            items.append(item)
            seen[key] = item
    items.sort(key=lambda item: item["name"].lower())
    with cache_lock:
        model_cache[kind] = items
    return items


def build_workflow(payload: dict) -> dict:
    checkpoint = payload["checkpoint"]
    prompt = payload.get("prompt", "")
    negative = payload.get("negative_prompt", "")
    width = max(256, min(2048, int(payload.get("width", 768))))
    height = max(256, min(2048, int(payload.get("height", 768))))
    steps = max(1, min(100, int(payload.get("steps", 24))))
    cfg = max(0, min(30, float(payload.get("cfg", 7))))
    seed = int(payload.get("seed", -1))
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)
    sampler = payload.get("sampler", "euler")
    scheduler = payload.get("scheduler", "normal")

    prompt_loras = []
    for match in re.finditer(r"<lora:([^:>]+)(?::([0-9.]+))?>", prompt, flags=re.IGNORECASE):
        requested = match.group(1).strip().lower()
        strength = float(match.group(2) or 1.0)
        found = next((item for item in scan_models("loras") if Path(item["name"]).stem.lower() == requested), None)
        if not found:
            raise ValueError(f"LoRA '{match.group(1)}' was not found in the linked library.")
        prompt_loras.append({"name": found["relative"], "strength": strength})
    prompt = re.sub(r"<lora:[^>]+>", "", prompt, flags=re.IGNORECASE).strip()
    combined_loras = []
    seen_loras = set()
    for lora in [*payload.get("loras", []), *prompt_loras]:
        key = str(lora.get("name", "")).lower()
        if key and key not in seen_loras:
            combined_loras.append(lora)
            seen_loras.add(key)

    # Z-Image uses separately loaded diffusion, text-encoder, and VAE models.
    architecture_name = str(payload.get("architecture", ""))
    checkpoint_lower = str(checkpoint).lower()
    if architecture_name == "MOSS-Image":
        # Comfy-Org MOSS Base graph, with the quantized Qwen3.5 encoder.
        workflow = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": checkpoint, "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3.5_9b_w4a8_gptq.safetensors", "type": "moss_image", "device": "default"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative}},
            "5": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "6": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae_small.safetensors"}},
        }
        model_ref = ["1", 0]
        for index, lora in enumerate(combined_loras[:8], 20):
            node = str(index)
            workflow[node] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model_ref, "lora_name": lora["name"], "strength_model": float(lora.get("strength", 1))}}
            model_ref = [node, 0]
        workflow.update({
            "7": {"class_type": "KSampler", "inputs": {"model": model_ref, "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0], "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": sampler, "scheduler": "simple", "denoise": 1.0}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["6", 0]}},
            "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "Froja/MOSSImage"}},
        })
        return workflow

    if architecture_name == "MiniMax-H3-Image" or any(
        tag in checkpoint_lower for tag in ("minimax_h3_image", "minimax-h3-image", "minimaxh3image")
    ):
        # Official Comfy-Org MiniMax-H3-Image text-to-image graph
        # (workflows/minimax-h3/official/image_minimax_h3_image_t2i.json),
        # without the optional prompt-enhancer branch. The model is distilled
        # (6 steps, CFG 1) and is tuned for ~2048x2048 of area, so small
        # canvases are scaled up to that area while keeping the aspect ratio.
        target_area = 2048 * 2048
        if width * height < target_area:
            scale = (target_area / (width * height)) ** 0.5
            width = max(32, int(round(width * scale / 32)) * 32)
            height = max(32, int(round(height * scale / 32)) * 32)
        width, height = width // 32 * 32, height // 32 * 32
        return {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": checkpoint, "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {
                "clip_name": LOCAL_CONFIG.get("minimax_h3_image_text_encoder", "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
                "type": "minimax", "device": "default",
            }},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_image_vae_fp16.safetensors"}},
            "4": {"class_type": "MiniMaxH3ImageConditioning", "inputs": {
                "clip": ["2", 0], "vae": ["3", 0], "prompt": prompt, "width": width, "height": height,
            }},
            "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
            "6": {"class_type": "KSampler", "inputs": {
                "model": ["1", 0], "seed": seed, "steps": 6, "cfg": 1.0,
                "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
                "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["4", 1],
            }},
            "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
            "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/MiniMaxH3Image", "images": ["7", 0]}},
        }

    if architecture_name == "Qwen-Image-2.1" or any(
        tag in checkpoint_lower for tag in ("qwen_image_2.1", "qwen-image-2.1", "qwenimage2.1")
    ):
        # Official ComfyUI Qwen-Image-2.1 text-to-image graph. The INT8
        # diffusion model and encoder are deliberately used for this 12 GB
        # machine; ComfyUI offloads them between stages as required.
        is_gguf = checkpoint_lower.endswith(".gguf")
        return {
            # Qwen 2.1 GGUFs use the custom loader; safetensors use ComfyUI's
            # built-in diffusion-model loader. Both share the same encoder,
            # VAE, prompt encoding and sampler graph.
            "1": {"class_type": "UnetLoaderGGUF" if is_gguf else "UNETLoader", "inputs": (
                {"unet_name": checkpoint} if is_gguf else {"unet_name": checkpoint, "weight_dtype": "default"}
            )},
            "2": {"class_type": "CLIPLoader", "inputs": {
                "clip_name": "qwen3vl_8b_int8_convrot.safetensors",
                "type": "qwen_image", "device": "default",
            }},
            "3": {"class_type": "TextEncodeQwenImage21", "inputs": {
                "clip": ["2", 0], "prompt": prompt, "negative_prompt": negative,
                "resolution": max(width, height),
            }},
            "4": {"class_type": "EmptyLatentImage", "inputs": {
                "width": width, "height": height, "batch_size": 1,
            }},
            "5": {"class_type": "VAELoader", "inputs": {
                "vae_name": "qwen_image_2.1_vae_bf16.safetensors",
            }},
            "6": {"class_type": "KSampler", "inputs": {
                "model": ["1", 0], "seed": seed, "steps": steps, "cfg": 1.0,
                "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
                "positive": ["3", 0], "negative": ["3", 1], "latent_image": ["4", 0],
            }},
            "7": {"class_type": "VAEDecode", "inputs": {
                "samples": ["6", 0], "vae": ["5", 0],
            }},
            "8": {"class_type": "SaveImage", "inputs": {
                "filename_prefix": "Froja/QwenImage21", "images": ["7", 0],
            }},
        }

    if architecture_name == "Z-Image" or any(tag in checkpoint_lower for tag in ("zimage", "z-image", "z_image")):
        workflow = {
            # Z-Image Turbo is a diffusion-model file (not a bundled checkpoint).
            # Loading it through CheckpointLoaderSimple makes Comfy report it as missing.
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": checkpoint, "weight_dtype": "default"}},
            "4": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3_4b_fp8_scaled.safetensors", "type": "lumina2", "device": "default"}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 0]}},
            "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
            "7": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "8": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        }
        model_ref = ["1", 0]
        next_id = 20
        for lora in combined_loras[:8]:
            if not lora.get("name"):
                continue
            node_id = str(next_id)
            workflow[node_id] = {"class_type": "LoraLoaderModelOnly", "inputs": {
                "model": model_ref, "lora_name": lora["name"],
                "strength_model": float(lora.get("strength", 0.8)),
            }}
            model_ref = [node_id, 0]
            next_id += 1
        sampling_id = str(next_id)
        workflow[sampling_id] = {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": model_ref, "shift": 3.0}}
        workflow.update({
            "9": {"class_type": "KSampler", "inputs": {
                "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "res_multistep",
                "scheduler": "simple", "denoise": 1.0, "model": [sampling_id, 0],
                "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0],
            }},
            "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["8", 0]}},
            "11": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/ZImage", "images": ["10", 0]}},
        })
        return workflow

    # Krea-2 Turbo is a split 12B diffusion model. It requires the Krea-specific
    # Qwen3-VL text encoder and uses distilled 8-step sampling with zeroed
    # negative conditioning (CFG is disabled by the model design).
    if architecture_name == "Krea-2" or any(tag in checkpoint_lower for tag in ("krea2", "krea-2", "krea_2", "darkbeast")):
        # Krea-2 can be installed either as a lightweight GGUF UNet or as a
        # checkpoint-format model such as Krea2 DarkBeast.  Both use the same
        # Krea text encoder/VAE pipeline; only the model loader differs.
        model_loader = "UnetLoaderGGUF" if checkpoint_lower.endswith(".gguf") else "CheckpointLoaderSimple"
        workflow = {
            "1": {"class_type": model_loader, "inputs": {
                "unet_name": checkpoint
            } if model_loader == "UnetLoaderGGUF" else {
                "ckpt_name": checkpoint
            }},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
            "4": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["3", 0]}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "6": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        }
        model_ref = ["1", 0]
        next_id = 20
        sda_lora = next((item for item in combined_loras[:8] if "krea2_turbo_sda" in str(item.get("name", "")).lower()), None)
        for lora in combined_loras[:8]:
            if not lora.get("name") or lora is sda_lora:
                continue
            node_id = str(next_id)
            workflow[node_id] = {"class_type": "LoraLoaderModelOnly", "inputs": {
                "model": model_ref,
                "lora_name": lora["name"],
                "strength_model": float(lora.get("strength", 0.8)),
            }}
            model_ref = [node_id, 0]
            next_id += 1
        if sda_lora:
            # SDA is trained only for Krea Turbo's second sigma node. Applying
            # it for all eight steps damages detail, so split sampling at step 2.
            sda_node = str(next_id)
            workflow[sda_node] = {"class_type": "LoraLoaderModelOnly", "inputs": {
                "model": model_ref,
                "lora_name": sda_lora["name"],
                "strength_model": float(sda_lora.get("strength", 1.0)),
            }}
            workflow["7"] = {"class_type": "KSamplerAdvanced", "inputs": {
                "model": [sda_node, 0], "add_noise": "enable", "noise_seed": seed,
                "steps": 8, "cfg": 1.0, "sampler_name": "er_sde", "scheduler": "simple",
                "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0],
                "start_at_step": 0, "end_at_step": 2, "return_with_leftover_noise": "enable",
            }}
            workflow["10"] = {"class_type": "KSamplerAdvanced", "inputs": {
                "model": model_ref, "add_noise": "disable", "noise_seed": seed,
                "steps": 8, "cfg": 1.0, "sampler_name": "er_sde", "scheduler": "simple",
                "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["7", 0],
                "start_at_step": 2, "end_at_step": 8, "return_with_leftover_noise": "disable",
            }}
            sample_ref = ["10", 0]
        else:
            workflow["7"] = {"class_type": "KSampler", "inputs": {
                "model": model_ref, "seed": seed, "steps": 8, "cfg": 1.0,
                "sampler_name": "er_sde", "scheduler": "simple", "denoise": 1.0,
                "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0],
            }}
            sample_ref = ["7", 0]
        workflow.update({
            "8": {"class_type": "VAEDecode", "inputs": {"samples": sample_ref, "vae": ["6", 0]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/Krea2", "images": ["8", 0]}},
        })
        return workflow

    # FLUX.2 Klein 4B distilled is the compact FLUX.2 path for 12 GB GPUs. It
    # uses a single Qwen3 encoder, FLUX.2 latent/scheduler nodes and four steps.
    if architecture_name == "Flux2-Klein":
        model_loader = "UnetLoaderGGUF" if checkpoint_lower.endswith(".gguf") else "UNETLoader"
        workflow = {
            "1": {"class_type": model_loader, "inputs": {
                "unet_name": checkpoint, **({} if model_loader == "UnetLoaderGGUF" else {"weight_dtype": "default"})
            }},
            "2": {"class_type": "CLIPLoader", "inputs": {
                "clip_name": "qwen_3_4b_fp4_flux2.safetensors", "type": "flux2", "device": "default",
            }},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
            "4": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["3", 0]}},
            "5": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "6": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        }
        model_ref = ["1", 0]
        next_id = 20
        for lora in combined_loras[:8]:
            if not lora.get("name"):
                continue
            node_id = str(next_id)
            workflow[node_id] = {"class_type": "LoraLoaderModelOnly", "inputs": {
                "model": model_ref, "lora_name": lora["name"],
                "strength_model": float(lora.get("strength", 0.8)),
            }}
            model_ref = [node_id, 0]
            next_id += 1
        workflow.update({
            "7": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
            "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
            "9": {"class_type": "Flux2Scheduler", "inputs": {"steps": 4, "width": width, "height": height}},
            "10": {"class_type": "CFGGuider", "inputs": {
                "model": model_ref, "positive": ["3", 0], "negative": ["4", 0], "cfg": 1.0,
            }},
            "11": {"class_type": "SamplerCustomAdvanced", "inputs": {
                "noise": ["7", 0], "guider": ["10", 0], "sampler": ["8", 0],
                "sigmas": ["9", 0], "latent_image": ["5", 0],
            }},
            "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["6", 0]}},
            "13": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/Flux2Klein", "images": ["12", 0]}},
        })
        return workflow

    # Mage-Flow Turbo INT8 is a current 4B image model. Reuse the installed FP8
    # Qwen3-VL encoder so the total working set remains suitable for 12 GB VRAM.
    if architecture_name == "Mage-Flow" or "mage_flow" in checkpoint_lower or "mage-flow" in checkpoint_lower:
        workflow = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": checkpoint, "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {
                "clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "mage", "device": "default",
            }},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "mage_flow_vae_bf16.safetensors"}},
            "4": {"class_type": "TextEncodeMageFlowEdit", "inputs": {
                "clip": ["2", 0], "prompt": prompt, "negative_prompt": negative,
                "images": {}, "width": width, "height": height, "batch_size": 1, "vae": ["3", 0],
            }},
        }
        model_ref = ["1", 0]
        next_id = 20
        for lora in combined_loras[:8]:
            if not lora.get("name"):
                continue
            node_id = str(next_id)
            workflow[node_id] = {"class_type": "LoraLoaderModelOnly", "inputs": {
                "model": model_ref, "lora_name": lora["name"],
                "strength_model": float(lora.get("strength", 0.8)),
            }}
            model_ref = [node_id, 0]
            next_id += 1
        workflow.update({
            "5": {"class_type": "KSampler", "inputs": {
                "model": model_ref, "seed": seed, "steps": 4, "cfg": 1.0,
                "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
                "positive": ["4", 0], "negative": ["4", 1], "latent_image": ["4", 2],
            }},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["3", 0]}},
            "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/MageFlow", "images": ["6", 0]}},
        })
        return workflow

    # Flux checkpoints and exported Flux UNets need their own text encoders,
    # Flux guidance and SD3 latent.  Do not reuse the SD/SDXL checkpoint CLIP:
    # many Flux files intentionally contain only the diffusion model.
    if architecture_name == "Flux" or "flux" in checkpoint_lower:
        workflow = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
            "2": {"class_type": "DualCLIPLoader", "inputs": {
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux",
                "device": "default",
            }},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
            "4": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["3", 0], "guidance": 3.5}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["2", 0]}},
            "6": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "7": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        }
        model_ref = ["1", 0]
        clip_ref = ["2", 0]
        next_id = 20
        for lora in combined_loras[:8]:
            if not lora.get("name"):
                continue
            node_id = str(next_id)
            workflow[node_id] = {"class_type": "LoraLoader", "inputs": {
                "model": model_ref, "clip": clip_ref, "lora_name": lora["name"],
                "strength_model": float(lora.get("strength", 0.8)),
                "strength_clip": float(lora.get("strength", 0.8)),
            }}
            model_ref, clip_ref = [node_id, 0], [node_id, 1]
            next_id += 1
        sampling_id = str(next_id)
        workflow[sampling_id] = {"class_type": "ModelSamplingFlux", "inputs": {
            "model": model_ref, "max_shift": 1.15, "base_shift": 0.5, "width": width, "height": height,
        }}
        workflow.update({
            "8": {"class_type": "KSampler", "inputs": {
                "model": [sampling_id, 0], "seed": seed, "steps": max(1, min(50, steps)), "cfg": 1.0,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
                "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0],
            }},
            "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["7", 0]}},
            "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/Flux", "images": ["9", 0]}},
        })
        return workflow

    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
    }
    model_ref = ["1", 0]
    clip_ref = ["1", 1]
    next_id = 10
    for lora in combined_loras[:8]:
        if not lora.get("name"):
            continue
        node_id = str(next_id)
        workflow[node_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": model_ref,
                "clip": clip_ref,
                "lora_name": lora["name"],
                "strength_model": float(lora.get("strength", 0.8)),
                "strength_clip": float(lora.get("strength", 0.8)),
            },
        }
        model_ref = [node_id, 0]
        clip_ref = [node_id, 1]
        next_id += 1
    workflow.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_ref}},
        "5": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": cfg,
            "sampler_name": sampler, "scheduler": scheduler, "denoise": 1,
            "model": model_ref, "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
        }},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja", "images": ["6", 0]}},
    })
    return workflow


class FrojaHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        clean = urllib.parse.urlparse(path).path.lstrip("/") or "index.html"
        target = DIST / clean
        if not target.exists() and "." not in Path(clean).name:
            target = DIST / "index.html"
        return str(target)

    def log_message(self, fmt, *args):
        message = fmt % args
        print("[Froja]", message)
        if any(route in message for route in ("GET /api/status", "GET /api/models")):
            return
        try:
            LOGS.mkdir(exist_ok=True)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with request_log_lock, (LOGS / "backend.out.log").open("a", encoding="utf-8") as stream:
                stream.write(f"[{timestamp}] [Froja] {message}\n")
        except OSError:
            pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/llada/status":
            return json_response(self, llada_status())
        if parsed.path.startswith("/api/llada/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            with llada_jobs_lock:
                job = dict(llada_jobs.get(job_id, {"status": "missing", "error": "LLaDA job was not found."}))
            if job.get("status") == "complete":
                job["image"] = "/api/llada/image?job=" + urllib.parse.quote(job_id)
                job.pop("output", None)
            return json_response(self, job, 404 if job.get("status") == "missing" else 200)
        if parsed.path == "/api/llada/image":
            job_id = (query.get("job") or [""])[0]
            with llada_jobs_lock:
                output = llada_jobs.get(job_id, {}).get("output")
            path = Path(output).resolve() if output else None
            allowed = (ROOT / "test-output").resolve()
            if not path or allowed not in path.parents or not path.is_file():
                return self.send_error(404)
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path == "/api/pinned-loras":
            try:
                items = json.loads(PINNED_LORAS_FILE.read_text(encoding="utf-8")) if PINNED_LORAS_FILE.is_file() else []
                return json_response(self, {"items": items if isinstance(items, list) else []})
            except Exception as exc:
                return json_response(self, {"error": str(exc), "items": []}, 500)
        if parsed.path == "/api/pinned-checkpoints":
            try:
                items = json.loads(PINNED_CHECKPOINTS_FILE.read_text(encoding="utf-8")) if PINNED_CHECKPOINTS_FILE.is_file() else []
                return json_response(self, {"items": items if isinstance(items, list) else []})
            except Exception as exc:
                return json_response(self, {"error": str(exc), "items": []}, 500)
        if parsed.path == "/api/krea-fast/status":
            return json_response(self, krea_fast_status())
        if parsed.path == "/api/sensenova/status":
            return json_response(self, sensenova_status())
        if parsed.path.startswith("/api/sensenova/jobs/"):
            prompt_id = parsed.path.rsplit("/", 1)[-1]
            try:
                history = sensenova_request(f"/history/{prompt_id}")
                record = history.get(prompt_id)
                if not record:
                    return json_response(self, {"status": "running"})
                messages = record.get("status", {}).get("messages", [])
                errors = [message for kind, message in messages if kind == "execution_error"]
                images = []
                for output in record.get("outputs", {}).values():
                    for image in output.get("images", []):
                        images.append("/api/sensenova/image?" + urllib.parse.urlencode(image))
                if images:
                    return json_response(self, {"status": "complete", "images": images})
                error = errors[-1] if errors else "SenseNova produced no image."
                if isinstance(error, dict):
                    error = error.get("exception_message") or str(error)
                return json_response(self, {"status": "failed", "error": error})
            except Exception as exc:
                return json_response(self, {"status": "error", "error": str(exc)}, 500)
        if parsed.path == "/api/sensenova/image":
            try:
                with urllib.request.urlopen(SENSENOVA_URL + "/view?" + parsed.query, timeout=60) as response:
                    data = response.read()
                    content_type = response.headers.get("Content-Type", "image/png")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_error(404)
            return
        if parsed.path == "/api/sketch3d/status":
            return json_response(self, sketch3d_status())
        if parsed.path.startswith("/api/sketch3d/jobs/"):
            prompt_id = parsed.path.rsplit("/", 1)[-1]
            try:
                history = comfy_request(f"/history/{prompt_id}")
                record = history.get(prompt_id)
                if not record:
                    return json_response(self, {"status": "running"})
                messages = record.get("status", {}).get("messages", [])
                errors = [message for kind, message in messages if kind == "execution_error"]
                meshes = []
                for output in record.get("outputs", {}).values():
                    raw_meshes = output.get("mesh", output.get("meshes", output.get("3d", output.get("files", []))))
                    if isinstance(raw_meshes, (str, dict)):
                        raw_meshes = [raw_meshes]
                    for mesh in raw_meshes:
                        if isinstance(mesh, str):
                            mesh = {"filename": mesh, "subfolder": "", "type": "output"}
                        if isinstance(mesh, dict) and mesh.get("filename"):
                            meshes.append("/api/sketch3d/mesh-file?" + urllib.parse.urlencode(mesh))
                if meshes:
                    return json_response(self, {"status": "complete", "meshes": meshes})
                error = errors[-1] if errors else None
                if isinstance(error, dict):
                    error = error.get("exception_message") or str(error)
                return json_response(self, {"status": "failed", "error": error or "The mesh workflow produced no GLB or OBJ file."})
            except Exception as exc:
                return json_response(self, {"status": "error", "error": str(exc)}, 500)
        if parsed.path == "/api/sketch3d/mesh-file":
            filename = Path(urllib.parse.unquote(query.get("filename", [""])[0])).name
            subfolder = urllib.parse.unquote(query.get("subfolder", [""])[0]).replace("\\", "/").strip("/")
            candidate = (COMFY_OUTPUT / subfolder / filename).resolve()
            output_root = COMFY_OUTPUT.resolve()
            if not filename or output_root not in candidate.parents or not candidate.is_file() or candidate.suffix.lower() not in (".obj", ".glb"):
                return self.send_error(404)
            data = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "model/gltf-binary" if candidate.suffix.lower() == ".glb" else "model/obj")
            self.send_header("Content-Disposition", f'inline; filename="{candidate.name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path == "/api/training-session":
            return json_response(self, load_training_session())
        if parsed.path == "/api/materials":
            return json_response(self, scan_material_library())
        if parsed.path == "/api/material-image":
            relative = urllib.parse.unquote(query.get("path", [""])[0]).replace("\\", "/").strip("/")
            candidate = (MATERIAL_LIBRARY / relative).resolve()
            root = MATERIAL_LIBRARY.resolve()
            if not relative or root not in candidate.parents or not candidate.is_file() or candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                return self.send_error(404)
            data = candidate.read_bytes()
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(data))); self.send_header("Cache-Control", "no-cache"); self.end_headers(); self.wfile.write(data); return
        if parsed.path == "/api/system":
            return json_response(self, system_status())
        if parsed.path == "/api/status":
            ready = comfy_ready()
            stats = None
            if ready:
                try:
                    stats = comfy_request("/system_stats")
                except Exception:
                    pass
            return json_response(self, {
                "engine": "ready" if ready else ("failed" if comfy_start_error else "starting"),
                "engine_url": COMFY_URL,
                "engine_error": comfy_start_error or None,
                "counts": {kind: len(model_cache.get(kind, [])) for kind in MODEL_ROOTS},
                "stats": stats,
                "video_engine": wangp_status(),
            })
        if parsed.path == "/api/private-video/status":
            return json_response(self, wangp_status())
        if parsed.path == "/api/minimax-video/status":
            return json_response(self, minimax_status())
        if parsed.path.startswith("/api/minimax-video/files/"):
            job = minimax_jobs.get(parsed.path.rsplit("/", 1)[-1])
            if not job or not job.get("file") or not Path(job["file"]).exists():
                self.send_error(404); return
            data = Path(job["file"]).read_bytes()
            self.send_response(200); self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            return
        if parsed.path.startswith("/api/private-video/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            if job_id.startswith("mm-"):
                job = minimax_jobs.get(job_id)
                if not job:
                    return json_response(self, {"status": "error", "error": "Unknown video job."}, 404)
                return json_response(self, {k: v for k, v in job.items() if k != "file"})
            if not WANGP_ENABLED:
                return json_response(self, {"status": "disabled", "error": "Private video integration is disabled."}, 503)
            try:
                return json_response(self, wangp_request(f"/jobs/{urllib.parse.quote(job_id)}", timeout=5))
            except Exception as exc:
                return json_response(self, {"status": "offline", "error": str(exc)}, 503)
        if parsed.path.startswith("/api/private-video/files/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            try:
                with urllib.request.urlopen(WANGP_URL + "/files/" + urllib.parse.quote(job_id), timeout=60) as response:
                    data = response.read(); content_type = response.headers.get("Content-Type", "video/mp4")
                self.send_response(200); self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            except Exception: self.send_error(404)
            return
        if parsed.path == "/api/extensions":
            manifests = extension_manifests()
            try:
                ollama_models = ollama_request("/api/tags", timeout=4).get("models", [])
                ollama_online = True
            except Exception:
                ollama_models = []
                ollama_online = False
            return json_response(self, {
                "items": manifests,
                "ollama": {
                    "online": ollama_online,
                    "models": [item.get("name") for item in ollama_models if item.get("name")],
                },
            })
        if parsed.path == "/api/models":
            kind = query.get("type", ["checkpoints"])[0]
            search = query.get("search", [""])[0].lower()
            limit = min(5000, int(query.get("limit", ["200"])[0]))
            items = scan_models(kind, query.get("refresh", ["0"])[0] == "1")
            if search:
                items = [item for item in items if search in item["name"].lower()]
            return json_response(self, {"items": items[:limit], "total": len(items)})
        if parsed.path == "/api/video-models":
            registry_path = ROOT / "config" / "video-models.json"
            if not registry_path.is_file():
                return json_response(self, {"error": "Video model registry is missing."}, 404)
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for engine in registry.get("engines", []):
                requirements = engine.get("requirements", {})
                components = []
                for role, value in requirements.items():
                    path = Path(value)
                    present = path.is_file()
                    components.append({"role": role, "path": str(path), "present": present,
                                       "size": path.stat().st_size if present else 0})
                engine["components"] = components
                engine["requirements_present"] = all(item["present"] for item in components)
            return json_response(self, registry)
        if parsed.path == "/api/preview":
            requested = Path(urllib.parse.unquote(query.get("path", [""])[0]))
            preview_roots = [root for roots in MODEL_ROOTS.values() for root in roots] + [SPECIAL_DIFFUSION_ROOT]
            allowed = any(str(requested).lower().startswith(str(root).lower()) for root in preview_roots)
            if not allowed or not requested.is_file():
                return self.send_error(404)
            data = requested.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(requested.name)[0] or "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path.startswith("/api/jobs/"):
            prompt_id = parsed.path.rsplit("/", 1)[-1]
            try:
                history = comfy_request(f"/history/{prompt_id}")
                record = history.get(prompt_id)
                if not record:
                    return json_response(self, {"status": "running"})
                images = []
                for output in record.get("outputs", {}).values():
                    for image in output.get("images", []):
                        params = urllib.parse.urlencode(image)
                        images.append(f"/api/comfy-image?{params}")
                status = "complete" if images else "failed"
                return json_response(self, {"status": status, "images": images, "record": record.get("status")})
            except Exception as exc:
                return json_response(self, {"status": "error", "error": str(exc)}, 500)
        if parsed.path.startswith("/api/extension-jobs/"):
            prompt_id = parsed.path.rsplit("/", 1)[-1]
            try:
                history = extension_comfy_request(f"/history/{prompt_id}")
                record = history.get(prompt_id)
                if not record:
                    return json_response(self, {"status": "running"})
                messages = record.get("status", {}).get("messages", [])
                errors = [message for kind, message in messages if kind == "execution_error"]
                images = []
                for output in record.get("outputs", {}).values():
                    for image in output.get("images", []):
                        images.append("/api/extension-image?" + urllib.parse.urlencode(image))
                if images:
                    return json_response(self, {"status": "complete", "images": images})
                return json_response(self, {"status": "failed", "error": errors[-1] if errors else "Face workflow produced no image."})
            except Exception as exc:
                return json_response(self, {"status": "error", "error": str(exc)}, 500)
        if parsed.path.startswith("/api/joyai-jobs/"):
            prompt_id = parsed.path.rsplit("/", 1)[-1]
            try:
                history = joyai_request(f"/history/{prompt_id}")
                record = history.get(prompt_id)
                if not record:
                    return json_response(self, {"status": "running"})
                messages = record.get("status", {}).get("messages", [])
                errors = [message for kind, message in messages if kind == "execution_error"]
                images = []
                for output in record.get("outputs", {}).values():
                    for image in output.get("images", []):
                        images.append("/api/joyai-image?" + urllib.parse.urlencode(image))
                if images:
                    return json_response(self, {"status": "complete", "images": images})
                return json_response(self, {
                    "status": "failed",
                    "error": errors[-1].get("exception_message", "JoyAI produced no image") if errors else "JoyAI produced no image.",
                })
            except Exception as exc:
                return json_response(self, {"status": "error", "error": str(exc)}, 500)
        if parsed.path == "/api/comfy-image":
            try:
                with urllib.request.urlopen(COMFY_URL + "/view?" + parsed.query, timeout=30) as response:
                    data = response.read()
                    content_type = response.headers.get("Content-Type", "image/png")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_error(404)
            return
        if parsed.path == "/api/extension-image":
            try:
                with urllib.request.urlopen(EXTENSION_COMFY_URL + "/view?" + parsed.query, timeout=30) as response:
                    data = response.read()
                    content_type = response.headers.get("Content-Type", "image/png")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_error(404)
            return
        if parsed.path == "/api/joyai-image":
            try:
                with urllib.request.urlopen(JOYAI_URL + "/view?" + parsed.query, timeout=30) as response:
                    data = response.read()
                    content_type = response.headers.get("Content-Type", "image/png")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_error(404)
            return
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/llada/generate":
            try:
                status = llada_status()
                if not status["installed"]:
                    return json_response(self, {"error": "LLaDA quantized installation is incomplete.", "status": status}, 409)
                payload = read_json_body(self)
                prompt = re.sub(r"\s+", " ", str(payload.get("prompt", "")).strip())
                width = int(payload.get("width", 512))
                height = int(payload.get("height", 512))
                steps = int(payload.get("steps", 1))
                if not prompt or len(prompt) > 2000:
                    raise ValueError("Enter a prompt between 1 and 2000 characters.")
                if width < 256 or height < 256 or width > 1024 or height > 1024 or width % 32 or height % 32:
                    raise ValueError("LLaDA trial sizes must be multiples of 32 between 256 and 1024.")
                if steps not in {1, 2, 3, 4}:
                    raise ValueError("LLaDA Turbo supports 1 to 4 trial steps.")
                with llada_jobs_lock:
                    if any(job.get("status") == "running" for job in llada_jobs.values()):
                        return json_response(self, {"error": "A LLaDA image is already generating."}, 409)
                    job_id = uuid.uuid4().hex
                    llada_jobs[job_id] = {"status": "running", "started": time.time()}
                release_engine_memory("main", "extension", "joyai", "sensenova", "ollama")
                threading.Thread(target=run_llada_job, args=(job_id, prompt, width, height, steps), daemon=True).start()
                return json_response(self, {"job_id": job_id, "status": "running"})
            except ValueError as exc:
                return json_response(self, {"error": str(exc)}, 400)
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/pinned-loras":
            try:
                payload = read_json_body(self)
                raw_items = payload.get("items", [])
                if not isinstance(raw_items, list):
                    raise ValueError("Pinned LoRAs must be a list.")
                items = list(dict.fromkeys(str(item).strip() for item in raw_items if str(item).strip()))[:1000]
                PINNED_LORAS_FILE.parent.mkdir(parents=True, exist_ok=True)
                PINNED_LORAS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
                return json_response(self, {"ok": True, "items": items})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 400)
        if self.path == "/api/pinned-checkpoints":
            try:
                payload = read_json_body(self)
                raw_items = payload.get("items", [])
                if not isinstance(raw_items, list):
                    raise ValueError("Pinned checkpoints must be a list.")
                known = {item["relative"] for item in scan_models("checkpoints") if item.get("relative")}
                items = list(dict.fromkeys(str(item).strip() for item in raw_items if str(item).strip() in known))[:1000]
                PINNED_CHECKPOINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
                PINNED_CHECKPOINTS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
                return json_response(self, {"ok": True, "items": items})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 400)
        if self.path == "/api/krea-fast/generate":
            try:
                if engine_has_queued_work(extension_comfy_request):
                    return json_response(self, {
                        "error": "Variation Lab or another extension tool is still generating. Let it finish before starting Krea Fast.",
                    }, 409)
                release_engine_memory("extension", "joyai", "sensenova", "ollama")
                if not start_comfy():
                    return json_response(self, {"error": "The main ComfyUI engine could not start."}, 503)
                status = krea_fast_status()
                if not status["installed"]:
                    return json_response(self, {
                        "error": "Krea Fast installation is incomplete.", "status": status,
                    }, 409)
                workflow = build_krea_fast_workflow(read_json_body(self))
                result = comfy_request(
                    "/prompt", {"prompt": workflow, "client_id": "froja-krea-fast"}, timeout=60,
                )
                if "prompt_id" not in result:
                    return json_response(self, {
                        "error": "Krea Fast workflow validation failed.", "details": result,
                    }, 400)
                return json_response(self, {"prompt_id": result["prompt_id"]})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/sensenova/generate":
            try:
                release_engine_memory("main", "extension", "joyai")
                if not start_sensenova():
                    return json_response(self, {"error": "SenseNova could not start. Check its installation and Froja logs."}, 503)
                workflow = build_sensenova_workflow(read_json_body(self))
                result = sensenova_request("/prompt", {"prompt": workflow, "client_id": "froja-sensenova"}, timeout=60)
                if "prompt_id" not in result:
                    return json_response(self, {"error": "SenseNova workflow validation failed.", "details": result}, 400)
                return json_response(self, {"prompt_id": result["prompt_id"]})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/sketch3d/mesh":
            try:
                release_engine_memory("main", "joyai", "sensenova", "ollama")
                if not start_comfy():
                    return json_response(self, {"error": "The main ComfyUI engine could not start for Hunyuan3D."}, 503)
                workflow = build_sketch3d_mesh_workflow(read_json_body(self))
                result = comfy_request("/prompt", {"prompt": workflow, "client_id": "froja-sketch3d"}, timeout=30)
                if "prompt_id" not in result:
                    return json_response(self, {"error": "The 3D workflow did not validate.", "details": result}, 400)
                return json_response(self, {"prompt_id": result["prompt_id"], "message": "Real 3D reconstruction started."})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/materials/open-folder":
            try:
                return json_response(self, open_material_library())
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/training-session":
            try:
                return json_response(self, save_training_session(read_json_body(self)))
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 400)
        if self.path == "/api/dataset/export":
            try:
                data = build_dataset_zip(read_json_body(self))
                self.send_response(200); self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", 'attachment; filename="froja-lora-dataset.zip"')
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 400)
            return
        if self.path == "/api/minimax-video/enable":
            try:
                payload = read_json_body(self)
                set_minimax_video_enabled(bool(payload.get("enabled")))
                return json_response(self, minimax_status())
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/private-video/generate" and self.headers.get("X-Froja-Engine") == "minimax-h3":
            try:
                return json_response(self, start_minimax_job(read_json_body(self)))
            except (PermissionError, FileNotFoundError, ValueError) as exc:
                return json_response(self, {"error": str(exc)}, 400)
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 409)
        if self.path == "/api/private-video/generate":
            if not WANGP_ENABLED:
                return json_response(self, {"error": "Private Video Studio is disabled in Froja's local configuration."}, 503)
            try:
                payload = read_json_body(self)
                profile = str(payload.get("profile", "safe"))
                limits = {
                    "safe": {"width": 832, "height": 480, "seconds": 4, "steps": 6},
                    "balanced": {"width": 832, "height": 480, "seconds": 5, "steps": 8},
                    "experimental": {"width": 832, "height": 480, "seconds": 5, "steps": 15},
                }.get(profile, {"width": 832, "height": 480, "seconds": 3, "steps": 6})
                payload.update(limits)
                payload["profile"] = profile
                payload["private"] = True
                release_engine_memory("main", "extension", "joyai", "sensenova", "ollama")
                return json_response(self, wangp_request("/generate", payload, timeout=30))
            except urllib.error.URLError:
                return json_response(self, {"error": "The private video bridge is offline."}, 503)
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/private-video/cancel":
            if self.headers.get("X-Froja-Engine") == "minimax-h3":
                return json_response(self, cancel_minimax_job(str(read_json_body(self).get("job_id", ""))))
            if not WANGP_ENABLED:
                return json_response(self, {"error": "Private Video Studio is disabled."}, 503)
            try:
                return json_response(self, wangp_request("/cancel", read_json_body(self), timeout=10))
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 503)
        if self.path == "/api/open-output":
            try:
                payload = read_json_body(self)
                return json_response(self, open_generated_output(str(payload.get("image_url", ""))))
            except Exception as error:
                return json_response(self, {"error": str(error)}, 500)
        if self.path == "/api/enhance-image":
            try:
                return json_response(self, enhance_image(read_json_body(self)))
            except Exception as error:
                return json_response(self, {"error": str(error)}, 400)
        if self.path == "/api/image-metadata":
            try:
                return json_response(self, read_image_metadata(read_json_body(self)))
            except Exception as error:
                return json_response(self, {"error": str(error)}, 400)
        if self.path == "/api/image-to-prompt":
            try:
                return json_response(self, image_to_prompt(read_json_body(self)))
            except Exception as error:
                return json_response(self, {"error": str(error)}, 400)
        if self.path == "/api/reference-compose-prompt":
            try:
                return json_response(self, compose_reference_prompt(read_json_body(self)))
            except urllib.error.URLError:
                return json_response(self, {"error": "Ollama vision or prompt model is not available. Start Ollama and try again."}, 503)
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 400)
        if self.path == "/api/prompt-assist":
            try:
                return json_response(self, assist_prompt(read_json_body(self)))
            except urllib.error.URLError:
                return json_response(self, {"error": "Ollama is not available. Start Ollama and try again."}, 503)
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/face-swap":
            try:
                if engine_has_queued_work(comfy_request):
                    return json_response(self, {
                        "error": "Froja's main generator is still working. Let it finish or stop it before starting Face Studio.",
                    }, 409)
                release_engine_memory("main", "joyai", "sensenova", "ollama")
                if not start_extension_comfy():
                    return json_response(self, {"error": "Face Studio could not start its isolated engine. Check the extension log."}, 503)
                workflow = build_face_swap_workflow(read_json_body(self))
                result = extension_comfy_request("/prompt", {"prompt": workflow, "client_id": "froja-face-studio"}, timeout=30)
                if "prompt_id" not in result:
                    return json_response(self, {"error": "Face workflow validation failed", "details": result}, 400)
                return json_response(self, {"prompt_id": result["prompt_id"]})
            except urllib.error.URLError:
                return json_response(self, {"error": "The Face Studio extension engine is offline."}, 503)
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/character-transform":
            try:
                if engine_has_queued_work(comfy_request):
                    return json_response(self, {"error": "Froja's generator is already working. Let it finish or stop it first."}, 409)
                release_engine_memory("extension", "joyai", "sensenova", "ollama")
                workflow = build_character_transform_workflow(read_json_body(self))
                result = comfy_request("/prompt", {"prompt": workflow, "client_id": "froja-character-transformer"}, timeout=30)
                if "prompt_id" not in result:
                    return json_response(self, {"error": "Character Transformer workflow validation failed", "details": result}, 400)
                return json_response(self, {"prompt_id": result["prompt_id"]})
            except urllib.error.URLError:
                return json_response(self, {"error": "Froja's main image engine is offline."}, 503)
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/image-tool":
            try:
                if engine_has_queued_work(comfy_request):
                    return json_response(self, {
                        "error": "Froja's main generator is still working. Let it finish or stop it before starting Variation Lab.",
                    }, 409)
                release_engine_memory("main", "joyai", "sensenova", "ollama")
                if not start_extension_comfy():
                    return json_response(self, {"error": "The image-tool extension engine could not start."}, 503)
                workflow = build_image_tool_workflow(read_json_body(self))
                result = extension_comfy_request("/prompt", {"prompt": workflow, "client_id": "froja-image-tools"}, timeout=30)
                if "prompt_id" not in result:
                    return json_response(self, {"error": "Image-tool workflow validation failed", "details": result}, 400)
                return json_response(self, {"prompt_id": result["prompt_id"]})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/relight/light-map":
            try:
                payload = read_json_body(self)
                return json_response(self, {"image": light_map_data_url(payload.get("lights"), float(payload.get("ambient", 15)))})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 400)
        if self.path == "/api/relight":
            try:
                release_engine_memory("main", "joyai", "sensenova", "ollama")
                if not start_extension_comfy():
                    return json_response(self, {"error": "The Relight engine could not start."}, 503)
                workflow = build_relight_workflow(read_json_body(self))
                result = extension_comfy_request("/prompt", {"prompt": workflow, "client_id": "froja-relight"}, timeout=30)
                if "prompt_id" not in result:
                    return json_response(self, {"error": "Relight workflow validation failed", "details": result}, 400)
                return json_response(self, {"prompt_id": result["prompt_id"]})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/repair":
            try:
                release_engine_memory("main", "joyai", "sensenova", "ollama")
                if not start_extension_comfy():
                    return json_response(self, {"error": "The Repair Studio engine could not start."}, 503)
                workflow = build_repair_workflow(read_json_body(self))
                result = extension_comfy_request("/prompt", {"prompt": workflow, "client_id": "froja-repair"}, timeout=30)
                if "prompt_id" not in result:
                    return json_response(self, {"error": "Repair workflow validation failed", "details": result}, 400)
                return json_response(self, {"prompt_id": result["prompt_id"]})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/joyai-edit":
            try:
                release_engine_memory("main", "extension", "sensenova")
                if not start_joyai():
                    return json_response(self, {"error": "The isolated JoyAI engine could not start. Check the JoyAI log."}, 503)
                workflow = build_joyai_workflow(read_json_body(self))
                result = joyai_request("/prompt", {"prompt": workflow, "client_id": "froja-joyai"}, timeout=30)
                if "prompt_id" not in result:
                    return json_response(self, {"error": "JoyAI workflow validation failed", "details": result}, 400)
                return json_response(self, {"prompt_id": result["prompt_id"]})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/generate":
            if not comfy_ready():
                return json_response(self, {"error": "The image engine is still starting."}, 503)
            try:
                if engine_has_queued_work(extension_comfy_request):
                    return json_response(self, {
                        "error": "Variation Lab or another extension tool is still generating. Let it finish before starting the main generator.",
                    }, 409)
                release_engine_memory("extension", "joyai", "sensenova", "ollama")
                payload = read_json_body(self)
                selected = str(payload.get("checkpoint", ""))
                known = next((item for item in scan_models("checkpoints") if item["relative"] == selected), None)
                if not known:
                    return json_response(self, {"error": "The selected file is not a valid Froja checkpoint. Choose a main model; LoRA adapters belong in the LoRA selector."}, 400)
                payload["architecture"] = known["architecture"]
                workflow = build_workflow(payload)
                result = comfy_request("/prompt", {"prompt": workflow, "client_id": "froja"}, timeout=30)
                if "prompt_id" not in result:
                    return json_response(self, {"error": "Workflow validation failed", "details": result}, 400)
                return json_response(self, {"prompt_id": result["prompt_id"], "number": result.get("number")})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/interrupt":
            try:
                comfy_request("/interrupt", {}, timeout=10)
                return json_response(self, {"ok": True})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/loras/set-preview":
            try:
                payload = read_json_body(self)
                lora_path = Path(payload.get("lora_path", ""))
                image_url = str(payload.get("image_url", ""))
                known = next((item for item in scan_models("loras") if Path(item["path"]) == lora_path), None)
                if not known:
                    return json_response(self, {"error": "The selected LoRA is not in Froja's linked library."}, 400)
                parsed = urllib.parse.urlparse(image_url)
                if parsed.path != "/api/comfy-image" or not parsed.query:
                    return json_response(self, {"error": "Generate an image in Froja before assigning it as a LoRA preview."}, 400)
                with urllib.request.urlopen(COMFY_URL + "/view?" + parsed.query, timeout=60) as response:
                    image_data = response.read()
                preview_path = Path(str(lora_path.with_suffix("")) + ".preview.png")
                preview_path.write_bytes(image_data)
                scan_models("loras", force=True)
                return json_response(self, {"ok": True, "preview_path": str(preview_path)})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/checkpoints/set-preview":
            try:
                payload = read_json_body(self)
                checkpoint_path = Path(payload.get("checkpoint_path", ""))
                image_url = str(payload.get("image_url", ""))
                known = next((item for item in scan_models("checkpoints") if Path(item["path"]) == checkpoint_path), None)
                if not known:
                    return json_response(self, {"error": "The selected checkpoint is not in Froja's linked library."}, 400)
                parsed = urllib.parse.urlparse(image_url)
                if parsed.path not in {"/api/comfy-image", "/api/extension-image"} or not parsed.query:
                    return json_response(self, {"error": "Generate an image in Froja first, then assign it as a checkpoint preview."}, 400)
                source_url = COMFY_URL if parsed.path == "/api/comfy-image" else EXTENSION_COMFY_URL
                with urllib.request.urlopen(source_url + "/view?" + parsed.query, timeout=60) as response:
                    image_data = response.read()
                preview_path = Path(str(checkpoint_path.with_suffix("")) + ".preview.png")
                preview_path.write_bytes(image_data)
                scan_models("checkpoints", force=True)
                return json_response(self, {"ok": True, "preview_path": str(preview_path)})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        self.send_error(404)


def warm_up():
    threading.Thread(target=start_comfy, daemon=True).start()
    # Keep the optional RedNode/extension ComfyUI tool available from Froja's Tools menu.
    # It runs on its own port and does not alter the main generation engine.
    threading.Thread(target=start_extension_comfy, daemon=True).start()
    for kind in MODEL_ROOTS:
        threading.Thread(target=scan_models, args=(kind,), daemon=True).start()


if __name__ == "__main__":
    OUTPUTS.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    warm_up()
    # Ports around 3000 are commonly reserved by Windows VPN/Hyper-V networking. Use an unreserved
    # local default while still allowing installers and advanced users to
    # override it through FROJA_PORT.
    froja_port = int(os.environ.get("FROJA_PORT", "3310"))
    if not 1 <= froja_port <= 65535:
        raise ValueError("FROJA_PORT must be between 1 and 65535.")
    print(f"Froja Image Studio: http://127.0.0.1:{froja_port}")
    ThreadingHTTPServer(("127.0.0.1", froja_port), FrojaHandler).serve_forever()
