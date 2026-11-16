from pathlib import Path

p = Path(__file__).resolve().parents[1] / "backend.py"
s = p.read_text(encoding="utf-8")
marker = "\n\ndef read_image_metadata(payload: dict) -> dict:"
if marker not in s:
    raise SystemExit("function marker missing")
fn = r'''


def compose_reference_prompt(payload: dict) -> dict:
    intention = str(payload.get("intention", "")).strip()
    references = payload.get("references", [])
    model = str(payload.get("model", "qwen3.5:4b"))
    if not intention:
        raise ValueError("Describe what the references should become.")
    usable = []
    for index, item in enumerate(references if isinstance(references, list) else [], 1):
        if not isinstance(item, dict):
            continue
        description = str(item.get("description", "")).strip()
        role = str(item.get("role", f"Reference {index}")).strip()
        influence = int(item.get("influence", 70))
        if description:
            usable.append(f"REFERENCE {index} ROLE: {role}\nINFLUENCE: {influence}%\nVISIBLE CONTENT: {description}")
    if not usable:
        raise ValueError("Analyze at least one reference image first.")
    system = (
        "You are Froja's scene composition director. Build one precise image-generation prompt from independently analyzed "
        "visual references. Assign every reference only to its declared role. Explicitly describe spatial relationships, pose, "
        "body-to-furniture contact, scale, foreground/background placement, lighting integration and material application. "
        "The user intention is authoritative. Preserve character identity from the character reference. Never ask the model "
        "to reproduce a contact sheet, collage, reference board, labels, transparent checkerboard, separate panels, or pasted "
        "cut-outs. Return one fluent positive prompt only, followed by no commentary, headings, settings, or negative prompt."
    )
    content = "\n\n".join(usable) + "\n\nUSER INTENTION:\n" + intention
    result = ollama_request("/api/chat", {
        "model": model, "stream": False, "think": False, "keep_alive": "10m",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        "options": {"temperature": 0.3, "num_predict": 900},
    }, timeout=360)
    prompt = str(result.get("message", {}).get("content", "")).strip().strip('"')
    if not prompt:
        raise RuntimeError("Ollama returned an empty scene plan.")
    return {"prompt": prompt, "model": model, "references": len(usable)}
'''
s = s.replace(marker, fn + marker, 1)
route = '        if self.path == "/api/prompt-assist":'
if route not in s:
    raise SystemExit("route marker missing")
insert = '''        if self.path == "/api/reference-compose-prompt":
            try:
                return json_response(self, compose_reference_prompt(read_json_body(self)))
            except urllib.error.URLError:
                return json_response(self, {"error": "Ollama vision or prompt model is not available. Start Ollama and try again."}, 503)
            except Exception as exc:
                return json_response(self, {"error": str(exc)}, 400)
'''
s = s.replace(route, insert + route, 1)
p.write_text(s, encoding="utf-8")
