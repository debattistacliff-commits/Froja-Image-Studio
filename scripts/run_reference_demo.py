import base64, io, json, sys, time, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output" / "reference-demo-inputs"
OUTPUT = ROOT / "output" / "reference-composer-demo"
OUTPUT.mkdir(parents=True, exist_ok=True)
FILES = [
    ("Character / identity", SOURCE / "3eb3540a-3204-47b2-9393-7ef82ecd42a4.png"),
    ("Furniture / pose support", SOURCE / "ana-m-rodriguez-01-atoxafloor-spehere.jpg"),
    ("Environment / room", SOURCE / "froja-enhanced-1787347312819.jpg"),
    ("Material / clothing", SOURCE / "ChatGPT Image Aug 20, 2026, 04_17_40 PM.png"),
    ("Prop / secondary object", SOURCE / "ChatGPT Image Aug 20, 2026, 04_08_17 PM.png"),
]

board = Image.new("RGB", (1536, 1024), "#11171c")
draw = ImageDraw.Draw(board)
layouts = [(20,60,720,944),(760,60,366,452),(1150,60,366,452),(760,552,366,452),(1150,552,366,452)]
for number, ((role, path), (x,y,w,h)) in enumerate(zip(FILES, layouts), 1):
    image = Image.open(path).convert("RGB")
    scale = min((w-16)/image.width, (h-16)/image.height)
    image = image.resize((max(1,int(image.width*scale)), max(1,int(image.height*scale))), Image.Resampling.LANCZOS)
    board.paste(image, (x+(w-image.width)//2, y+(h-image.height)//2))
    draw.rectangle((x,y,x+w,y+40), fill=(0,0,0))
    draw.text((x+12,y+12), f"REFERENCE {number}: {role}", fill="white")
board_path = OUTPUT / "reference-board.png"
board.save(board_path)
buffer = io.BytesIO(); board.save(buffer, format="PNG")
source_data = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

prompt = """Create one unified photorealistic editorial scene, not a collage or character sheet. Use Reference 1 for the adult woman's identity, face, hair, body proportions, clothing and jewelry. Use Reference 2 for a large luxurious cream upholstered lounge chair and natural seated pose. Use Reference 3 for an elegant warm contemporary room with warm plaster walls, natural oak flooring, textured rug, linen curtains, a tall daylight window, wooden side table, ceramic lamp and understated wall artwork. Use Reference 4 for realistic woven fabric, clothing fibers, color and material finish. Use Reference 5 as a tasteful secondary prop.

The same adult petite Latina woman sits diagonally at approximately 45 degrees in the chair, one arm relaxed on the rounded armrest, legs comfortably angled to one side, head turned naturally toward the camera. Preserve one consistent identity. Show realistic seated weight distribution, cushion compression, correct hip and leg position, natural hands, clothing folds, hair strands, accurate contact shadows and chair perspective. Professional interior editorial photography, soft window illumination, subtle warm practical lighting, cinematic 50mm lens, high dynamic range and restrained depth of field.

Produce exactly one coherent photograph. No collage, no split screen, no labels, no duplicated people, no multiple panels, no distorted hands, no extra limbs, no floating feet, no plastic skin, no cartoon or illustration."""

payload = {
    "mode": "krea2-reference",
    "checkpoint": "darkBeast30BF16INT8_darkBeast330.safetensors",
    "source_image": source_data,
    "prompt": prompt,
    "width": 768, "height": 768, "seed": 1787563201,
    "strength": 1, "loras": [],
}

def request_json(url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"} if body else {})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())

try:
    queued = request_json("http://127.0.0.1:7865/api/image-tool", payload)
    prompt_id = queued["prompt_id"]
    print(f"QUEUED {prompt_id}", flush=True)
    for _ in range(240):
        status = request_json(f"http://127.0.0.1:7865/api/extension-jobs/{prompt_id}")
        print(status.get("status", "running"), flush=True)
        if status.get("status") == "complete" and status.get("images"):
            image_url = "http://127.0.0.1:7865" + status["images"][0]
            with urllib.request.urlopen(image_url, timeout=120) as response:
                result_path = OUTPUT / "froja-reference-composer-result.png"
                result_path.write_bytes(response.read())
            print(f"RESULT {result_path}", flush=True)
            sys.exit(0)
        if status.get("status") in {"failed", "error"}:
            raise RuntimeError(str(status.get("error", status)))
        time.sleep(2)
    raise TimeoutError("Froja reference generation exceeded eight minutes.")
except Exception as exc:
    print(f"ERROR {type(exc).__name__}: {exc}", flush=True)
    sys.exit(1)
