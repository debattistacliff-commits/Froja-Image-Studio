import { useEffect, useState } from "react";
import "./civitai-panel.css";
type Target = { kind: "loras" | "checkpoints"; relative: string };
type Info = { found: boolean; model_name: string; version_name: string; creator: string; type: string; base_model: string; trained_words: string[]; model_url: string; images: string[] };
type Progress = { running: boolean; done: number; total: number; found: number; current: string };
async function api(url: string, body?: unknown) {
  const response = await fetch(url, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
export default function CivitaiPanel({ target, onClose, onAdd }: { target: Target; onClose: () => void; onAdd: (words: string) => void }) {
  const [enabled, setEnabled] = useState<boolean | null>(null), [key, setKey] = useState("");
  const [info, setInfo] = useState<Info | null>(null), [error, setError] = useState(""), [loading, setLoading] = useState(false), [saving, setSaving] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null), [notice, setNotice] = useState("");
  useEffect(() => { let alive = true; api("/api/civitai/settings").then(d => { if (alive) setEnabled(d.enabled); }).catch(e => { if (alive) setError(e.message); }); return () => { alive = false; }; }, []);
  useEffect(() => {
    if (!enabled) return;
    let alive = true; setLoading(true); setInfo(null); setError("");
    api(`/api/civitai/info?kind=${target.kind}&relative=${encodeURIComponent(target.relative)}`).then(d => { if (alive) setInfo(d); }).catch(e => { if (alive) setError(e.message); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [enabled, target.kind, target.relative]);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const poll = () => api("/api/civitai/scan").then(d => { if (alive) setProgress(d); }).catch(() => {});
    void poll(); const timer = window.setInterval(poll, 1500); return () => { alive = false; clearInterval(timer); };
  }, [enabled]);
  async function settings(next: boolean) { setSaving(true); setError(""); try { const d = await api("/api/civitai/settings", { enabled: next, ...(key ? { api_key: key } : {}) }); setKey(""); setEnabled(d.enabled); } catch (e) { setError(String(e)); } finally { setSaving(false); } }
  return <div className="civitai-overlay" onClick={onClose}><section className="civitai-panel" role="dialog" aria-modal="true" aria-label="Civitai model information" onClick={e => e.stopPropagation()}><header><h2>ⓘ Civitai</h2><button onClick={onClose}>Close</button></header><p>Froja sends only a file fingerprint (hash) to civitai.com to find the model page. Your files and your name are never sent.</p>{error && <p role="alert">{error}</p>}{enabled === null ? <p>Checking settings…</p> : <><label className="civitai-switch"><input type="checkbox" checked={enabled} disabled={saving} onChange={e => void settings(e.target.checked)} />Turn on Civitai link</label>{!enabled && <label>Optional API key<input type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} /></label>}{enabled && <><button disabled={progress?.running} onClick={() => { api("/api/civitai/scan", { kind: "loras" }).then(setProgress).catch(e => setError(e.message)); }}>Scan all LoRAs</button>{progress && <p aria-live="polite">{progress.running ? "Scanning" : "Scan progress"}: {progress.done}/{progress.total} · {progress.found} found {progress.current}</p>}{loading && <p role="status">Reading the file fingerprint… (large files take a few minutes)</p>}{info && (info.found ? <><div className="civitai-pictures">{info.images.map(src => <a href={src} target="_blank" rel="noreferrer" key={src}><img src={src} alt="Civitai model sample" /></a>)}</div><h3>{info.model_name} · {info.version_name}</h3><p>by {info.creator || "unknown"}</p><p>{info.type} · {info.base_model}</p><div className="civitai-words">{info.trained_words.map(word => <button key={word} title="Copy trigger word" onClick={() => { navigator.clipboard.writeText(word).then(() => setNotice("Copied")).catch(() => setError("Could not copy trigger word")); }}>{word}</button>)}</div>{target.kind === "loras" && info.trained_words.length > 0 && <button onClick={() => { onAdd(info.trained_words.join(", ")); setNotice("Added to prompt"); }}>Add to prompt</button>}<p>{notice}</p><a href={info.model_url} target="_blank" rel="noopener noreferrer">Open on Civitai ↗</a></> : <p>No matching model was found on Civitai.</p>)}</>}</>}</section></div>;
}
