"""Build docs/images/froja-social-preview.png (1280x640): dotted metal, the 3D logo and the studios screen.

    python scripts/make_social_card.py
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1280, 640
bg = Image.open(ROOT / "public/materials-ui/dotwave.jpg").convert("RGB").resize((W, int(W * 1440 / 2560)))
bg = bg.crop((0, (bg.height - H) // 2, W, (bg.height - H) // 2 + H))
bg = ImageEnhance.Brightness(bg).enhance(0.55).convert("RGBA")
shot = Image.open(ROOT / "docs/screenshots/01-studios.jpg").convert("RGB").resize((620, 349), Image.LANCZOS)
frame = Image.new("RGBA", (shot.width + 4, shot.height + 4), (47, 198, 255, 255))
bg.alpha_composite(frame.filter(ImageFilter.GaussianBlur(16)), (W - shot.width - 72, 203))
bg.alpha_composite(frame, (W - shot.width - 72, 203))
bg.alpha_composite(shot.convert("RGBA"), (W - shot.width - 70, 205))
logo = Image.open(ROOT / "public/brand/froja-logo-3d.png").convert("RGBA")
logo.thumbnail((560, 230), Image.LANCZOS)
fade = Image.new("L", logo.size, 255)
draw = ImageDraw.Draw(fade)
start = int(logo.height * 0.62)
for y in range(start, logo.height):
    draw.line([(0, y), (logo.width, y)], fill=int(255 * (1 - (y - start) / (logo.height - start))))
logo.putalpha(ImageChops.multiply(logo.getchannel("A"), fade))
bg.alpha_composite(logo, (50, 60))
d = ImageDraw.Draw(bg)
font = ImageFont.truetype(str(ROOT / "assets/fonts/Michroma-Regular.ttf"), 21)
small = ImageFont.truetype(str(ROOT / "assets/fonts/Michroma-Regular.ttf"), 15)
for i, line in enumerate(["Local image & video studio", "for ComfyUI and Ollama"]):
    d.text((60, 330 + i * 38), line, font=font, fill=(232, 236, 239))
for i, line in enumerate(["Studios slider  ·  3D Relight room", "LED design  ·  System monitor", "Free  ·  private  ·  on your PC"]):
    d.text((60, 432 + i * 30), line, font=small, fill=(140, 214, 255))
bg.convert("RGB").save(ROOT / "docs/images/froja-social-preview.png", optimize=True)
print("saved docs/images/froja-social-preview.png")
