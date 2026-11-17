"""Portable ComfyUI workflow conversion and packaging; no I/O side effects."""
from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Any


def _specs(info: dict) -> dict:
    inputs = info.get("input", {})
    return {**inputs.get("required", {}), **inputs.get("optional", {})}


def _widget(spec: list | tuple) -> bool:
    return isinstance(spec[0], list) or spec[0] in {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}


def _link(value: Any) -> bool:
    return (isinstance(value, list) and len(value) == 2
            and isinstance(value[0], (str, int)) and type(value[1]) is int)


def validate_api(api: dict, object_info: dict) -> list[str]:
    problems = []
    nodes = {str(key): value for key, value in api.items()}
    for key, node in nodes.items():
        kind = node.get("class_type")
        info = object_info.get(kind)
        if info is None:
            problems.append(f"Node {key}: unknown node type {kind}")
        inputs = node.get("inputs", {})
        if info:
            for name in info.get("input", {}).get("required", {}):
                if name not in inputs:
                    problems.append(f"Node {key} ({kind}): missing required input {name}")
        for name, value in inputs.items():
            if not _link(value):
                continue
            source, slot = str(value[0]), value[1]
            if source not in nodes:
                problems.append(f"Node {key}.{name}: link to missing node {source}")
            else:
                source_info = object_info.get(nodes[source].get("class_type"))
                if source_info is not None and not 0 <= slot < len(source_info.get("output", [])):
                    problems.append(f"Node {key}.{name}: output slot {slot} out of range on {source}")
    return problems


def api_to_ui(api: dict, object_info: dict) -> dict:
    nodes = {str(key): value for key, value in api.items()}
    ids: dict[str, int] = {}
    reserved = {int(key) for key in nodes if key.lstrip("-").isdigit()}
    next_id = max(reserved | {0}) + 1
    for key, node in nodes.items():
        if node["class_type"] not in object_info:
            raise ValueError(f"Unknown node type: {node['class_type']}")
        candidate = int(key) if key.lstrip("-").isdigit() else next_id
        if candidate in ids.values():
            candidate = next_id
        ids[key] = candidate
        next_id = max(next_id, candidate + 1)
    ordered: list[str] = []
    depths: dict[str, int] = {}
    pending = list(nodes)
    while pending:
        ready = [key for key in pending if all(str(v[0]) in ordered for v in nodes[key].get("inputs", {}).values() if _link(v))]
        if not ready:
            raise ValueError("Workflow has cyclic dependencies or missing source nodes")
        for key in ready:
            depths[key] = max((depths[str(v[0])] + 1 for v in nodes[key].get("inputs", {}).values() if _link(v)), default=0)
            ordered.append(key)
            pending.remove(key)
    result: dict[str, dict] = {}
    rows: dict[int, int] = {}
    for order, key in enumerate(ordered):
        node = nodes[key]
        kind = node["class_type"]
        info = object_info[kind]
        inputs = node.get("inputs", {})
        slots, widgets = [], []
        for name, spec in _specs(info).items():
            options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            value = inputs.get(name, options.get("default"))
            widget = _widget(spec)
            if not widget or _link(value):
                entry = {"name": name, "type": "COMBO" if isinstance(spec[0], list) else spec[0], "link": None}
                if widget:
                    entry["widget"] = {"name": name}
                slots.append(entry)
            if widget and (name in inputs or "default" in options):
                # Converted widgets retain their default value behind the socket.
                widgets.append(options.get("default", spec[0][0] if isinstance(spec[0], list) and spec[0] else 0) if _link(value) else value)
                if spec[0] == "INT" and ("control_after_generate" in options or name in {"seed", "noise_seed"}):
                    widgets.append("fixed")
        depth = depths[key]
        row = rows.get(depth, 0)
        rows[depth] = row + 1
        names = info.get("output_name", [])
        result[key] = {"id": ids[key], "type": kind, "pos": [depth * 400, row * 300], "size": [320, 200],
                       "flags": {}, "order": order, "mode": 0, "inputs": slots,
                       "outputs": [{"name": names[i] if i < len(names) else typ, "type": typ, "links": [], "slot_index": i} for i, typ in enumerate(info.get("output", []))],
                       "properties": {"Node name for S&R": kind}, "widgets_values": widgets}
    links = []
    for key in ordered:
        for slot, entry in enumerate(result[key]["inputs"]):
            value = nodes[key].get("inputs", {}).get(entry["name"])
            if _link(value):
                source, output = str(value[0]), value[1]
                link_id = len(links) + 1
                entry["link"] = link_id
                typ = result[source]["outputs"][output]["type"]
                links.append([link_id, ids[source], output, ids[key], slot, typ])
                result[source]["outputs"][output]["links"].append(link_id)
    return {"last_node_id": max(ids.values(), default=0), "last_link_id": len(links), "nodes": list(result.values()),
            "links": links, "groups": [], "config": {}, "extra": {}, "version": 0.4}


def portable_string(value: str) -> str:
    """Remove host-specific roots, including paths embedded in prose."""
    def relative(match: re.Match) -> str:
        path = match.group(0).replace("\\", "/")
        parts = [p for p in path.split("/") if p and p not in {".", ".."}]
        markers = {"models", "checkpoints", "diffusion_models", "unet", "clip", "text_encoders", "vae", "loras"}
        indices = [i for i, part in enumerate(parts[:-1]) if part.lower() in markers]
        return "/".join(parts[max(indices) + 1:]) if indices else (parts[-1] if parts else "")
    value = re.sub(r"(?<![\w./\\])(?:[A-Za-z]:[\\/]|\\\\|/)[^\s\"<>|]*", relative, value)
    # Only a real path piece like "Users\name\" is personal; the plain word "Users" in a prompt stays.
    value = re.sub(r"(?i)\bUsers[\\/][^\s\\/]+[\\/]?", "", value)
    return value


_WHOLE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/)\S")


def portable_path(value: str) -> str:
    """A value that IS a full path (spaces allowed): keep only the part after the models folder, or the file name."""
    parts = [p for p in value.replace("\\", "/").split("/") if p and p not in {".", ".."}]
    markers = {"models", "checkpoints", "diffusion_models", "unet", "clip", "text_encoders", "vae", "loras"}
    indices = [i for i, part in enumerate(parts[:-1]) if part.lower() in markers]
    return "/".join(parts[max(indices) + 1:]) if indices else (parts[-1] if parts else "")


def _portable(value: Any) -> Any:
    if isinstance(value, str):
        return portable_path(value) if _WHOLE_PATH.match(value) else portable_string(value)
    if isinstance(value, dict):
        return {portable_string(str(k)): _portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_portable(v) for v in value]
    return value


def make_pack(name: str, api: dict, ui: dict, plan: dict, sample_image: bytes | None,
              input_images: dict[str, bytes], models: list[dict]) -> bytes:
    buffer = io.BytesIO()
    model_lines = []
    destinations = {"checkpoint": "checkpoints", "unet": "diffusion_models", "clip": "text_encoders", "lora": "loras", "vae": "vae"}
    for model in _portable(models):
        kind = model.get("kind", "model")
        filename = model.get("relative", model.get("name", model.get("path", "unknown")))
        size = float(model.get("size", 0) or 0) / 1_000_000_000
        model_lines.append(f"{kind}, {filename}, {size:.3f} GB")
    readme = f"# {portable_string(name)}\n\nThis workflow generates images using the saved prompts and settings.\n"
    if plan:
        readme += "See plan.json for the intended picture and workflow plan.\n"
    readme += "\nPut these models in your ComfyUI models folders:\n"
    for model, line in zip(_portable(models), model_lines):
        readme += f"- models/{destinations.get(model.get('kind'), model.get('kind', 'model'))}: {line}\n"
    readme += "\nOpen ComfyUI and drag workflow_ui.json onto the canvas, then queue the workflow.\nThe API graph is in workflow_api.json. Copy supplied inputs into ComfyUI's input folder.\n"
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, data in (("workflow_ui.json", ui), ("workflow_api.json", api), ("plan.json", plan)):
            archive.writestr(filename, json.dumps(_portable(data), indent=2, ensure_ascii=False))
        archive.writestr("models.txt", "\n".join(model_lines) + "\n")
        archive.writestr("README.md", readme)
        if sample_image is not None:
            archive.writestr("sample.png", sample_image)
        used = set()
        for filename, data in input_images.items():
            safe = portable_string(filename).replace("\\", "/").split("/")[-1]
            if safe in {"", ".", ".."} or safe in used:
                raise ValueError("Input image filenames must be unique and nonempty")
            used.add(safe)
            archive.writestr("inputs/" + safe, data)
    return buffer.getvalue()
