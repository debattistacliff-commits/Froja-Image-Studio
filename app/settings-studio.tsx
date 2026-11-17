import { useEffect, useRef, useState, type ReactNode } from "react";
import { LedPicker } from "./stations";
import { DeckSymbol } from "./tool-deck";
import packageInfo from "../package.json";
import "./settings-studio.css";

type Props = {
  ledColor: string; setLedColor: (value: string) => void;
  iconStyle: string; setIconStyle: (value: string) => void;
  fontFamily: string; setFontFamily: (value: string) => void;
  textScale: number; setTextScale: (value: number) => void;
  fontScale: number; setFontScale: (value: number) => void;
  boldText: boolean; setBoldText: (value: boolean) => void;
  uiLanguage: string; setUiLanguage: (value: string) => void;
  pendingBackground: string; setPendingBackground: (value: string) => void;
  customBackground: string; setCustomBackground: (value: string) => void;
  themeFileName: string; setThemeFileName: (value: string) => void;
  themeUploadState: string; setThemeUploadState: (value: string) => void;
  loadThemeBackground: (file?: File) => Promise<void>;
  maintenanceState: string; setMaintenanceState: (value: string) => void;
  refreshLibrary: () => Promise<void>; downloadSettingsBackup: () => void; onClose: () => void;
};
const sections = [
  ["look", "Look & Feel", "palette", "Make Froja comfortable to use."],
  ["background", "Background", "gallery", "Give your workspace a personal backdrop."],
  ["language", "Language", "sphere", "Choose the language for interface labels."],
  ["connections", "Connections", "nodes", "Check the services Froja can use."],
  ["library", "Library & folders", "library", "Keep your local library and settings organised."],
  ["about", "About", "gear", "Your local creative workspace."],
] as const;
type Connection = { text: string; enabled?: boolean; hasKey?: boolean };
async function request(path: string, body?: object) {
  const response = await fetch(path, { signal: AbortSignal.timeout(15000), ...(body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}) });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}
function Setting({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <article className="ss-card"><div className="ss-setting-heading"><h3>{title}</h3><p>{description}</p></div><div className="ss-control">{children}</div></article>;
}
export default function SettingsStudio(p: Props) {
  const [section, setSection] = useState("look");
  const [connections, setConnections] = useState<Record<string, Connection>>({});
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [key, setKey] = useState("");
  const closeRef = useRef<HTMLButtonElement>(null);
  const onClose = useRef(p.onClose); onClose.current = p.onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const escape = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onClose.current(); } };
    window.addEventListener("keydown", escape);
    return () => { window.removeEventListener("keydown", escape); if (previous?.isConnected) previous.focus(); };
  }, []);
  async function check() {
    setChecking(true);
    await Promise.all([
      ["engine", "/api/workflow-builder/inventory"],
      ["ollama", "/api/ollama/status"],
      ["civitai", "/api/civitai/settings"],
      ["minimax", "/api/minimax-video/status"],
    ].map(async ([id, path]) => {
      try {
        const d = await request(path);
        let result: Connection;
        if (id === "engine") result = { text: `${d.engine === "ready" ? "Ready" : "Offline"} · ${typeof d.nodes === "number" ? d.nodes : "Unknown"} nodes` };
        else if (id === "civitai") result = { text: `${d.enabled ? "On" : "Off"} · ${d.has_key ? "Key saved" : "No key saved"}`, enabled: d.enabled === true, hasKey: d.has_key === true };
        else if (id === "minimax") result = { text: `${d.enabled ? "Enabled" : "Disabled"} · ${d.running ? "Running" : "Not running"}. ${Array.isArray(d.missing) && d.missing.length ? `Needs: ${d.missing.join(", ")}.` : d.installed ? "Required model files installed." : "Model installation unknown."} ${d.gpu ? `GPU: ${d.gpu}.` : "No GPU reported."} ${typeof d.label === "string" ? d.label : ""}` };
        else result = { text: d.running ? `Ollama is running · ${(d.models || []).length} model${(d.models || []).length === 1 ? "" : "s"} installed${(d.models || []).length ? ": " + (d.models || []).slice(0, 4).join(", ") : ""}` : "Ollama is not running. Start Ollama to use Prompt Helper, Enhance and Image to Prompt." };
        setConnections(c => ({ ...c, [id]: result }));
      } catch { setConnections(c => ({ ...c, [id]: { text: "Could not check · service unavailable or request blocked." } })); }
    }));
    setChecking(false);
  }
  useEffect(() => { if (section === "connections") void check(); }, [section]);
  async function saveCivitai(enabled: boolean, includeKey = false) {
    setSaving(true);
    try {
      const d = await request("/api/civitai/settings", { enabled, ...(includeKey && key.trim() ? { api_key: key.trim() } : {}) });
      setConnections(c => ({ ...c, civitai: { text: `${d.enabled ? "On" : "Off"} · ${d.has_key ? "Key saved" : "No key saved"}`, enabled: d.enabled === true, hasKey: d.has_key === true } }));
      setKey(""); p.setMaintenanceState("Civitai connection settings saved.");
    } catch { p.setMaintenanceState("Could not save Civitai settings. Check the backend and try again."); }
    finally { setSaving(false); }
  }
  async function action(work: () => void | Promise<void>) {
    try { await work(); } catch { p.setMaintenanceState("The action could not finish. Check the backend and try again."); }
  }
  const active = sections.find(s => s[0] === section)!;
  return <section className="settings-studio" aria-label="Settings studio">
    <header className="ss-header"><div><span className="ss-eyebrow">YOUR WORKSPACE</span><h1>Settings</h1><p>A few thoughtful adjustments. A studio that feels like yours.</p></div><button ref={closeRef} className="ss-close" onClick={p.onClose} aria-label="Close Settings studio">×</button></header>
    <div className="ss-status" role="status">ⓘ {p.maintenanceState || "Appearance changes save automatically on this computer."}</div>
    <div className="ss-layout"><nav className="ss-menu" aria-label="Settings sections">{sections.map(([id, title, icon], index) => <button key={id} aria-current={section === id ? "page" : undefined} onClick={() => setSection(id)}><DeckSymbol name={icon} /><span>{title}</span><small>{String(index + 1).padStart(2, "0")}</small></button>)}<p>LOCAL FIRST<br />Your studio. Your computer.</p></nav>
    <div className="ss-content" key={section}><div className="ss-section-title"><span className="ss-eyebrow">SETTINGS / {String(sections.indexOf(active) + 1).padStart(2, "0")}</span><h2>{active[1]}</h2><p>{active[3]}</p></div>
    {section === "look" && <>
      <Setting title="LED colour" description="Choose the accent light used for highlights, buttons and sliders."><LedPicker value={p.ledColor} onChange={p.setLedColor} /><span className="ss-led-preview">● Studio light</span></Setting>
      <Setting title="Button & icon style" description="Choose crisp outlines or softly raised icons across the studio."><div className="ss-options">{[["outline", "Professional Outline"], ["soft3d", "Soft 3D"]].map(([id, label]) => <button key={id} className={`ss-style-${id}`} aria-pressed={p.iconStyle === id} onClick={() => p.setIconStyle(id)}><DeckSymbol name="gear" />{label}</button>)}</div></Setting>
      <Setting title="Typeface" description="Choose the style of lettering used throughout the interface."><select aria-label="Typeface" value={p.fontFamily} onChange={e => p.setFontFamily(e.target.value)}>{[["modern", "Modern Sans"], ["humanist", "Humanist"], ["classic", "Classic Serif"], ["mono", "Technical Mono"]].map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select><p className="ss-sample">A little imagination goes a long way.</p></Setting>
      <Setting title="Text size" description="Make writing larger or smaller without changing panel dimensions."><label className="ss-range">{p.textScale}%<input aria-label="Text size" type="range" min="90" max="160" step="5" value={p.textScale} onChange={e => p.setTextScale(+e.target.value)} /></label><p className="ss-sample" style={{ fontSize: `${p.textScale / 100}rem` }}>Your next idea starts here.</p></Setting>
      <Setting title="Display size" description="Make the complete interface larger or smaller."><label className="ss-range">{p.fontScale}%<input aria-label="Display size" type="range" min="90" max="140" step="5" value={p.fontScale} onChange={e => p.setFontScale(+e.target.value)} /></label></Setting>
      <Setting title="Bold text" description="Increase the weight of interface labels to make them easier to read."><label className="ss-toggle"><input type="checkbox" role="switch" checked={p.boldText} onChange={e => p.setBoldText(e.target.checked)} />{p.boldText ? "On" : "Off"}</label></Setting>
    </>}
    {section === "background" && <Setting title="Custom background image" description="Choose a PNG, JPEG or WebP up to 20 MB; Froja resizes it automatically."><label className="ss-drop" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); void p.loadThemeBackground(e.dataTransfer.files?.[0]); }}><DeckSymbol name="gallery" /><b>Choose an image or drop it here</b><span>{p.themeUploadState}</span>{p.themeFileName && <small>{p.themeFileName}</small>}<input aria-label="Choose background image" type="file" accept="image/png,image/jpeg,image/webp" onChange={e => { void p.loadThemeBackground(e.target.files?.[0]); e.target.value = ""; }} /></label>{(p.pendingBackground || p.customBackground) && <><img className="ss-background-preview" src={p.pendingBackground || p.customBackground} alt="Custom Froja background preview" /><small>{p.pendingBackground ? "Preview · apply to save this image" : "Current background"}</small><div className="ss-options">{p.pendingBackground && <button onClick={() => { p.setCustomBackground(p.pendingBackground); p.setPendingBackground(""); p.setMaintenanceState("Custom background applied and saved."); }}>Apply Background</button>}<button onClick={() => { p.setPendingBackground(""); p.setCustomBackground(""); p.setThemeFileName(""); p.setThemeUploadState("Choose or drop an image"); p.setMaintenanceState("Custom background removed."); }}>Remove</button></div></>}</Setting>}
    {section === "language" && <Setting title="Interface language" description="Choose the language used for translated interface labels."><select aria-label="Interface language" value={p.uiLanguage} onChange={e => p.setUiLanguage(e.target.value)}>{[["en", "English"], ["pt", "Português"], ["it", "Italiano"], ["es", "Español"], ["fr", "Français"], ["de", "Deutsch"]].map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></Setting>}
    {section === "connections" && <><div className="ss-check"><span>Checks report availability; they do not start services.</span><button disabled={checking || saving} onClick={() => void check()}>{checking ? "Checking…" : "Check again"}</button></div>{[["engine", "Image engine (ComfyUI)", "The image engine turns your prompts and workflows into pictures."], ["ollama", "Ollama", "Ollama provides local language and image-understanding models."], ["civitai", "Civitai link", "Froja sends only a file fingerprint (hash) to civitai.com. Civitai is not available in every country."], ["minimax", "MiniMax video", "Local video generation needs its model files, a compatible GPU and an enabled engine."]].map(([id, title, description]) => <Setting key={id} title={title} description={description}><p className="ss-connection-status" role="status">{connections[id]?.text || "Checking…"}</p>{id === "civitai" && <><label className="ss-toggle"><input type="checkbox" role="switch" aria-label="Civitai link" disabled={saving || checking || connections.civitai?.enabled === undefined} checked={connections.civitai?.enabled ?? false} onChange={e => void saveCivitai(e.target.checked)} />Enable Civitai link</label><label className="ss-key">Optional API key<input type="password" autoComplete="off" value={key} placeholder={connections.civitai?.hasKey ? "A key is saved · enter a replacement" : "Enter a key if needed"} onChange={e => setKey(e.target.value)} /></label><button disabled={saving || checking || !key.trim() || connections.civitai?.enabled === undefined} onClick={() => void saveCivitai(connections.civitai.enabled!, true)}>{saving ? "Saving…" : "Save key"}</button><small>Saved keys are never displayed.</small></>}</Setting>)}</>}
    {section === "library" && <>
      <Setting title="Refresh your library" description="Scan linked folders again to find models, LoRAs and embeddings you have added."><button onClick={() => void action(p.refreshLibrary)}>Refresh models, LoRAs and embeddings</button></Setting>
      <Setting title="Workflows folder" description="Open the local folder where your saved workflows are kept."><button onClick={() => void action(async () => { await request("/api/workflow-builder/library/open", {}); p.setMaintenanceState("Workflows folder opened."); })}>Open Workflows folder ↗</button></Setting>
      <Setting title="Settings backup" description="Download the existing settings and preset backup without copying model files."><button onClick={p.downloadSettingsBackup}>Download Froja settings backup</button></Setting>
      <Setting title="Safe update channel" description="Automatic replacement is disabled until versioned releases and one-click rollback are available."><span className="ss-badge">Manual updates</span></Setting>
    </>}
    {section === "about" && <article className="ss-card ss-about"><span className="ss-eyebrow">MADE FOR YOUR IMAGINATION</span><h3>Froja Image Studio</h3><span className="ss-badge">Version {packageInfo.version}</span><p>A local creative studio for image generation, workflows and your own model library.</p><a href="https://github.com/debattistacliff-commits/Froja-Image-Studio" target="_blank" rel="noopener noreferrer">Visit the GitHub project ↗</a><p className="ss-privacy">ⓘ Everything runs on this computer. Connections are optional.</p></article>}
    </div></div>
  </section>;
}
