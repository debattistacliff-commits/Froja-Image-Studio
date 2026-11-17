"""Let Froja paint a sample picture for every art style (same scene each time, so the styles are easy to compare).

    python scripts/make_style_covers.py [checkpoint] [--force] [--only=slug,slug] [--style-first]

--only redoes just those styles; --style-first puts the style words before the scene (stronger style).

Reads the styles from app/page.tsx (artStyleOptions), uses the running Froja (port 3310) and writes
public/style-covers/<slug>.webp (512x512). Skips pictures that already exist unless --force.
The slug rule matches styleSlug() in app/page.tsx.
"""
import io
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FROJA = "http://127.0.0.1:3310"
OUT = ROOT / "public" / "style-covers"
OUT.mkdir(parents=True, exist_ok=True)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
CHECKPOINT = args[0] if args else "Bjornulf_civitAI" + chr(92) + "analogMadnessKrea2Turbo_v30.safetensors"
FORCE = "--force" in sys.argv
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
STYLE_FIRST = "--style-first" in sys.argv
SCENE = "a young woman in a long wool dress and a hooded cloak, fully clothed, holding a glowing lantern on an old stone bridge over a river, a castle on a hill in the distance, evening sky"
NEGATIVE = "nude, naked, topless, nsfw, text, letters, words, logo, watermark, signature, caption, frame, border, blurry, low quality"


def slug(name: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def styles() -> list:
    source = (ROOT / "app" / "page.tsx").read_text(encoding="utf-8")
    block = source[source.index("const artStyleOptions = ["):]
    block = block[: block.index("] as const;")]
    pair = re.compile(r'\[\s*"((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)",?\s*\]', re.S)
    return [(json.loads(f'"{a}"'), json.loads(f'"{b}"')) for a, b in pair.findall(block)]


SAFE_WORDS = [  # cover pictures go public: keep bodies clothed (CFG 1 ignores the negative prompt)
    (r"\b(monumental |dramatic |coherent evolutionary )?anatom(y|ical|ically)( confidence| coherent)?\b", "clothed figure"),
    (r"\bmuscular\b", "heroic"), (r"\bnude|naked|bare\b", "clothed"),
]


def safe(prompt: str) -> str:
    for pattern, word in SAFE_WORDS:
        prompt = re.sub(pattern, word, prompt, flags=re.I)
    extra = ", statues draped in robes" if re.search(r"sculpt|marble|bronze|statue|monument|relief", prompt, re.I) else ""
    return prompt + ", everyone fully dressed" + extra


def call(path, payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(FROJA + path, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read() if path.startswith("/api/comfy-image") else json.loads(resp.read())


items = styles()
print(f"{len(items)} styles", flush=True)
for number, (name, style_prompt) in enumerate(items, 1):
    target = OUT / f"{slug(name)}.webp"
    if ONLY is not None and slug(name) not in ONLY:
        continue
    if target.exists() and not FORCE and ONLY is None:
        continue
    started = time.time()
    try:
        job = call("/api/generate", {
            "checkpoint": CHECKPOINT, "prompt": safe(f"{style_prompt}, {SCENE}, {style_prompt}" if STYLE_FIRST else f"{SCENE}, {style_prompt}") + (", traditional hand-made artwork on paper or canvas, visible medium, not a photograph" if STYLE_FIRST else ""), "negative_prompt": NEGATIVE,
            "steps": 8, "cfg": 1, "seed": 20261116, "width": 768, "height": 768,
            "sampler": "er_sde", "scheduler": "normal", "loras": [],
        })
        for _ in range(600):
            time.sleep(2)
            status = call(f"/api/jobs/{job['prompt_id']}")
            if status.get("status") == "complete":
                raw = call(status["images"][0], timeout=120)
                Image.open(io.BytesIO(raw)).convert("RGB").resize((512, 512), Image.LANCZOS).save(target, "WEBP", quality=84)
                print(f"{number}/{len(items)} done {name} in {time.time() - started:.0f}s", flush=True)
                break
            if status.get("status") in ("failed", "error"):
                print(f"{number}/{len(items)} FAILED {name}: {status}", flush=True)
                break
    except Exception as exc:  # keep going with the next style
        print(f"{number}/{len(items)} FAILED {name}: {exc}", flush=True)
print("ALL DONE", flush=True)
