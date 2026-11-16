"""Private Froja-to-WanGP adapter.

This file is Froja code. It imports WanGP's documented Python API only from a
separate installation selected with WANGP_ROOT. Do not package WanGP inside a
public Froja release without reviewing its current licence and notices.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("WANGP_ROOT", "")).expanduser().resolve()
PORT = int(os.environ.get("FROJA_WANGP_BRIDGE_PORT", "9010"))
WORK = Path(os.environ.get("FROJA_WANGP_WORK", Path(__file__).resolve().parents[1] / "outputs" / "private-video"))
WORK.mkdir(parents=True, exist_ok=True)
JOBS: dict[str, dict] = {}
ACTIVE: dict[str, object] = {}
LOCK = threading.Lock()
SESSION = None


def reply(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status); handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw))); handler.send_header("Cache-Control", "no-store")
    handler.end_headers(); handler.wfile.write(raw)


def read_body(handler: BaseHTTPRequestHandler) -> dict:
    return json.loads(handler.rfile.read(int(handler.headers.get("Content-Length", "0"))) or b"{}")


def get_session():
    global SESSION
    if SESSION is not None: return SESSION
    api_file = ROOT / "shared" / "api.py"
    if not api_file.is_file(): raise RuntimeError(f"WanGP API was not found under {ROOT}")
    os.chdir(ROOT); sys.path.insert(0, str(ROOT))
    from shared.api import init  # type: ignore
    SESSION = init(root=ROOT, output_dir=WORK, cli_args=["--attention", "sdpa", "--profile", "4"], console_output=True)
    return SESSION


def save_source(job_id: str, value: str) -> str | None:
    if not value or not value.startswith("data:"): return None
    header, encoded = value.split(",", 1)
    mime = header.split(";", 1)[0].split(":", 1)[1]
    suffix = {"image/png":".png","image/jpeg":".jpg","image/webp":".webp","video/mp4":".mp4","audio/wav":".wav","audio/mpeg":".mp3"}.get(mime, ".bin")
    target = WORK / "inputs" / f"{job_id}{suffix}"; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(encoded)); return str(target)


def run_job(job_id: str, request: dict) -> None:
    try:
        source = save_source(job_id, str(request.get("source", "")))
        frames = max(5, round(float(request["seconds"]) * 24)); frames += (5 - frames % 17) % 17
        settings = {
            "model_type": request.get("model_type") or "froja_minimax_h3_12gb",
            "prompt": str(request.get("prompt", "")), "resolution": f'{request["width"]}x{request["height"]}',
            "num_inference_steps": int(request["steps"]), "video_length": frames,
            "duration_seconds": int(request["seconds"]), "force_fps": 24,
            # WanGP serializes its Text Encoder and Priority selectors in the
            # comma-delimited `config` field.  Q2 is the smallest supported H3
            # encoder and the empty second value keeps the Lower VRAM default.
            "config": "gguf_q2_k",
        }
        if source:
            settings["image_start"] = source
            settings["image_prompt_type"] = "S"
        job = get_session().submit_task(settings)
        with LOCK: ACTIVE[job_id] = job; JOBS[job_id].update(status="running", phase="Loading model")
        for event in job.events.iter(timeout=0.25):
            if getattr(event, "kind", "") == "progress":
                item = event.data; current = float(getattr(item, "current_step", 0) or 0); total = float(getattr(item, "total_steps", 1) or 1)
                with LOCK: JOBS[job_id].update(phase=str(getattr(item, "phase", "Generating")), progress=current / max(1, total))
        result = job.result()
        outputs = [str(path) for path in getattr(result, "generated_files", [])]
        with LOCK:
            JOBS[job_id].update(status="complete" if getattr(result, "success", False) else "failed", phase="Complete", progress=1, output=outputs[0] if outputs else "", video_url=f"/api/private-video/files/{job_id}" if outputs else "", outputs=outputs)
            if not getattr(result, "success", False): JOBS[job_id]["error"] = "; ".join(str(getattr(e, "message", e)) for e in getattr(result, "errors", []))
    except Exception as exc:
        with LOCK: JOBS[job_id].update(status="error", phase="Error", error=str(exc))
    finally:
        with LOCK: ACTIVE.pop(job_id, None)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): print("[Froja Video Bridge]", fmt % args)
    def do_GET(self):
        if self.path == "/status": return reply(self, {"online": True, "runtime_found": (ROOT / "shared" / "api.py").is_file(), "root": str(ROOT), "busy": bool(ACTIVE)})
        if self.path == "/models":
            try:
                models = get_session().list_model_metadata(main_output="video", include_availability=True)
                return reply(self, {"items": models})
            except Exception as exc: return reply(self, {"error": str(exc)}, 500)
        if self.path.startswith("/files/"):
            job_id = self.path.rsplit("/", 1)[-1]
            with LOCK: output = str(JOBS.get(job_id, {}).get("output", ""))
            target = Path(output).resolve() if output else None
            if not target or not target.is_file() or WORK.resolve() not in target.parents: return reply(self, {"error":"Video output was not found."}, 404)
            raw = target.read_bytes(); self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "video/mp4")
            self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if self.path.startswith("/jobs/"):
            job_id = self.path.rsplit("/", 1)[-1]
            with LOCK: item = dict(JOBS.get(job_id, {"status":"missing","error":"Unknown private video job."}))
            return reply(self, item, 200 if job_id in JOBS else 404)
        return reply(self, {"error":"Not found"}, 404)
    def do_POST(self):
        if self.path == "/generate":
            if not (ROOT / "shared" / "api.py").is_file(): return reply(self, {"error":"WanGP runtime is not installed."}, 503)
            with LOCK:
                if ACTIVE: return reply(self, {"error":"A private video job is already running."}, 409)
                job_id = uuid.uuid4().hex; JOBS[job_id] = {"job_id":job_id,"status":"queued","phase":"Queued","progress":0,"created":time.time()}
            threading.Thread(target=run_job, args=(job_id, read_body(self)), daemon=True).start(); return reply(self, {"job_id":job_id}, 202)
        if self.path == "/cancel":
            job_id = str(read_body(self).get("job_id", ""))
            with LOCK: job = ACTIVE.get(job_id)
            if job is not None: job.cancel()
            with LOCK:
                if job_id in JOBS: JOBS[job_id].update(status="cancelled", phase="Cancelling")
            return reply(self, {"ok": bool(job), "job_id": job_id})
        return reply(self, {"error":"Not found"}, 404)


if __name__ == "__main__":
    if not str(ROOT): raise SystemExit("Set WANGP_ROOT to the separate private WanGP installation.")
    print(f"Froja private video bridge: http://127.0.0.1:{PORT} -> {ROOT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
