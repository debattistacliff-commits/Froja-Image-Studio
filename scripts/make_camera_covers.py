"""Let Froja photograph its own camera looks: one product shot per camera profile (black studio, dramatic light).

    python scripts/make_camera_covers.py [checkpoint]

Uses the running Froja (port 3310). Writes public/camera-covers/<id>.webp. Skips covers that already exist.
"""
import io
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

FROJA = "http://127.0.0.1:3310"
OUT = Path(__file__).resolve().parent.parent / "public" / "camera-covers"
OUT.mkdir(parents=True, exist_ok=True)
CHECKPOINT = sys.argv[1] if len(sys.argv) > 1 else "analogMadnessKrea2Turbo_v30.safetensors"

STUDIO = ("professional product photography, three-quarter view, isolated on a seamless pure black background, "
          "dramatic low-key studio lighting, soft grey rim light from behind, glossy black floor with a faint reflection, "
          "sharp focus, ultra detailed, premium advertising photo, unbranded, no logos, no text")
CAMERAS = {
    "none": "a sleek black minimalist camera lens cap and a closed matte black camera body resting side by side",
    "s35": "a black professional Super 35 digital cinema camera with a modern cinema prime lens, matte box and top handle",
    "portrait": "a black full-frame mirrorless camera with a large 85mm f/1.8 portrait prime lens with glowing coated glass",
    "medium": "a black medium-format camera body with an 80mm standard prime lens and a large square sensor back",
    "wide": "a black full-frame camera with a wide-angle 24mm lens with a short petal lens hood",
    "documentary": "a compact black full-frame rangefinder style street camera with a small 35mm prime lens",
    "telephoto": "a black cinema camera with a long 135mm telephoto prime lens and follow focus",
    "macro": "a black full-frame camera with a 100mm macro lens and a ring light on the front of the lens",
    "vintage": "a vintage 35mm motion-picture film camera with a large anamorphic lens, film magazine on top, worn black paint",
}
NEGATIVE = "brand name, logo, text, watermark, label, letters, words, hands, person, cluttered background, colored background, blurry"


def call(path, payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(FROJA + path, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read() if path.startswith("/api/comfy-image") else json.loads(resp.read())


for cam_id, subject in CAMERAS.items():
    target = OUT / f"{cam_id}.webp"
    if target.exists():
        print("skip", cam_id); continue
    job = call("/api/generate", {
        "checkpoint": CHECKPOINT, "prompt": f"{subject}, {STUDIO}", "negative_prompt": NEGATIVE,
        "steps": 8, "cfg": 1, "seed": random.randint(1, 2**31), "width": 1024, "height": 1024,
        "sampler": "er_sde", "scheduler": "normal", "loras": [],
    })
    if "prompt_id" not in job:
        print("FAILED to queue", cam_id, job); continue
    for _ in range(600):
        time.sleep(2)
        status = call(f"/api/jobs/{job['prompt_id']}")
        if status.get("status") == "complete":
            raw = call(status["images"][0], timeout=120)
            Image.open(io.BytesIO(raw)).convert("RGB").resize((640, 640), Image.LANCZOS).save(target, "WEBP", quality=86)
            print("done", cam_id, flush=True); break
        if status.get("status") in ("failed", "error"):
            print("FAILED", cam_id, status); break
