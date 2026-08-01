from __future__ import annotations

import json
import base64
import mimetypes
import os
import random
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
OUTPUTS = ROOT / "outputs"
LOGS = ROOT / "logs"


def load_local_config() -> dict:
    config_path = Path(os.environ.get("FROJA_CONFIG", ROOT / "config" / "config.local.json"))
    if not config_path.is_file():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
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
COMFY_ROOT = configured_path(os.environ.get("FROJA_COMFY_ROOT") or LOCAL_CONFIG.get("comfy_root"), ROOT / "ComfyUI")
COMFY_PYTHON = venv_python(COMFY_ROOT)
COMFY_URL = os.environ.get("FROJA_COMFY_URL") or LOCAL_CONFIG.get("comfy_url", "http://127.0.0.1:9000")
EXTENSION_COMFY_URL = os.environ.get("FROJA_EXTENSION_COMFY_URL") or LOCAL_CONFIG.get("extension_comfy_url", "http://127.0.0.1:9001")
JOYAI_ROOT = configured_path(os.environ.get("FROJA_JOYAI_ROOT") or LOCAL_CONFIG.get("joyai_root"), ROOT / "ComfyUI_JoyAI")
JOYAI_PYTHON = venv_python(JOYAI_ROOT)
JOYAI_URL = os.environ.get("FROJA_JOYAI_URL") or LOCAL_CONFIG.get("joyai_url", "http://127.0.0.1:9002")
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
    kind: [configured_path(value, ROOT / "models" / kind) for value in configured_roots.get(kind, [])] or defaults
    for kind, defaults in DEFAULT_MODEL_ROOTS.items()
}
SPECIAL_DIFFUSION_ROOT = configured_path(
    LOCAL_CONFIG.get("diffusion_models_root"), COMFY_ROOT / "models" / "diffusion_models"
)
MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".gguf"}
PREVIEW_EXTENSIONS = [".preview.png", ".preview.jpeg", ".preview.jpg", ".png", ".jpg", ".jpeg", ".webp"]
model_cache: dict[str, list[dict]] = {}
cache_lock = threading.Lock()
comfy_process: subprocess.Popen | None = None
extension_comfy_process: subprocess.Popen | None = None
joyai_process: subprocess.Popen | None = None


def read_json_body(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    return json.loads(handler.rfile.read(length) or b"{}")


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
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


def extension_comfy_request(path: str, data: dict | None = None, timeout=15):
    encoded = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        EXTENSION_COMFY_URL + path,
        data=encoded,
        headers={"Content-Type": "application/json"} if encoded else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


def joyai_request(path: str, data: dict | None = None, timeout=30):
    encoded = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        JOYAI_URL + path,
        data=encoded,
        headers={"Content-Type": "application/json"} if encoded else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"{}")


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
    source_index = str(max(0, int(payload.get("source_face", 0))))
    target_index = str(max(0, int(payload.get("target_face", 0))))
    restoration = str(payload.get("restoration", "codeformer-v0.1.0.pth"))
    allowed_restoration = {"none", "codeformer-v0.1.0.pth", "GFPGANv1.3.pth", "GFPGANv1.4.pth", "GPEN-BFR-512.onnx"}
    if restoration not in allowed_restoration:
        restoration = "codeformer-v0.1.0.pth"
    visibility = max(0.1, min(1.0, float(payload.get("visibility", 0.85))))
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


def build_image_tool_workflow(payload: dict) -> dict:
    mode = str(payload.get("mode", "img2img"))
    if mode not in {"img2img", "inpaint", "controlnet"}:
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
    lighting = {
        "left": "Left Light", "right": "Right Light", "top": "Top Light",
        "bottom": "Bottom Light", "center": "Circle Light", "front": "Circle Light",
        "back": "None", "ambient": "None",
    }.get(str(payload.get("direction", "left")).lower(), "Left Light")
    return {
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


def extension_comfy_ready() -> bool:
    try:
        extension_comfy_request("/system_stats", timeout=2)
        return True
    except Exception:
        return False


def joyai_ready() -> bool:
    try:
        joyai_request("/system_stats", timeout=2)
        return True
    except Exception:
        return False


def release_engine_memory(*engines: str) -> None:
    """Best-effort VRAM handoff between Froja's isolated ComfyUI engines."""
    requests = {
        "main": lambda: comfy_request("/free", {"unload_models": True, "free_memory": True}, timeout=15),
        "extension": lambda: extension_comfy_request("/free", {"unload_models": True, "free_memory": True}, timeout=15),
        "joyai": lambda: joyai_request("/free", {"unload_models": True, "free_memory": True}, timeout=15),
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
        "--cpu-vae", "--preview-method", "none",
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


def image_to_prompt(payload: dict) -> dict:
    data_url = str(payload.get("image", ""))
    model = str(payload.get("model", "llama3.2-vision:latest"))
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
        "messages": [{"role": "user", "content": instruction, "images": [encoded]}],
        "options": {"temperature": 0.25, "num_predict": 650},
    }, timeout=360)
    visual_description = str(result.get("message", {}).get("content", "")).strip()
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
    content = str(polish.get("message", {}).get("content", "")).strip()
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
    global comfy_process
    if comfy_ready():
        return True
    if not COMFY_PYTHON.exists():
        return False
    LOGS.mkdir(exist_ok=True)
    stdout = open(LOGS / "comfy.log", "a", encoding="utf-8")
    stderr = open(LOGS / "comfy-error.log", "a", encoding="utf-8")
    args = [
        str(COMFY_PYTHON), str(COMFY_ROOT / "main.py"),
        "--listen", "127.0.0.1", "--port", url_port(COMFY_URL, 9000),
        "--disable-all-custom-nodes",
        "--whitelist-custom-nodes", "ComfyUI-GGUF",
    ]
    if EXTRA_PATHS.is_file():
        args.extend(["--extra-model-paths-config", str(EXTRA_PATHS)])
    comfy_process = subprocess.Popen(args, cwd=COMFY_ROOT, stdout=stdout, stderr=stderr)
    for _ in range(90):
        if comfy_ready():
            return True
        if comfy_process.poll() is not None:
            return False
        time.sleep(1)
    return False


def find_preview(path: Path) -> str | None:
    base = path.with_suffix("")
    candidates = [Path(str(base) + ext) for ext in PREVIEW_EXTENSIONS]
    for candidate in candidates:
        if candidate.exists():
            return urllib.parse.quote(str(candidate))
    return None


def architecture(name: str) -> str:
    value = name.lower()
    if "ace_step" in value or "acestep" in value:
        return "ACE Audio"
    if "zimage" in value or "z_image" in value or "z-image" in value:
        return "Z-Image"
    if "krea2" in value or "krea-2" in value or "krea_2" in value:
        return "Krea-2"
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
    seen = set()
    for root in MODEL_ROOTS.get(kind, []):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in MODEL_EXTENSIONS:
                continue
            key = (path.name.lower(), path.stat().st_size)
            if key in seen:
                continue
            seen.add(key)
            relative = str(path.relative_to(root)).replace("/", "\\")
            item = {
                "name": path.name,
                "relative": relative,
                "path": str(path),
                "source": "External library" if COMFY_ROOT.resolve() not in path.resolve().parents else "ComfyUI",
                "size": path.stat().st_size,
                "architecture": architecture(path.name),
                "preview": find_preview(path),
            }
            if kind == "loras":
                item.update(lora_metadata(path))
            items.append(item)
    # Large split-model engines live outside checkpoints. Expose only supported
    # Krea-2 diffusion weights here, without flooding the checkpoint picker with
    # every UNET in the shared ComfyUI library.
    if kind == "checkpoints" and SPECIAL_DIFFUSION_ROOT.exists():
        for path in SPECIAL_DIFFUSION_ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in MODEL_EXTENSIONS:
                continue
            if architecture(path.name) != "Krea-2":
                continue
            key = (path.name.lower(), path.stat().st_size)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "name": path.name,
                "relative": path.name,
                "path": str(path),
                "source": "ComfyUI Diffusion",
                "size": path.stat().st_size,
                "architecture": "Krea-2",
                "preview": find_preview(path),
            })
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
    if architecture_name == "Z-Image" or any(tag in checkpoint_lower for tag in ("zimage", "z-image", "z_image")):
        workflow = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors", "weight_dtype": "default"}},
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
    if architecture_name == "Krea-2" or any(tag in checkpoint_lower for tag in ("krea2", "krea-2", "krea_2")):
        workflow = {
            "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": checkpoint}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
            "4": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["3", 0]}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "6": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        }
        model_ref = ["1", 0]
        next_id = 20
        for lora in combined_loras[:8]:
            if not lora.get("name"):
                continue
            node_id = str(next_id)
            workflow[node_id] = {"class_type": "LoraLoaderModelOnly", "inputs": {
                "model": model_ref,
                "lora_name": lora["name"],
                "strength_model": float(lora.get("strength", 0.8)),
            }}
            model_ref = [node_id, 0]
            next_id += 1
        workflow.update({
            "7": {"class_type": "KSampler", "inputs": {
                "model": model_ref, "seed": seed, "steps": 8, "cfg": 1.0,
                "sampler_name": "er_sde", "scheduler": "simple", "denoise": 1.0,
                "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0],
            }},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["6", 0]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Froja/Krea2", "images": ["8", 0]}},
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
        print("[Froja]", fmt % args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/status":
            ready = comfy_ready()
            stats = None
            if ready:
                try:
                    stats = comfy_request("/system_stats")
                except Exception:
                    pass
            return json_response(self, {
                "engine": "ready" if ready else "starting",
                "counts": {kind: len(scan_models(kind)) for kind in MODEL_ROOTS},
                "stats": stats,
            })
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
        if parsed.path == "/api/preview":
            requested = Path(urllib.parse.unquote(query.get("path", [""])[0]))
            allowed = any(str(requested).lower().startswith(str(root).lower()) for roots in MODEL_ROOTS.values() for root in roots)
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
        if self.path == "/api/image-to-prompt":
            try:
                return json_response(self, image_to_prompt(read_json_body(self)))
            except Exception as error:
                return json_response(self, {"error": str(error)}, 400)
        if self.path == "/api/prompt-assist":
            try:
                return json_response(self, assist_prompt(read_json_body(self)))
            except urllib.error.URLError:
                return json_response(self, {"error": "Ollama is not available. Start Ollama and try again."}, 503)
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/face-swap":
            try:
                release_engine_memory("main", "joyai")
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
        if self.path == "/api/image-tool":
            try:
                release_engine_memory("main", "joyai")
                if not start_extension_comfy():
                    return json_response(self, {"error": "The image-tool extension engine could not start."}, 503)
                workflow = build_image_tool_workflow(read_json_body(self))
                result = extension_comfy_request("/prompt", {"prompt": workflow, "client_id": "froja-image-tools"}, timeout=30)
                if "prompt_id" not in result:
                    return json_response(self, {"error": "Image-tool workflow validation failed", "details": result}, 400)
                return json_response(self, {"prompt_id": result["prompt_id"]})
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 500)
        if self.path == "/api/relight":
            try:
                release_engine_memory("main", "joyai")
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
                release_engine_memory("main", "joyai")
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
                release_engine_memory("main", "extension")
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
                release_engine_memory("extension", "joyai")
                payload = read_json_body(self)
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
        self.send_error(404)


def warm_up():
    threading.Thread(target=start_comfy, daemon=True).start()
    for kind in MODEL_ROOTS:
        threading.Thread(target=scan_models, args=(kind,), daemon=True).start()


if __name__ == "__main__":
    OUTPUTS.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    warm_up()
    froja_port = int(os.environ.get("FROJA_PORT", "3000"))
    if not 1 <= froja_port <= 65535:
        raise ValueError("FROJA_PORT must be between 1 and 65535.")
    print(f"Froja Image Studio: http://127.0.0.1:{froja_port}")
    ThreadingHTTPServer(("127.0.0.1", froja_port), FrojaHandler).serve_forever()
