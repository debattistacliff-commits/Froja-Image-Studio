"""Let Froja make its own slide covers: one picture per studio and per tool, showing what it is for.

    python scripts/make_slide_covers.py [checkpoint] [--force]

Uses the running Froja (port 3310). Writes public/covers/<key>.webp (640x640). Skips existing covers unless --force.
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
OUT = Path(__file__).resolve().parent.parent / "public" / "covers"
OUT.mkdir(parents=True, exist_ok=True)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
CHECKPOINT = args[0] if args else "Bjornulf_civitAI" + chr(92) + "analogMadnessKrea2Turbo_v30.safetensors"
FORCE = "--force" in sys.argv

LOOK = ("cinematic still life photography, dark moody background, dramatic low-key studio lighting with a soft cyan rim light, "
        "rich detail, premium editorial photo, no text, no letters, no logos, no watermark")
COVERS = {
    # studios
    "studio-create": "an artist's hand holding a glowing stylus above a large dark canvas where a vivid fantasy landscape is materialising out of streams of light particles",
    "studio-styles": "a dark gallery wall with five small framed paintings in very different art styles: a renaissance oil portrait, an impressionist garden, a japanese wave woodblock, an art nouveau woman and a cubist still life, each lit by a museum spotlight",
    "studio-pictures": "a dark studio wall covered with many pinned photographic prints of different colourful scenes, some framed, soft spotlight, a few prints lying on a table",
    "studio-tools": "a craftsman's dark tool wall with fine brushes, a jeweller's loupe, a scalpel, brass calipers and a small camera lens neatly arranged on black leather",
    "studio-video": "a wooden film clapperboard and a reel of 35mm film on a director's table, a projector light beam with floating dust behind them",
    "studio-training": "a wooden artist mannequin standing on a dark desk surrounded by eight small photographs of the same character seen from different angles",
    "studio-library": "rows of softly glowing glass cubes on dark shelves in a futuristic archive, each cube holding a tiny different miniature scene",
    "studio-settings": "close-up of a premium black aluminium control panel with knurled knobs, toggle switches and small glowing blue LED indicators",
    # tools (file names follow the slide symbols)
    "tool-eye": "a large magnifying glass held over a printed photograph of a landscape, glowing abstract light symbols rising out of the photo",
    "tool-atom": "a glowing orbital sculpture of light rings around a bright core floating above a black stone pedestal",
    "tool-layers": "several translucent glass panels stacked in depth, each holding part of a colourful painting, together forming one complete picture",
    "tool-bolt": "a bright lightning bolt striking a blank canvas on an easel, sparks and motion blur, sense of speed",
    "tool-hexdots": "six variations of the same small bronze robot figurine standing in a row on a dark table, each with a different design",
    "tool-nodes": "a dark board with glowing connected nodes and cables forming a network, red and cyan light",
    "tool-queue": "a long row of freshly printed colourful photographs coming out of a vintage printer in a dark room",
    "tool-portrait": "the same bearded man's portrait shown as four panels side by side: photograph, marble statue, oil painting and comic illustration",
    "tool-sphere": "seven spheres of different materials on black: polished gold, white marble, clear glass, dark wood, brown leather, brushed steel and rough stone",
    "tool-target": "an archery target with three arrows in the bullseye in a dark studio, single spotlight",
    "tool-cube": "a pencil sketch of a sports car on paper turning into a realistic grey clay 3D model of the same car on a drawing table",
    "tool-compose": "five reference photographs fanned out on a dark table, light beams merging them into one finished photograph in the centre",
    "tool-database": "a contact sheet with many small photos of the same woman's face from different angles, next to archival boxes and a loupe",
    "tool-zoomplus": "an old blurry faded photograph becoming sharp, clean and detailed under a jeweller's loupe",
    "tool-swap": "a pencil sketch of a castle on the left half smoothly transforming into a photorealistic castle at sunset on the right half",
    "tool-brush": "a fine paint brush repainting one small area of a photograph, the painted area revealing a new flower",
    "tool-face": "close-up portrait of a woman's face in soft window light, half photographic and half painted in oil",
    "tool-cycle": "a bronze statue of a lion in the middle of transforming into clear crystal glass, half bronze half crystal",
    "tool-pose": "a wooden artist mannequin in a dynamic running pose with thin glowing cyan pose lines drawn along its limbs",
    "tool-sun": "a white plaster classical bust lit by three coloured lights, warm orange from the left and cool blue from the right",
    "tool-wrench": "an art restorer's hands repairing a cracked old oil painting with a very fine brush under a work lamp",
    "tool-wand": "a glowing slender wand above a photograph whose sky is changing from daylight to a golden sunset",
    "tool-film": "a vintage film clapperboard and a reel of 35mm film on a director's table, a projector light beam with floating dust behind them",
}
NEGATIVE = "text, letters, words, logo, watermark, signature, caption, frame border, blurry, low quality"


def call(path, payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(FROJA + path, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read() if path.startswith("/api/comfy-image") else json.loads(resp.read())


for key, subject in COVERS.items():
    target = OUT / f"{key}.webp"
    if target.exists() and not FORCE:
        print("skip", key, flush=True); continue
    started = time.time()
    job = call("/api/generate", {
        "checkpoint": CHECKPOINT, "prompt": f"{subject}, {LOOK}", "negative_prompt": NEGATIVE,
        "steps": 8, "cfg": 1, "seed": random.randint(1, 2**31), "width": 1024, "height": 1024,
        "sampler": "er_sde", "scheduler": "normal", "loras": [],
    })
    if "prompt_id" not in job:
        print("FAILED to queue", key, job, flush=True); continue
    for _ in range(600):
        time.sleep(2)
        status = call(f"/api/jobs/{job['prompt_id']}")
        if status.get("status") == "complete":
            raw = call(status["images"][0], timeout=120)
            Image.open(io.BytesIO(raw)).convert("RGB").resize((640, 640), Image.LANCZOS).save(target, "WEBP", quality=86)
            print(f"done {key} in {time.time() - started:.0f}s", flush=True); break
        if status.get("status") in ("failed", "error"):
            print("FAILED", key, status, flush=True); break
print("ALL DONE", flush=True)
