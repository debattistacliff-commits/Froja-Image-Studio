from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sqlite3
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # The service still indexes filenames without Pillow.
    Image = None


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "library.sqlite3"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS images (
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  filename TEXT NOT NULL,
  folder TEXT NOT NULL,
  modified_ns INTEGER NOT NULL,
  size_bytes INTEGER NOT NULL,
  width INTEGER,
  height INTEGER,
  prompt TEXT NOT NULL DEFAULT '',
  negative_prompt TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  seed TEXT NOT NULL DEFAULT '',
  sampler TEXT NOT NULL DEFAULT '',
  steps TEXT NOT NULL DEFAULT '',
  cfg TEXT NOT NULL DEFAULT '',
  raw_metadata TEXT NOT NULL DEFAULT '{}',
  favorite INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS collections (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS collection_items (
  collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
  PRIMARY KEY (collection_id, image_id)
);
"""


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def _json_dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _linked_text(graph: dict, link: object) -> str:
    if not isinstance(link, list) or not link:
        return ""
    node = graph.get(str(link[0]), {})
    inputs = node.get("inputs", {}) if isinstance(node, dict) else {}
    text = inputs.get("text")
    return text.strip() if isinstance(text, str) else ""


def _comfy_fields(graph: dict) -> dict:
    result = {"prompt": "", "negative_prompt": "", "model": "", "seed": "",
              "sampler": "", "steps": "", "cfg": ""}
    nodes = [node for node in graph.values() if isinstance(node, dict)]
    for node in nodes:
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        positive = _linked_text(graph, inputs.get("positive"))
        negative = _linked_text(graph, inputs.get("negative"))
        if positive and not result["prompt"]:
            result["prompt"] = positive
        if negative and not result["negative_prompt"]:
            result["negative_prompt"] = negative
        for key in ("ckpt_name", "unet_name"):
            value = inputs.get(key)
            if isinstance(value, str) and value and not result["model"]:
                result["model"] = value
        for source, target in (("seed", "seed"), ("noise_seed", "seed"),
                               ("sampler_name", "sampler"), ("steps", "steps"),
                               ("cfg", "cfg"), ("guidance", "cfg")):
            value = inputs.get(source)
            if value is not None and not isinstance(value, list) and result[target] == "":
                result[target] = str(value)
    if not result["prompt"]:
        for node in nodes:
            inputs = node.get("inputs", {})
            value = inputs.get("text") if isinstance(inputs, dict) else None
            if isinstance(value, str) and value.strip():
                result["prompt"] = value.strip()
                break
    return result


def extract_metadata(path: Path) -> dict:
    result = {"width": None, "height": None, "prompt": "", "negative_prompt": "",
              "model": "", "seed": "", "sampler": "", "steps": "", "cfg": "",
              "raw_metadata": "{}"}
    if Image is None:
        return result
    try:
        with Image.open(path) as image:
            result["width"], result["height"] = image.size
            info = {str(k): str(v) for k, v in image.info.items() if isinstance(v, (str, int, float, bool))}
            prompt_data = _json_dict(info.get("prompt"))
            workflow = _json_dict(info.get("workflow"))
            parameters = info.get("parameters", "")
            result["raw_metadata"] = json.dumps({"info": info, "prompt": prompt_data, "workflow": workflow}, ensure_ascii=False)
            if prompt_data:
                result.update(_comfy_fields(prompt_data))
            if parameters:
                lines = parameters.splitlines()
                result["prompt"] = lines[0].strip() if lines else ""
                for line in lines[1:]:
                    low = line.lower()
                    if low.startswith("negative prompt:"):
                        result["negative_prompt"] = line.split(":", 1)[1].strip()
                    for label, key in (("model:", "model"), ("seed:", "seed"), ("sampler:", "sampler"),
                                       ("steps:", "steps"), ("cfg scale:", "cfg")):
                        if label in low:
                            tail = line[low.index(label) + len(label):].split(",", 1)[0]
                            result[key] = tail.strip()

    except Exception:
        pass
    return result


def scan_folders(folders: list[Path]) -> dict:
    discovered: set[str] = set()
    indexed = updated = 0
    with connect() as db:
        for root in folders:
            root = root.resolve()
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                resolved = str(path.resolve())
                discovered.add(resolved)
                stat = path.stat()
                current = db.execute("SELECT modified_ns,size_bytes FROM images WHERE path=?", (resolved,)).fetchone()
                if current and current["modified_ns"] == stat.st_mtime_ns and current["size_bytes"] == stat.st_size:
                    continue
                meta = extract_metadata(path)
                values = (resolved, path.name, str(root), stat.st_mtime_ns, stat.st_size, meta["width"], meta["height"],
                          meta["prompt"], meta["negative_prompt"], meta["model"], meta["seed"], meta["sampler"],
                          meta["steps"], meta["cfg"], meta["raw_metadata"])
                db.execute("""INSERT INTO images(path,filename,folder,modified_ns,size_bytes,width,height,prompt,negative_prompt,
                           model,seed,sampler,steps,cfg,raw_metadata) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(path) DO UPDATE SET filename=excluded.filename,folder=excluded.folder,
                           modified_ns=excluded.modified_ns,size_bytes=excluded.size_bytes,width=excluded.width,
                           height=excluded.height,prompt=excluded.prompt,negative_prompt=excluded.negative_prompt,
                           model=excluded.model,seed=excluded.seed,sampler=excluded.sampler,steps=excluded.steps,
                           cfg=excluded.cfg,raw_metadata=excluded.raw_metadata""", values)
                indexed += current is None
                updated += current is not None
        # Only remove stale rows belonging to roots explicitly included in this scan.
        for root in folders:
            prefix = str(root.resolve())
            rows = db.execute("SELECT id,path FROM images WHERE folder=?", (prefix,)).fetchall()
            for row in rows:
                if row["path"] not in discovered and not Path(row["path"]).is_file():
                    db.execute("DELETE FROM images WHERE id=?", (row["id"],))
        total = db.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    return {"indexed": indexed, "updated": updated, "total": total}


class LibraryHandler(BaseHTTPRequestHandler):
    folders: list[Path] = []

    def log_message(self, fmt: str, *args) -> None:
        print("[Library Studio] " + fmt % args)

    def send_json(self, value: object, status: int = 200) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def payload(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return _json_dict(self.rfile.read(length).decode("utf-8")) if length else {}

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path in ("/", "/index.html"):
            body = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(body)
        if parsed.path == "/api/status":
            with connect() as db:
                total = db.execute("SELECT COUNT(*) FROM images").fetchone()[0]
            return self.send_json({"online": True, "private": True, "folders": [str(p) for p in self.folders], "images": total})
        if parsed.path == "/api/images":
            term = query.get("q", [""])[0].strip()
            clauses, values = [], []
            if term:
                clauses.append("(filename LIKE ? OR prompt LIKE ? OR negative_prompt LIKE ? OR model LIKE ?)")
                values.extend([f"%{term}%"] * 4)
            if query.get("favorite", [""])[0] == "1":
                clauses.append("favorite=1")
            join = ""
            collection = query.get("collection", [""])[0]
            if collection:
                join = " JOIN collection_items ci ON ci.image_id=images.id JOIN collections c ON c.id=ci.collection_id "
                clauses.append("c.name=?")
                values.append(collection)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            with connect() as db:
                rows = db.execute(f"SELECT images.* FROM images{join}{where} ORDER BY modified_ns DESC LIMIT 500", values).fetchall()
            return self.send_json([dict(row) for row in rows])
        if parsed.path == "/api/collections":
            with connect() as db:
                rows = db.execute("SELECT c.id,c.name,COUNT(ci.image_id) AS count FROM collections c LEFT JOIN collection_items ci ON ci.collection_id=c.id GROUP BY c.id ORDER BY c.name").fetchall()
            return self.send_json([dict(row) for row in rows])
        if parsed.path in ("/api/image", "/api/reuse"):
            try:
                image_id = int(query.get("id", ["0"])[0])
            except (TypeError, ValueError):
                return self.send_json({"error": "A valid numeric image id is required"}, 400)
            with connect() as db:
                row = db.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
            if not row:
                return self.send_json({"error": "Image not found"}, 404)
            if parsed.path == "/api/reuse":
                keys = ("prompt", "negative_prompt", "model", "seed", "sampler", "steps", "cfg", "width", "height")
                return self.send_json({key: row[key] for key in keys})
            path = Path(row["path"])
            if not path.is_file():
                return self.send_json({"error": "Source image is unavailable"}, 404)
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        return self.send_json({"error": "Route not found"}, 404)

    def do_POST(self) -> None:
        payload = self.payload()
        if self.path == "/api/scan":
            return self.send_json(scan_folders(self.folders))
        if self.path == "/api/favorite":
            try:
                image_id = int(payload.get("id", 0))
            except (TypeError, ValueError):
                return self.send_json({"error": "A valid numeric image id is required"}, 400)
            with connect() as db:
                db.execute("UPDATE images SET favorite=? WHERE id=?", (1 if payload.get("favorite") else 0, image_id))
            return self.send_json({"ok": True})
        if self.path == "/api/collections":
            name = str(payload.get("name", "")).strip()
            if not name:
                return self.send_json({"error": "Collection name is required"}, 400)
            with connect() as db:
                db.execute("INSERT OR IGNORE INTO collections(name) VALUES(?)", (name,))
                row = db.execute("SELECT id,name FROM collections WHERE name=?", (name,)).fetchone()
            return self.send_json(dict(row), 201)
        if self.path == "/api/collection-items":
            try:
                collection_id = int(payload.get("collection_id", 0))
                image_id = int(payload.get("image_id", 0))
            except (TypeError, ValueError):
                return self.send_json({"error": "Valid numeric collection and image ids are required"}, 400)
            with connect() as db:
                db.execute("INSERT OR IGNORE INTO collection_items(collection_id,image_id) VALUES(?,?)",
                           (collection_id, image_id))
            return self.send_json({"ok": True})
        return self.send_json({"error": "Route not found"}, 404)


def main() -> None:
    parser = argparse.ArgumentParser(description="Private Froja output-library plugin")
    parser.add_argument("--folder", action="append", default=[], help="Existing image folder to index; repeat as needed")
    parser.add_argument("--port", type=int, default=9020)
    args = parser.parse_args()
    LibraryHandler.folders = [Path(value) for value in args.folder]
    server = ThreadingHTTPServer(("127.0.0.1", args.port), LibraryHandler)
    print(f"Froja Library Studio: http://127.0.0.1:{args.port}")
    print("Source images remain untouched. Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
