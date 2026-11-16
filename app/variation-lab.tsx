"use client";

import { useEffect, useMemo, useState } from "react";
import "./variation-lab.css";

type Result = { id: string; label: string; prompt: string; job: string; image: string; state: string };
type Props = { onClose: () => void; checkpoint: string; architecture?: string; width: number; height: number; seed: number; loras: { relative: string; strength: number }[] };

const modes = {
  "Controlled redesign": ["sleek industrial redesign", "heavy armored redesign", "retro-futurist redesign", "precision racing redesign", "weathered battlefield redesign", "luxury ceremonial redesign"],
  "New scenarios": ["inside a futuristic hangar", "walking through a rainy neon city", "standing in a desert outpost", "inside a clean engineering laboratory", "guarding an ancient ruined temple", "on a cinematic spacecraft bridge"],
  "Materials & finish": ["brushed titanium and carbon fiber", "weathered bronze and black steel", "white ceramic armor and chrome", "translucent panels with internal light", "matte military composite armor", "polished crimson enamel and gunmetal"],
  "Pose & action": ["neutral full-body character turnaround pose", "powerful walking pose", "defensive action stance", "kneeling for maintenance", "lifting a heavy mechanical object", "three-quarter hero pose"],
  "Camera study": ["front orthographic view", "three-quarter eye-level view", "complete side profile", "low-angle cinematic view", "rear three-quarter view", "close medium portrait showing the upper body"],
};

function readFile(file?: File) {
  return new Promise<string>((resolve, reject) => {
    if (!file) return reject(new Error("Choose a reference image."));
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Froja could not read this image."));
    reader.readAsDataURL(file);
  });
}

export default function VariationLab(props: Props) {
  const [source, setSource] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [mode, setMode] = useState<keyof typeof modes>("Controlled redesign");
  const [instruction, setInstruction] = useState("Preserve the exact robot identity, silhouette, proportions, colors and recognizable mechanical details.");
  const [identity, setIdentity] = useState(88);
  const [results, setResults] = useState<Result[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState("Choose one main reference image.");
  const [inspect, setInspect] = useState("");
  const compatible = props.architecture === "Krea-2";
  const busy = submitting || results.some((item) => item.job);

  const tasks = useMemo(() => modes[mode].map((variation, index) => ({
    label: `${index + 1} · ${variation}`,
    prompt: `Create one finished image, not a collage or reference sheet. Use the uploaded image as the strict primary subject reference. ${instruction.trim()} VARIATION: ${variation}. Identity preservation strength ${identity} percent. Preserve recognisable geometry and design language unless the variation explicitly changes a material or setting. Keep anatomy, perspective, lighting, contact shadows and scale believable. Show one coherent scene only; no panels, captions, borders, text or watermark.`,
  })), [mode, instruction, identity]);

  useEffect(() => {
    if (!results.some((item) => item.job)) return;
    const timer = window.setInterval(async () => {
      const active = results.filter((item) => item.job);
      for (const item of active) {
        try {
          const response = await fetch(`/api/extension-jobs/${item.job}`);
          const data = await response.json();
          if (data.status === "complete") {
            const image = data.images?.[0] || data.image || data.output || "";
            setResults((list) => list.map((entry) => entry.id === item.id ? { ...entry, job: "", image, state: image ? "Complete" : "No image returned" } : entry));
          } else if (data.status === "error" || data.error) {
            setResults((list) => list.map((entry) => entry.id === item.id ? { ...entry, job: "", state: data.error || "Failed" } : entry));
          }
        } catch { /* keep polling while ComfyUI finishes */ }
      }
    }, 1800);
    return () => window.clearInterval(timer);
  }, [results]);

  useEffect(() => {
    if (results.length && !results.some((item) => item.job)) setStatus(`${results.filter((item) => item.image).length} of ${results.length} variations completed.`);
  }, [results]);

  const choose = async (file?: File) => {
    try { setSource(await readFile(file)); setSourceName(file?.name || "Reference"); setResults([]); setStatus("Reference ready. Choose how Froja should transform it."); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Image load failed."); }
  };

  const generate = async () => {
    if (!source || !compatible || busy) return;
    setSubmitting(true);
    setResults(tasks.map((task, index) => ({ id: `${Date.now()}-${index}`, ...task, job: "", image: "", state: "Waiting" })));
    setStatus("Submitting six controlled variations…");
    for (let index = 0; index < tasks.length; index += 1) {
      const task = tasks[index];
      try {
        const response = await fetch("/api/image-tool", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
          mode: "krea2-reference", checkpoint: props.checkpoint, source_image: source, prompt: task.prompt,
          width: props.width, height: props.height, seed: props.seed < 0 ? -1 : props.seed + index, strength: .78,
          loras: props.loras.map((item) => ({ name: item.relative, strength: item.strength })),
        }) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not start variation.");
        setResults((list) => list.map((entry, i) => i === index ? { ...entry, job: data.job || data.prompt_id || "", state: "Generating" } : entry));
      } catch (error) {
        setResults((list) => list.map((entry, i) => i === index ? { ...entry, state: error instanceof Error ? error.message : "Failed" } : entry));
      }
    }
    setSubmitting(false);
    setStatus("Froja is generating the variation board…");
  };

  const continueFrom = (item: Result) => {
    if (!item.image) return;
    setSource(item.image); setSourceName(item.label); setResults([]); setStatus("Selected result is now the main reference. Start another controlled round.");
  };

  return <div className="vl-overlay" onClick={props.onClose}><section className="vl-studio" onClick={(event) => event.stopPropagation()}>
    <header><div><h2>◈ Froja Variation Lab</h2><p>Transform one reference into controlled redesigns, scenarios and visual studies.</p></div><button onClick={props.onClose}>×</button></header>
    <div className="vl-notice"><b>Experimental · identity-first workflow</b><span>Each output is generated separately. Froja does not make a collage and your original stays untouched.</span></div>
    <main>
      <aside className="vl-source"><h3>Main reference</h3><label>{source ? <img src={source} alt="Primary reference" /> : <span><b>+ Add robot, character or object</b><small>PNG, JPEG or WebP</small></span>}<input type="file" accept="image/*" onChange={(event) => choose(event.target.files?.[0])} /></label><small>{sourceName || "No image selected"}</small></aside>
      <section className="vl-controls"><label><span>Creation mode</span><select value={mode} onChange={(event) => setMode(event.target.value as keyof typeof modes)}>{Object.keys(modes).map((item) => <option key={item}>{item}</option>)}</select></label><label><span>Main instruction</span><textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} /></label><label className="vl-range"><span>Keep original identity</span><input type="range" min="55" max="100" value={identity} onChange={(event) => setIdentity(Number(event.target.value))} /><b>{identity}%</b></label><div className="vl-recipes">{tasks.map((task) => <span key={task.label}>{task.label}</span>)}</div><button className="vl-generate" disabled={!source || !compatible || busy} onClick={generate}>{busy ? "Generating variation board…" : "Generate 6 Variations"}</button><small>{compatible ? status : "Choose a Krea-2 checkpoint in Froja Models first."}</small></section>
    </main>
    <section className="vl-board">{results.length ? results.map((item) => <article key={item.id}><header><b>{item.label}</b><small>{item.state}</small></header><div>{item.image ? <img src={item.image} alt={item.label} onClick={() => setInspect(item.image)} /> : <span className={item.job ? "working" : ""}>◈</span>}</div>{item.image && <footer><button onClick={() => setInspect(item.image)}>Zoom</button><button onClick={() => continueFrom(item)}>Use as next reference</button><a href={item.image} download>Download</a></footer>}</article>) : <div className="vl-empty"><b>Your six-image comparison board appears here</b><span>Choose a mode to explore the same design without replacing your original.</span></div>}</section>
  </section>{inspect && <div className="vl-inspect" onClick={() => setInspect("")}><img src={inspect} alt="Variation full-size preview" /></div>}</div>;
}
