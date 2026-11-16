"""Queue Froja's isolated SenseNova Q4 smoke test through ComfyUI."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path


COMFY_URL = "http://127.0.0.1:8192"
MODEL_PATH = r"G:\ComfyUI_NEW\models\sensenova\SenseNova-U1.5-8B-MoT-Preview"
GGUF_FILE = "SenseNova-U1.5-8B-MoT-Preview-Q4_0-v2.gguf"


def request_json(path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        COMFY_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> None:
    workflow = {
        "1": {
            "class_type": "SenseNovaU1LocalLoader",
            "inputs": {
                "model_path": MODEL_PATH,
                "sensenova_u1_src": "",
                "device": "cuda",
                "dtype": "bfloat16",
                "attn_backend": "sdpa",
                "device_map": "none",
                "max_memory": "",
                "vram_mode": "balanced",
                "gguf_checkpoint": GGUF_FILE,
                "fast_vram_fraction": "0.9",
                "fast_vram_headroom_gib": "2.0",
                "fast_activation_reserve_gib": "4.0",
                "fast_vram_budget_gib": "0.0",
            },
        },
        "2": {
            "class_type": "SenseNovaU1LocalTextToImage",
            "inputs": {
                "u1_model": ["1", 0],
                "prompt": (
                    "A cinematic close-up product photograph of a circular black steel "
                    "camera-aperture emblem surrounding a luminous turquoise flame above "
                    "a small bronze anvil, dark studio background, cyan rim light, realistic "
                    "brushed metal, elegant, centered composition, no words, no watermark."
                ),
                "resolution": "2048x2048|1:1",
                "cfg_scale": 4.0,
                "cfg_norm": "none",
                "timestep_shift": 3.0,
                "cfg_interval_start": 0.0,
                "cfg_interval_end": 1.0,
                "num_steps": 1,
                "batch_size": 1,
                "seed": 23082026,
                "think_mode": False,
            },
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["2", 0],
                "filename_prefix": "Froja/SenseNova/sensenova_q4_smoke",
            },
        },
    }
    queued = request_json("/prompt", {"prompt": workflow})
    prompt_id = queued["prompt_id"]
    print(f"QUEUED {prompt_id}", flush=True)
    deadline = time.time() + 3600
    while time.time() < deadline:
        history = request_json(f"/history/{prompt_id}")
        if prompt_id in history:
            item = history[prompt_id]
            print(json.dumps(item, indent=2), flush=True)
            outputs = item.get("outputs", {}).get("3", {}).get("images", [])
            if outputs:
                image = outputs[0]
                output_path = Path(r"G:\ComfyUI_NEW\output") / image.get("subfolder", "") / image["filename"]
                print(f"OUTPUT {output_path}", flush=True)
                return
            raise SystemExit("SenseNova job finished without an image.")
        time.sleep(2)
    raise SystemExit("SenseNova smoke test timed out.")


if __name__ == "__main__":
    main()
