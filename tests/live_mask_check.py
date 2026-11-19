"""Measure the live Mask by words result on the t-shirt fixture."""

import argparse
import base64
import io
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageOps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Path to mask_test_man.png")
    parser.add_argument("--url", default="http://127.0.0.1:3310")
    parser.add_argument("--overlay", type=Path, help="Output PNG path (default: beside the source)")
    parser.add_argument("--threshold", type=float, help="Override Froja's detection threshold")
    parser.add_argument("--grow", type=int, help="Override Froja's mask growth in pixels")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    try:
        with urlopen(base_url + "/", timeout=3):
            pass
    except HTTPError:
        pass  # A web server responded. Let the API call report its status.
    except (URLError, TimeoutError) as exc:
        print(f"SKIP: Froja is offline at {base_url} ({exc})")
        return

    source_bytes = args.image.read_bytes()
    with Image.open(io.BytesIO(source_bytes)) as opened:
        media_type = Image.MIME[opened.format]
        source = ImageOps.exif_transpose(opened).convert("RGB")
    prompt = "the t-shirt"
    body = {"image": f"data:{media_type};base64," + base64.b64encode(source_bytes).decode("ascii"), "prompt": prompt}
    for option in ("threshold", "grow"):
        if getattr(args, option) is not None:
            body[option] = getattr(args, option)

    start = time.monotonic()
    request = Request(base_url + "/api/mask-from-text", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urlopen(request, timeout=90) as response:
        prompt_id = json.load(response)["prompt_id"]
    while time.monotonic() - start < 360:
        with urlopen(f"{base_url}/api/extension-jobs/{prompt_id}", timeout=20) as response:
            result = json.load(response)
        if result["status"] == "complete" and result.get("images"):
            break
        if result["status"] != "running":
            raise SystemExit(f"Mask job failed: {result}")
        time.sleep(2)
    else:
        raise SystemExit("Mask job did not finish within six minutes.")

    with urlopen(urljoin(base_url, result["images"][0]), timeout=20) as response:
        with Image.open(io.BytesIO(response.read())) as opened:
            mask_rgb = opened.convert("RGB")
    if mask_rgb.size != source.size:
        raise SystemExit(f"Mask size {mask_rgb.size} differs from source size {source.size}.")
    mask = mask_rgb.convert("L")
    histogram = mask.histogram()
    white = 100 * histogram[255] / (mask.width * mask.height)
    print(f'"{prompt}": {white:.3f}% white, {mask.width}×{mask.height}, {time.monotonic() - start:.1f}s')
    overlay = args.overlay or args.image.with_name(f"{args.image.stem}_mask_overlay.png")
    tinted = Image.blend(source, Image.new("RGB", source.size, "dodgerblue"), 0.5)
    Image.composite(tinted, source, mask).save(overlay)
    print(f"Overlay saved to {overlay}")
    if sum(histogram[1:255]) or ImageChops.difference(mask_rgb, mask.convert("RGB")).getbbox():
        raise SystemExit("Mask contains pixels other than black or white.")
    if not histogram[255]:
        raise SystemExit("Mask is empty.")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as exc:
        raise SystemExit(f"Froja returned HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc
