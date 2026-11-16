"use client";

import { useEffect, useMemo, useState } from "react";

type Slot = { role: string; image: string; name: string; influence: number; description: string; analyzing: boolean };
type Props = {
  onClose: () => void;
  checkpoint: string;
  architecture?: string;
  initialPrompt: string;
  width: number;
  height: number;
  seed: number;
  loras: { relative: string; strength: number }[];
};

const defaults: Slot[] = [
  { role: "Character / identity", image: "", name: "", influence: 100, description: "", analyzing: false },
  { role: "Furniture / pose support", image: "", name: "", influence: 85, description: "", analyzing: false },
  { role: "Environment / room", image: "", name: "", influence: 75, description: "", analyzing: false },
  { role: "Material / clothing", image: "", name: "", influence: 65, description: "", analyzing: false },
  { role: "Prop / secondary object", image: "", name: "", influence: 60, description: "", analyzing: false },
];

const roleDirections: Record<string, string> = {
  "Character / identity": "preserve the subject's identity, face, hair, body proportions, skin tone, clothing and jewelry",
  "Furniture / pose support": "use the furniture design, scale, upholstery and believable body contact or seated pose",
  "Environment / room": "use the environment's architecture, layout, atmosphere, lighting and spatial character",
  "Material / clothing": "apply the referenced material, texture, fibers, finish, colors and physical response to light",
  "Prop / secondary object": "include the referenced prop with its recognizable shape, scale, placement and material",
};

function contain(ctx: CanvasRenderingContext2D, image: HTMLImageElement, x: number, y: number, w: number, h: number) {
  const scale = Math.min(w / image.width, h / image.height);
  const dw = image.width * scale;
  const dh = image.height * scale;
  ctx.drawImage(image, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
}

async function loadImage(src: string) {
  return await new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = src;
  });
}

export default function ReferenceComposerStudio(props: Props) {
  const [slots, setSlots] = useState<Slot[]>(defaults);
  const [prompt, setPrompt] = useState(props.initialPrompt);
  const [status, setStatus] = useState("Ready");
  const [job, setJob] = useState("");
  const [result, setResult] = useState("");
  const [inspect, setInspect] = useState(false);
  const [planning, setPlanning] = useState(false);
  const active = slots.filter((slot) => slot.image);
  const compatible = props.architecture === "Krea-2";

  const composedPrompt = useMemo(() => {
    const references = active.map((slot, index) =>
      `REFERENCE ${index + 1} — ${slot.role} (${slot.influence}% influence): ${roleDirections[slot.role] || "use this reference carefully"}. VISUAL ANALYSIS: ${slot.description || "not analyzed yet"}.`,
    );
    return [
      "Create one unified, coherent, photorealistic scene from the supplied visual references.",
      "Do not reproduce a collage, contact sheet, split screen, labels, borders, or multiple panels. The final result must be one natural photograph.",
      ...references,
      `MAIN CREATIVE INSTRUCTION: ${prompt.trim()}`,
      "Keep perspective, scale, anatomy, contact shadows and material interactions physically believable. Resolve conflicts in favor of the main instruction while preserving the character identity.",
    ].join("\n");
  }, [active, prompt]);

  useEffect(() => {
    if (!job) return;
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`/api/extension-jobs/${job}`);
        const data = await response.json();
        setStatus(data.status || "Generating");
        if (data.status === "complete") {
          window.clearInterval(timer);
          setJob("");
          setResult(data.images?.[0] || data.image || data.output || "");
          setStatus("Complete");
        } else if (data.status === "error" || data.error) {
          window.clearInterval(timer);
          setJob("");
          setStatus(data.error || "Generation failed");
        }
      } catch {
        setStatus("Waiting for Froja engine…");
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [job]);

  const setSlot = (index: number, patch: Partial<Slot>) => setSlots((items) => items.map((item, i) => i === index ? { ...item, ...patch } : item));
  const choose = (index: number, file?: File) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setSlot(index, { image: String(reader.result), name: file.name, description: "", analyzing: false });
    reader.readAsDataURL(file);
  };

  const describeImage = async (image: string) => {
    const response = await fetch("/api/image-to-prompt", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image, model: "qwen3-vl:4b", detail: "balanced" }),
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

  const makeReferenceBoard = async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 1536;
    canvas.height = 1024;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas is unavailable.");
    ctx.fillStyle = "#11171c";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const layouts = [
      [20, 60, 720, 944], [760, 60, 366, 452], [1150, 60, 366, 452],
      [760, 552, 366, 452], [1150, 552, 366, 452],
    ];
    for (let i = 0; i < slots.length; i += 1) {
      const slot = slots[i];
      if (!slot.image) continue;
      const [x, y, w, h] = layouts[i];
      ctx.fillStyle = "#070b0e";
      ctx.fillRect(x, y, w, h);
      contain(ctx, await loadImage(slot.image), x + 8, y + 8, w - 16, h - 16);
      ctx.fillStyle = "rgba(0,0,0,.78)";
      ctx.fillRect(x, y, w, 40);
      ctx.fillStyle = "#eafcff";
      ctx.font = "600 20px Arial";
      ctx.fillText(`REFERENCE ${i + 1}: ${slot.role}`, x + 12, y + 27);
    }
    return canvas.toDataURL("image/png");
  };

  const generate = async () => {
    if (!compatible || !active.length || !prompt.trim() || job) return;
    try {
      setStatus("Preparing five-reference composition…");
      const source = await makeReferenceBoard();
      const response = await fetch("/api/image-tool", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: "krea2-reference", checkpoint: props.checkpoint, source_image: source,
          prompt: composedPrompt, width: props.width, height: props.height,
          seed: props.seed, strength: 1, loras: props.loras,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Reference composition failed.");
      setJob(data.job || data.prompt_id || "");
      setStatus("Queued — combining references…");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Reference composition failed.");
    }
  };

  return <div className="reference-composer-modal" onClick={props.onClose}>
    <section className="reference-composer" onClick={(event) => event.stopPropagation()}>
      <header><div><h2>◈ Froja Reference Composer</h2><p>Combine up to five visual references into one coherent image.</p></div><button className="close" onClick={props.onClose}>×</button></header>
      <div className="reference-status"><span className={compatible ? "ready" : "warning"} /> <b>{compatible ? "Krea-2 multi-reference engine ready" : "Choose a Krea-2 checkpoint in Models"}</b><small>{active.length}/5 references loaded · originals remain untouched</small></div>
      <div className="reference-slot-grid">
        {slots.map((slot, index) => <article key={index} className={slot.image ? "filled" : ""}>
          <label className="reference-drop">
            {slot.image ? <img src={slot.image} alt={slot.role} /> : <span><b>+ Reference {index + 1}</b><small>Drop or choose an image</small></span>}
            <input type="file" accept="image/*" onChange={(event) => choose(index, event.target.files?.[0])} />
          </label>
          <select value={slot.role} onChange={(event) => setSlot(index, { role: event.target.value })}>{defaults.map((item) => <option key={item.role}>{item.role}</option>)}</select>
          <div className="reference-influence"><span>Influence</span><input type="range" min="20" max="100" value={slot.influence} onChange={(event) => setSlot(index, { influence: Number(event.target.value) })} /><b>{slot.influence}%</b></div>
          {slot.image && <div className="reference-analysis">
            <button onClick={() => analyzeSlot(index)} disabled={slot.analyzing}>{slot.analyzing ? "Analyzing…" : slot.description ? "Analyze again" : "Analyze with Ollama"}</button>
            <textarea value={slot.description} onChange={(event) => setSlot(index, { description: event.target.value })} placeholder="Ollama's editable description of this reference…" />
            <button className="remove" onClick={() => setSlot(index, { image: "", name: "", description: "", analyzing: false })}>Remove</button>
          </div>}
        </article>)}
      </div>
      <div className="reference-workbench">
        <div><div className="reference-ai-actions"><button onClick={analyzeAll} disabled={!active.length}>1 · Analyze all references</button><button onClick={planScene} disabled={planning || !active.some((slot) => slot.description) || !prompt.trim()}>{planning ? "Planning…" : "2 · Suggest composition with Ollama"}</button></div><label>Main creative instruction / composed scene<textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Describe the final unified scene…" /></label><details><summary>View generated multi-reference instruction</summary><pre>{composedPrompt}</pre></details></div>
        <aside><b>Output</b><span>{props.width} × {props.height}</span><span>{props.architecture || "No model"}</span><span>{props.loras.length} active LoRA{props.loras.length === 1 ? "" : "s"}</span><button className="primary" disabled={!compatible || !active.length || !prompt.trim() || !!job} onClick={generate}>{job ? status : "Generate Unified Image"}</button><small>{status}</small></aside>
      </div>
      {result && <div className="reference-result"><header><h3>Combined result</h3><a href={result} download>Download</a></header><img src={result} alt="Combined reference result" onClick={() => setInspect(true)} /><small>Click the image to inspect at full size.</small></div>}
    </section>
    {inspect && result && <div className="reference-inspector" onClick={() => setInspect(false)}><img src={result} alt="Full-size combined reference result" /></div>}
  </div>;
}
