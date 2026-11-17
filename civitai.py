"""Optional Civitai fingerprint lookup. Model files are opened read-only."""
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "data/civitai-cache.json"
PREVIEWS = ROOT / "data/civitai-previews"
_lock = threading.RLock()
_request_lock = threading.Lock()
_last_request = 0.0


def _read():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(data):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    temp = CACHE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
    temp.replace(CACHE)


def sha256(path):
    path = Path(path).resolve()
    with _lock:
        stat = path.stat()
        key = str(path) + "|" + str(stat.st_size) + "|" + str(stat.st_mtime_ns)
        data = _read()
        hashes = data.setdefault("hashes", {})
        if key in hashes:
            return hashes[key]
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        if path.stat().st_mtime_ns != stat.st_mtime_ns or path.stat().st_size != stat.st_size:
            raise ValueError("Model changed while reading its fingerprint. Try again.")
        hashes[key] = digest.hexdigest()
        _save(data)
        return hashes[key]


def safe_images(images):
    result = []
    for item in images or []:
        if item.get("type", "image") != "image":
            continue
        level = item.get("nsfwLevel")
        safe = isinstance(level, (int, float)) and not isinstance(level, bool) and 0 <= level <= 1 if level is not None else item.get("nsfw") is False or item.get("nsfw") == "None"
        if safe and isinstance(item.get("url"), str):
            result.append(item)
    return result[:4]


def parse_version(data, creator=""):
    model = data.get("model") or {}
    model_id = data.get("modelId") or model.get("id")
    return {"found": True, "model_name": model.get("name", ""), "version_name": data.get("name", ""), "type": model.get("type", ""), "base_model": data.get("baseModel", ""), "trained_words": [x for x in data.get("trainedWords", []) if isinstance(x, str)], "creator": creator, "model_url": f"https://civitai.com/models/{int(model_id)}?modelVersionId={int(data['id'])}", "images": []}


def preview_path(digest, filename):
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or not re.fullmatch(r"[0-3]\.(png|jpg|webp)", filename):
        raise ValueError("Invalid preview path")
    target = PREVIEWS / digest / filename
    if not target.resolve().is_relative_to(PREVIEWS.resolve()):
        raise ValueError("Invalid preview path")
    return target


def write_settings(path, enabled, api_key=None):
    if not isinstance(enabled, bool) or (api_key is not None and not isinstance(api_key, str)):
        raise ValueError("Invalid settings")
    path = Path(path)
    with _lock:
        data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
        data["civitai_enabled"] = enabled
        if api_key is not None:
            data["civitai_api_key"] = api_key.strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


class RegionBlocked(RuntimeError):
    """Civitai answered 451: the service is blocked in the user's country."""


def _request(url, key="", image=False):
    global _last_request
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or (image and not (parsed.hostname == "civitai.com" or parsed.hostname.endswith(".civitai.com"))):
        raise ValueError("Invalid Civitai URL")
    with _request_lock:
        time.sleep(max(0, 1 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        headers = {"User-Agent": "Froja-Image-Studio"}
        if key and not image:
            headers["Authorization"] = "Bearer " + key
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:
            raw = response.read(3 * 1024 * 1024 + 1 if image else 4 * 1024 * 1024)
            if image:
                if len(raw) > 3 * 1024 * 1024:
                    raise ValueError("Preview exceeds 3 MB")
                mime = response.headers.get_content_type()
                ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(mime)
                if not ext:
                    raise ValueError("Unsupported preview")
                return raw, ext
            return json.loads(raw)


def lookup(digest, api_key=""):
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Invalid fingerprint")
    with _lock:
        cached = _read().get("lookups", {}).get(digest)
        if cached and time.time() - cached["time"] < 7 * 86400:
            return cached["info"]
    try:
        data = _request("https://civitai.com/api/v1/model-versions/by-hash/" + digest, api_key)
    except urllib.error.HTTPError as exc:
        if exc.code == 451:
            raise RegionBlocked("Civitai isn't available in your region: Civitai blocks some countries for legal reasons.") from None
        if exc.code in (401, 403):
            raise RuntimeError("Civitai refused the request. If you added an API key, check that it is correct.") from None
        if exc.code == 429:
            raise RuntimeError("Civitai is busy (too many requests). Try again in a minute.") from None
        if exc.code != 404:
            raise RuntimeError(f"Civitai lookup failed (error {exc.code}). Try again later.") from None
        data = None  # 404: this file is not on Civitai
    except urllib.error.URLError:
        raise RuntimeError("Froja could not reach civitai.com. Check your internet connection.") from None
    info = {"found": False, "images": []}
    if data:
        model = _request("https://civitai.com/api/v1/models/" + str(int(data["modelId"])), api_key)
        info = parse_version(data, (model.get("creator") or {}).get("username", ""))
        for n, item in enumerate(safe_images(data.get("images"))):
            try:
                raw, ext = _request(item["url"], image=True)
                target = preview_path(digest, f"{n}.{ext}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                info["images"].append(f"/api/civitai-preview/{digest}/{n}.{ext}")
            except (OSError, ValueError):
                continue
    with _lock:
        cache = _read()
        cache.setdefault("lookups", {})[digest] = {"time": time.time(), "info": info}
        _save(cache)
    return info
