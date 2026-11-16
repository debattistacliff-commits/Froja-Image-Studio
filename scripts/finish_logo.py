"""Turn the opaque Blender render (black background) into a transparent PNG for the app.

    python scripts/finish_logo.py

Black becomes transparent, glows and reflections fade smoothly (luminance-to-alpha with colour un-premultiply).
"""
from pathlib import Path

import numpy as np
from PIL import Image

BRAND = Path(__file__).resolve().parent.parent / "public" / "brand"
raw = np.asarray(Image.open(BRAND / "froja-logo-3d-raw.png").convert("RGB")).astype(np.float32) / 255.0
black = np.array([0.006, 0.007, 0.009], dtype=np.float32)  # the scene background
lifted = np.clip(raw - black, 0, 1)
alpha = np.clip(lifted.max(axis=2) * 1.6, 0, 1) ** 0.85
rgb = np.where(alpha[..., None] > 1e-4, lifted / np.maximum(alpha[..., None], 1e-4), 0)
rgba = np.dstack([np.clip(rgb, 0, 1), alpha])
img = Image.fromarray((rgba * 255).astype(np.uint8), "RGBA")
bbox = img.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
img = img.crop((max(0, bbox[0] - 20), max(0, bbox[1] - 20), min(img.width, bbox[2] + 20), min(img.height, bbox[3] + 20)))
img.thumbnail((1800, 1800), Image.LANCZOS)
img.save(BRAND / "froja-logo-3d.png", optimize=True)
print(img.size, (BRAND / "froja-logo-3d.png").stat().st_size // 1024, "KB")
