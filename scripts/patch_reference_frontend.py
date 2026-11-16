from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app" / "reference-composer-studio.tsx"
s = p.read_text(encoding="utf-8")
s = s.replace(
    'type Slot = { role: string; image: string; name: string; influence: number };',
    'type Slot = { role: string; image: string; name: string; influence: number; description: string; analyzing: boolean };',
)
s = s.replace('influence: 100 }', 'influence: 100, description: "", analyzing: false }')
s = s.replace('influence: 85 }', 'influence: 85, description: "", analyzing: false }')
s = s.replace('influence: 75 }', 'influence: 75, description: "", analyzing: false }')
s = s.replace('influence: 65 }', 'influence: 65, description: "", analyzing: false }')
s = s.replace('influence: 60 }', 'influence: 60, description: "", analyzing: false }')
s = s.replace('  const [inspect, setInspect] = useState(false);', '  const [inspect, setInspect] = useState(false);\n  const [planning, setPlanning] = useState(false);')
s = s.replace(
    '`REFERENCE ${index + 1} — ${slot.role} (${slot.influence}% influence): ${roleDirections[slot.role] || "use this reference carefully"}.`,',
    '`REFERENCE ${index + 1} — ${slot.role} (${slot.influence}% influence): ${roleDirections[slot.role] || "use this reference carefully"}. VISUAL ANALYSIS: ${slot.description || "not analyzed yet"}.`,',
)
s = s.replace(
    'reader.onload = () => setSlot(index, { image: String(reader.result), name: file.name });',
    'reader.onload = () => setSlot(index, { image: String(reader.result), name: file.name, description: "", analyzing: false });',
)
needle = '  const makeReferenceBoard = async () => {'
methods = '''  const describeImage = async (image: string) => {
    const response = await fetch("/api/image-to-prompt", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image, model: "llama3.2-vision:latest", detail: "balanced" }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Ollama could not analyze this reference.");
    return String(data.prompt || data.description || "").trim();
  };

  const analyzeSlot = async (index: number) => {
    const slot = slots[index];
    if (!slot.image || slot.analyzing) return;
    setSlot(index, { analyzing: true });
    setStatus(`Analyzing reference ${index + 1} with Ollama…`);
    try {
      const description = await describeImage(slot.image);
      setSlot(index, { description, analyzing: false });
      setStatus(`Reference ${index + 1} analyzed.`);
    } catch (error) {
      setSlot(index, { analyzing: false });
      setStatus(error instanceof Error ? error.message : "Reference analysis failed.");
    }
  };

  const analyzeAll = async () => {
    setStatus("Analyzing every reference one at a time…");
    for (let index = 0; index < slots.length; index += 1) {
      if (!slots[index].image || slots[index].description) continue;
      setSlot(index, { analyzing: true });
      try {
        const description = await describeImage(slots[index].image);
        setSlot(index, { description, analyzing: false });
      } catch (error) {
        setSlot(index, { analyzing: false });
        setStatus(error instanceof Error ? error.message : `Reference ${index + 1} failed.`);
        return;
      }
    }
    setStatus("All loaded references analyzed. Ask Ollama to compose the scene.");
  };

  const planScene = async () => {
    const references = slots.filter((slot) => slot.image && slot.description).map(({ role, description, influence }) => ({ role, description, influence }));
    if (!references.length || !prompt.trim()) return;
    setPlanning(true);
    setStatus("Ollama is arranging the character, furniture and environment…");
    try {
      const response = await fetch("/api/reference-compose-prompt", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intention: prompt, references, model: "qwen3.5:4b" }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Scene planning failed.");
      setPrompt(String(data.prompt));
      setStatus("Scene plan ready. Review it, then generate the unified image.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Scene planning failed.");
    } finally { setPlanning(false); }
  };

'''
if needle not in s:
    raise SystemExit("method marker missing")
s = s.replace(needle, methods + needle, 1)
s = s.replace(
    '{slot.image && <button className="remove" onClick={() => setSlot(index, { image: "", name: "" })}>Remove</button>}',
    '''{slot.image && <div className="reference-analysis">
            <button onClick={() => analyzeSlot(index)} disabled={slot.analyzing}>{slot.analyzing ? "Analyzing…" : slot.description ? "Analyze again" : "Analyze with Ollama"}</button>
            <textarea value={slot.description} onChange={(event) => setSlot(index, { description: event.target.value })} placeholder="Ollama's editable description of this reference…" />
            <button className="remove" onClick={() => setSlot(index, { image: "", name: "", description: "", analyzing: false })}>Remove</button>
          </div>}''',
)
s = s.replace(
    '<div><label>Main creative instruction<textarea value={prompt}',
    '<div><div className="reference-ai-actions"><button onClick={analyzeAll} disabled={!active.length}>1 · Analyze all references</button><button onClick={planScene} disabled={planning || !active.some((slot) => slot.description) || !prompt.trim()}>{planning ? "Planning…" : "2 · Suggest composition with Ollama"}</button></div><label>Main creative instruction / composed scene<textarea value={prompt}',
)
s = s.replace('Generate Unified Image</button>', '3 · Generate Unified Image</button>')
p.write_text(s, encoding="utf-8")

css = Path(__file__).resolve().parents[1] / "app" / "reference-composer-studio.css"
t = css.read_text(encoding="utf-8")
t += '''

.reference-analysis { display:grid; gap:8px; margin-top:8px; }
.reference-analysis button, .reference-ai-actions button { border:1px solid #31545b; border-radius:8px; padding:9px 11px; background:#102329; color:#d9faff; cursor:pointer; font-weight:650; }
.reference-analysis button:disabled, .reference-ai-actions button:disabled { opacity:.45; cursor:not-allowed; }
.reference-analysis textarea { width:100%; min-height:86px; resize:vertical; border:1px solid #27434a; border-radius:8px; padding:9px; background:#081216; color:#dcecf0; font:inherit; }
.reference-ai-actions { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }
.reference-ai-actions button:last-child { border-color:#16b9b2; background:#103c3b; }
'''
css.write_text(t, encoding="utf-8")
