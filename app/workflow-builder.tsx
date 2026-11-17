import { Fragment, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { DeckSymbol } from "./tool-deck";
import "./workflow-builder.css";

type Props = { onClose: () => void; checkpoint: string; width: number; height: number; steps: number; cfg: number; sampler: string; negative: string; stylePrompt: string };
type Settings = Omit<Props, "onClose">;
type Saved = { id: string; name: string; prompt: string; picture: string; blocks: string[]; styleOn: boolean; settings: Settings };
type LibraryItem = { name: string; created: string; sample: string; has_sample: boolean; zip: string };
type State = "idle" | "working" | "done" | "failed";
type Step = "picture" | "prompt" | "style" | "generate" | "result";
const steps: Step[] = ["picture", "prompt", "style", "generate", "result"];
const labels = { picture: "Picture", prompt: "Prompt", style: "Style", generate: "Generate", result: "Result" };
const symbols = { picture: "gallery", prompt: "brush", style: "palette", generate: "bolt", result: "gallery" };
const explanations = { picture: "Turn a reference picture into words.", prompt: "Describe the picture you want to make.", style: "Add your current Froja style to the prompt.", generate: "Choose the model and image settings.", result: "Review your test image, then export the pack." };
const initialStates = (): Record<Step, State> => ({ picture: "idle", prompt: "idle", style: "idle", generate: "idle", result: "idle" });
function readSaved(): Saved[] {
  const data: unknown = JSON.parse(localStorage.getItem("froja-workflows") || "[]");
  if (!Array.isArray(data)) throw new Error("Your saved workflows could not be read.");
  return data.filter((x): x is Saved => !!x && typeof x.id === "string" && typeof x.name === "string" && typeof x.prompt === "string" && typeof x.picture === "string" && typeof x.styleOn === "boolean" && Array.isArray(x.blocks) && x.settings && ["checkpoint", "negative", "stylePrompt", "sampler"].every(k => typeof x.settings[k] === "string") && ["width", "height", "steps", "cfg"].every(k => typeof x.settings[k] === "number" && Number.isFinite(x.settings[k])));
}
async function request<T>(url: string, signal: AbortSignal, body?: unknown): Promise<T> {
  const response = await fetch(url, { signal, ...(body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) });
  const data = await response.json().catch(() => { throw new Error("The studio received an unreadable reply. Check that the backend is available."); });
  if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : "The request could not finish. Please try again.");
  return data;
}

export default function WorkflowBuilder({ onClose, ...defaults }: Props) {
  const [settings, setSettings] = useState<Settings>(defaults);
  const [prompt, setPrompt] = useState(""); const [picture, setPicture] = useState(""); const [styleOn, setStyleOn] = useState(true);
  const [states, setStates] = useState(initialStates); const [busy, setBusy] = useState(false); const [packing, setPacking] = useState(false);
  const [message, setMessage] = useState("Start with a picture or write your idea. Your blocks are already connected.");
  const [error, setError] = useState(""); const [result, setResult] = useState("");
  const [tested, setTested] = useState<{ id: string; prompt_id: string } | null>(null);
  const [inventory, setInventory] = useState<string[]>([]); const [engine, setEngine] = useState("Checking engine…");
  const [saved, setSaved] = useState<Saved[]>([]); const [library, setLibrary] = useState(false); const [name, setName] = useState("Untitled workflow");
  const [libraryItems, setLibraryItems] = useState<LibraryItem[]>([]);
  async function refreshLibrary() { try { const data = await request<{items: LibraryItem[]}>("/api/workflow-builder/library", new AbortController().signal); setLibraryItems(data.items); } catch (e) { setError(String(e)); } }
  useEffect(() => { void refreshLibrary(); }, [library]);  // also on first open, so the counter is right
  const controller = useRef<AbortController | null>(null); const input = useRef<HTMLInputElement>(null); const locked = useRef(false);
  useEffect(() => {
    const abort = new AbortController();
    request<{ engine: string; checkpoints: string[] }>("/api/workflow-builder/inventory", abort.signal).then(data => { setInventory(data.checkpoints || []); setEngine(data.engine === "ready" ? "Engine ready" : "Engine offline · try again when available"); }).catch(() => { if (!abort.signal.aborted) setEngine("Engine unavailable · check your backend"); });
    try { setSaved(readSaved()); } catch { setError("Saved workflows are unavailable. Browser storage may be disabled or damaged."); }
    return () => { abort.abort(); controller.current?.abort(); };
  }, []);
  function invalidate() { setTested(null); setResult(""); setStates(initialStates()); setError(""); }
  function update<K extends keyof Settings>(key: K, value: Settings[K]) { invalidate(); setSettings(s => ({ ...s, [key]: value })); }
  function start() { const abort = new AbortController(); controller.current = abort; return abort.signal; }
  async function describe(file?: File) {
    if (!file || locked.current) return;
    if (!file.type.startsWith("image/") || file.size > 15 * 1024 * 1024) { setError("Choose an image smaller than 15 MB."); return; }
    locked.current = true; invalidate(); setBusy(true); setStates(s => ({ ...s, picture: "working" })); setMessage("Reading your picture with Ollama…");
    const signal = start();
    try {
      const image = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error("This picture could not be opened.")); reader.readAsDataURL(file); });
      if (signal.aborted) return;
      setPicture(image);
      const data = await request<{ prompt: string }>("/api/image-to-prompt", signal, { image, model: "qwen3-vl:4b", detail: "balanced" });
      if (!data.prompt?.trim()) throw new Error("No description was returned. Try another picture or write your own prompt.");
      setPrompt(data.prompt); setStates(s => ({ ...s, picture: "done" })); setMessage("Picture described. Refine the prompt, then build your workflow.");
    } catch (e) { if (!signal.aborted) { setError(e instanceof TypeError ? "Could not reach Ollama through the backend. Check the connection and try again." : e instanceof Error ? e.message : "The picture could not be described."); setStates(s => ({ ...s, picture: "failed" })); } }
    finally { if (!signal.aborted) { locked.current = false; setBusy(false); } }
  }
  async function test() {
    if (locked.current) return;
    if (!prompt.trim() || !settings.checkpoint.trim()) { setError("Write a prompt and choose a checkpoint before testing."); return; }
    if (![settings.width, settings.height, settings.steps, settings.cfg].every(n => Number.isFinite(n) && n > 0) || settings.width % 8 || settings.height % 8 || !Number.isInteger(settings.steps)) { setError("Use positive settings, whole steps, and image dimensions divisible by 8."); return; }
    locked.current = true; invalidate(); setBusy(true); const signal = start();
    setStates({ picture: picture ? "done" : "idle", prompt: "done", style: styleOn && settings.stylePrompt ? "done" : "idle", generate: "working", result: "idle" }); setMessage("Building and checking your connected workflow…");
    try {
      const built = await request<{ id: string }>("/api/workflow-builder/build", signal, { ...settings, prompt: [prompt.trim(), styleOn ? settings.stylePrompt : ""].filter(Boolean).join(", "), negative_prompt: settings.negative, scheduler: "normal", seed: Math.floor(Math.random() * 4294967295), loras: [], plan: { name, blocks: steps.filter(s => s !== "picture" || picture), prompt, styleOn, stylePrompt: settings.stylePrompt, pictureSource: picture ? "described reference; text generation only" : null } });
      if (!built.id) throw new Error("The workflow was not created. Please try again.");
      const run = await request<{ prompt_id: string }>("/api/workflow-builder/run", signal, { id: built.id });
      if (!run.prompt_id) throw new Error("The engine did not return a test job. Please try again.");
      setMessage("Generating your test image. You can leave this studio; the engine may keep running.");
      const deadline = Date.now() + 30 * 60 * 1000;
      while (!signal.aborted) {
        await new Promise<void>(resolve => { const done = () => { clearTimeout(timer); signal.removeEventListener("abort", done); resolve(); }; const timer = window.setTimeout(done, 2000); signal.addEventListener("abort", done, { once: true }); });
        if (signal.aborted) return;
        const job = await request<{ status: string; images?: string[]; error?: string }>(`/api/jobs/${encodeURIComponent(run.prompt_id)}`, signal);
        if (job.status === "failed" || job.status === "error") throw new Error(job.error || "The image engine could not finish this test. Check the model and try again.");
        if (job.status === "complete") {
          if (!job.images?.[0]) throw new Error("The test finished without an image. Please try again.");
          setResult(job.images[0]); setTested({ id: built.id, prompt_id: run.prompt_id }); setStates(s => ({ ...s, generate: "done", result: "done" })); setMessage("Test complete. Your workflow pack is ready to download."); return;
        }
        if (Date.now() > deadline) throw new Error("This test is taking longer than 30 minutes. Check the engine before starting another test.");
      }
    } catch (e) { if (!signal.aborted) { setError(e instanceof TypeError ? "Lost contact with the backend. Check the engine before trying again; the job may still be running." : e instanceof Error ? e.message : "The test could not finish."); setStates(s => ({ ...s, generate: "failed", result: "failed" })); } }
    finally { if (!signal.aborted) { locked.current = false; setBusy(false); } }
  }
  async function download() {
    if (!tested || locked.current) return;
    locked.current = true; setPacking(true); setError(""); const signal = start();
    try { const data = await request<{ zip: string }>("/api/workflow-builder/pack", signal, { ...tested, name }); if (!data.zip) throw new Error("The pack was not returned. Please try again."); const link = document.createElement("a"); link.href = data.zip; link.download = `${name || "workflow"}.zip`; document.body.appendChild(link); link.click(); link.remove(); setMessage("Saved in your Workflows folder"); void refreshLibrary(); }
    catch (e) { if (!signal.aborted) setError(e instanceof Error ? e.message : "The pack could not be downloaded."); }
    finally { if (!signal.aborted) { locked.current = false; setPacking(false); } }
  }
  function persist(items: Saved[]) { try { localStorage.setItem("froja-workflows", JSON.stringify(items)); setSaved(items); return true; } catch { setError("Could not save to this browser. Storage may be full; try removing a saved workflow or using a smaller picture."); return false; } }
  function save() { if (!name.trim()) { setError("Give your workflow a name before saving."); return; } try { const item: Saved = { id: crypto.randomUUID(), name: name.trim(), prompt, picture, blocks: steps.filter(s => s !== "picture" || picture), styleOn, settings }; if (persist([...readSaved(), item])) { setLibrary(true); setMessage("Saved in this browser. Open it again from My workflows."); } } catch { setError("Could not read browser storage. Your current workflow is still open."); } }
  function jump(step: Step) { const node = document.getElementById(`wf-${step}`); node?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" }); node?.focus({ preventScroll: true }); }
  const unavailable = busy || packing;
  const content: Record<Step, ReactNode> = {
    picture: <><button className="wf-drop" disabled={unavailable} onClick={() => input.current?.click()} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (!unavailable) void describe(e.dataTransfer.files[0]); }}>{picture ? <img src={picture} alt="Your reference" /> : <><DeckSymbol name="gallery" /><strong>Picture to Workflow</strong><span>Drop a picture or choose a file</span><small>Optional · image files up to 15 MB</small></>}</button><input ref={input} type="file" accept="image/*" hidden onChange={e => { void describe(e.target.files?.[0]); e.target.value = ""; }} />{picture && <button disabled={unavailable} onClick={() => { invalidate(); setPicture(""); }}>Remove picture</button>}<p className="wf-hint">Only its description is used. Your reference is not sent to the image generator.</p></>,
    prompt: <><label htmlFor="wf-prompt-text">Your idea</label><textarea id="wf-prompt-text" disabled={unavailable} value={prompt} placeholder="A quiet coastal house at sunrise, soft light, cinematic photography…" onChange={e => { invalidate(); setPrompt(e.target.value); }} /><small>You can edit the description from your picture.</small></>,
    style: <><label className="wf-toggle"><input type="checkbox" checked={styleOn} disabled={unavailable} onChange={e => { invalidate(); setStyleOn(e.target.checked); }} />Use Froja style</label><div className="wf-style">{settings.stylePrompt || "No style selected in Froja. Your prompt will be used on its own."}</div><small>{styleOn && settings.stylePrompt ? "Added after your prompt." : "This step is bypassed."}</small></>,
    generate: <><label htmlFor="wf-checkpoint">Checkpoint</label><select id="wf-checkpoint" value={settings.checkpoint} disabled={unavailable} onChange={e => update("checkpoint", e.target.value)}><option value="">Choose a model</option>{Array.from(new Set([settings.checkpoint, ...inventory].filter(Boolean))).map(c => <option key={c} value={c}>{c}</option>)}</select><div className="wf-fields">{([ ["width", "Width"], ["height", "Height"], ["steps", "Steps"], ["cfg", "CFG"] ] as const).map(([key, label]) => <label key={key}>{label}<input type="number" disabled={unavailable} min={key === "cfg" ? 0.1 : key === "steps" ? 1 : 8} step={key === "cfg" ? 0.1 : key === "steps" ? 1 : 8} value={settings[key]} onChange={e => update(key, Number(e.target.value))} /></label>)}</div><small>Sampler: {settings.sampler} · random seed</small><details><summary>Negative prompt</summary><textarea aria-label="Negative prompt" value={settings.negative} disabled={unavailable} onChange={e => update("negative", e.target.value)} /></details></>,
    result: result ? <><a href={result} target="_blank" rel="noreferrer"><img className="wf-result" src={result} alt="Workflow test result" /></a><small>Click the picture to open the full image.</small></> : <div className="wf-empty"><DeckSymbol name="gallery" /><strong>{states.generate === "working" ? "Making your picture…" : "Your idea, brought to life"}</strong><span>{states.result === "failed" ? "See the error above and try again." : "Build & Test to see the result here."}</span></div>,
  };
  return <section className="wf-studio" aria-label="Workflow Builder">
    <header className="wf-toolbar"><div><span className="wf-eyebrow">FROJA / WORKFLOW STUDIO</span><h1>From an idea to a repeatable workflow.</h1></div><div className="wf-actions"><button disabled={unavailable} onClick={save}>Save</button><button aria-expanded={library} onClick={() => setLibrary(!library)}>My workflows <span>{libraryItems.length + saved.length}</span></button><button disabled={!tested || unavailable} onClick={download}>{packing ? "Packing…" : "Download Workflow Pack (.zip)"}</button><button className="wf-primary" disabled={unavailable || !prompt.trim()} onClick={test}>{busy ? "Working…" : "▶ Build & Test"}</button><button onClick={onClose} aria-label="Close Workflow Builder">✕</button></div></header>
    <div className="wf-notice" role="status"><span className={busy ? "wf-indicator working" : "wf-indicator"} />{message}<small>{engine}</small></div>{error && <div className="wf-error" role="alert">{error}</div>}
    {library && <section className="wf-library" aria-label="My workflows"><label>Workflow name<input value={name} maxLength={100} disabled={unavailable} onChange={e => setName(e.target.value)} /></label><button disabled={unavailable} onClick={save}>Save a copy</button><h3>Workflows folder</h3><button onClick={() => { request("/api/workflow-builder/library/open", new AbortController().signal, {}).catch(e => setError(String(e))); }}>Open Workflows folder</button>{libraryItems.map(item => <div key={item.name}>{item.has_sample && <img src={item.sample} alt="Workflow sample" style={{width: 96, height: 72, objectFit: "cover"}} />}<strong>{item.name}</strong><span>{new Date(item.created).toLocaleString()}</span><a href={item.zip} download>Download zip</a><button onClick={() => { if (window.confirm(`Delete ${item.name} from your Workflows folder?`)) request("/api/workflow-builder/library/delete", new AbortController().signal, {name: item.name}).then(refreshLibrary).catch(e => setError(String(e))); }}>Delete</button></div>)}<h3>Drafts in this browser</h3><p>Stored only in this browser, including your reference picture.</p>{!saved.length && <p>No saved workflows yet.</p>}{saved.map(item => <div key={item.id}><strong>{item.name}</strong><button disabled={unavailable} onClick={() => { invalidate(); setName(item.name); setPrompt(item.prompt); setPicture(item.picture); setStyleOn(item.styleOn); setSettings(item.settings); setLibrary(false); setMessage("Workflow loaded. Build & Test to make a fresh result."); }}>Load</button><button disabled={unavailable} onClick={() => { try { persist(readSaved().filter(s => s.id !== item.id)); } catch { setError("Could not read saved workflows."); } }}>Delete</button></div>)}</section>}
    <div className="wf-workspace"><aside className="wf-palette"><h2>Building blocks</h2><p>A simple recipe. Already wired for you.</p>{steps.map(step => <button key={step} onClick={() => jump(step)}><DeckSymbol name={symbols[step]} /><span>{labels[step]}<small>{step === "picture" ? "Optional reference" : step === "result" ? "Your test image" : "Ready to use"}</small></span><span>↗</span></button>)}<h2 className="wf-next">Next possibilities</h2>{["Upscale", "Relight", "Repair", "Image to Video"].map(label => <div className="wf-locked" key={label}><span aria-hidden="true">♧</span><span>{label}<small>Locked · coming soon</small></span></div>)}<p className="wf-hint">Version 1 · a fixed chain.<br />No wiring or technical setup needed.</p></aside>
    <main className="wf-canvas"><div className="wf-canvas-heading"><label className="wf-name">Workflow name<input aria-label="Workflow name" disabled={unavailable} value={name} maxLength={100} onChange={e => setName(e.target.value)} /></label><span>01 — IDEA → IMAGE<span className="wf-scroll-hint">Scroll sideways to follow the flow →</span></span></div><div className="wf-chain">{steps.map((step, i) => <Fragment key={step}>{i > 0 && <svg className={`wf-wire ${busy ? "working" : ""}`} viewBox="0 0 48 40" aria-hidden="true"><path d="M0 20 C18 20 30 20 48 20" /><path className="wf-flow" d="M0 20 H48" /><circle cx="4" cy="20" r="3" /><circle cx="44" cy="20" r="3" /></svg>}<article id={`wf-${step}`} tabIndex={-1} className={`wf-node ${states[step]}`}><header><span className="wf-node-icon"><DeckSymbol name={symbols[step]} /></span><h2>{labels[step]}</h2><span className="wf-state">{states[step] === "idle" ? step === "picture" ? "Optional" : "Ready" : states[step] === "working" ? "Working" : states[step] === "done" ? "✓ Done" : "Failed"}</span></header><p>{explanations[step]}</p>{content[step]}<footer>STEP {String(i + 1).padStart(2, "0")}</footer></article></Fragment>)}</div><footer className="wf-guide"><div><b>1. Start with your idea</b><span>Choose a picture or write a prompt.</span></div><div><b>2. Make it yours</b><span>Review the words, style and model.</span></div><div><b>3. Test, then keep it</b><span>Save locally or export a tested workflow pack.</span></div></footer></main></div>
  </section>;
}
