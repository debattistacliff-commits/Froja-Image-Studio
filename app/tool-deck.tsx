import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";

/** Glowing line symbols for the tool slides (24x24 viewBox, stroke only). */
const SYMBOLS: Record<string, string[]> = {
  eye: ["M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12Z", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z"],
  atom: ["M12 12m-1.6 0a1.6 1.6 0 1 0 3.2 0a1.6 1.6 0 1 0-3.2 0", "M12 3c5 0 9 4 9 9s-4 9-9 9-9-4-9-9", "M7.5 4.2c4.3-2.5 9.8-1 12.3 3.3", "M4.2 16.5c-2.5-4.3-1-9.8 3.3-12.3"],
  layers: ["m12 3 9 5-9 5-9-5 9-5Z", "m3 12 9 5 9-5", "m3 16 9 5 9-5"],
  bolt: ["M13 2 4 14h7l-1 8 9-12h-7l1-8Z"],
  hexdots: ["M7 6h.01", "M12 6h.01", "M17 6h.01", "M7 12h.01", "M12 12h.01", "M17 12h.01", "M4 3h16v18H4z"],
  nodes: ["M5 5h4v4H5z", "M15 15h4v4h-4z", "M15 3h4v4h-4z", "M9 7h6", "M17 7v8", "M7 9v6a2 2 0 0 0 2 2h6"],
  queue: ["M4 6h11", "M4 12h11", "M4 18h7", "m16 15 5 3-5 3v-6Z"],
  portrait: ["M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z", "M4 21c1-4.5 4.2-7 8-7s7 2.5 8 7", "M19 3v4", "M17 5h4"],
  sphere: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z", "M7.5 8.5a5 5 0 0 1 4-2.5"],
  target: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z", "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z", "M12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z"],
  cube: ["m12 2 9 5v10l-9 5-9-5V7l9-5Z", "m3 7 9 5 9-5", "M12 12v10"],
  compose: ["M3 3h11v11H3z", "M10 10h11v11H10z"],
  database: ["M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3Z", "M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6", "M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"],
  zoomplus: ["M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15Z", "m21 21-5.2-5.2", "M10.5 7.5v6", "M7.5 10.5h6"],
  swap: ["M3 4h8v8H3z", "M13 12h8v8h-8z", "M15 4h3a2 2 0 0 1 2 2v3", "m18 7 2 2 2-2", "M9 20H6a2 2 0 0 1-2-2v-3", "m6 17-2-2-2 2"],
  brush: ["M18.4 2.6a2 2 0 0 1 2.9 2.9L11 15.8 8.2 13 18.4 2.6Z", "M7 14.5c-2 0-3.5 1.6-3.5 3.5 0 1.2-.5 2-1.5 2.5 3.5 1 7-.5 7-4l-2-2Z"],
  face: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z", "M9 10h.01", "M15 10h.01", "M8.5 14.5c1.8 2 5.2 2 7 0"],
  cycle: ["M20 12a8 8 0 0 1-14 5.3", "M4 12A8 8 0 0 1 18 6.7", "M18 2v5h-5", "M6 22v-5h5"],
  pose: ["M12 2.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z", "M5 9l7 1 7-1", "M12 10v5", "m12 15-4 6", "m12 15 4 6"],
  sun: ["M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z", "M12 2v2", "M12 20v2", "m4.9 4.9 1.4 1.4", "m17.7 17.7 1.4 1.4", "M2 12h2", "M20 12h2", "m4.9 19.1 1.4-1.4", "m17.7 6.3 1.4-1.4"],
  wrench: ["M14.7 6.3a4 4 0 0 0 5 5L21 13l-8 8-3-3 6.3-6.3", "M14.7 6.3 9 12", "M3 21l6-6", "M14.7 6.3a4 4 0 0 1 5-3.2l-2.6 2.6.5 2.1 2.1.5 2.6-2.6"],
  wand: ["m4 20 11-11", "m13 7 4 4", "M18 2v3", "M16.5 3.5h3", "M21 8v2", "M20 9h2", "M9 3v2", "M8 4h2"],
  film: ["M3 5h18v14H3z", "M7 5v14", "M17 5v14", "M3 9h4", "M3 15h4", "M17 9h4", "M17 15h4", "m10.5 9.5 3.5 2.5-3.5 2.5v-5Z"],
  power: ["M12 3v8", "M6.3 6.8a8 8 0 1 0 11.4 0"],
  camera: ["M4 8h3l2-3h6l2 3h3v11H4z", "M12 10a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"],
  palette: ["M12 3a9 9 0 1 0 0 18c1.1 0 1.6-.8 1.6-1.6 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0-.9.7-1.6 1.6-1.6H16a5 5 0 0 0 5-5c0-4-4-7.4-9-7.4Z", "M7.5 11h.01", "M10 7h.01", "M14.5 7.5h.01", "M17 11h.01"],
  gallery: ["M3 7h14v12H3z", "M7 3h14v12", "m3 16 4-4 3 3 3-3 4 4"],
  gear: ["M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z", "M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"],
  toolbox: ["M3 8h18v12H3z", "M8 8V5h8v3", "M3 13h18", "M10 13v2h4v-2"],
  library: ["M4 4h4v16H4z", "M10 4h4v16h-4z", "m16 5 3.8-1 3 15.4-3.8 1z"],
};

export function DeckSymbol({ name }: { name: string }) {
  const paths = SYMBOLS[name] || SYMBOLS.wand;
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths.map((d) => <path key={d} d={d} />)}
    </svg>
  );
}

export type DeckTool = {
  name: string;
  cover?: string;
  symbol?: string;
  badge?: string | number;
  description: string;
  icon?: ReactNode;
  open: () => void;
};

/** Skyline-style tool deck: every tool is one slide; slide left/right, then press Open. */
export default function ToolDeck({ tools, onClose, title = "Tools", brand, storageKey = "froja-deck-index", home = false, stay = false, closeLabel = "Close tools", inline = false, actionLabel = "Open", startIndex, topRight }: {
  tools: DeckTool[];
  onClose: () => void;
  title?: string;
  brand?: ReactNode;
  storageKey?: string;
  home?: boolean;   // Froja's home screen: no close button, Esc does nothing
  stay?: boolean;   // keep the deck mounted by the parent after opening (it hides it itself)
  closeLabel?: string;
  inline?: boolean;      // sits inside a page (e.g. the Camera step) instead of covering the screen
  actionLabel?: string;  // text on the power button
  startIndex?: number;   // which slide to show first
  topRight?: ReactNode;  // extra controls in the title bar (e.g. LED colours on the home screen)
}) {
  const [index, setIndex] = useState(() => {
    if (startIndex !== undefined && startIndex >= 0) return Math.min(startIndex, tools.length - 1);
    let saved = 0;
    try { saved = Number(localStorage.getItem(storageKey) || 0); } catch { /* ignore */ }
    return Number.isFinite(saved) ? Math.min(Math.max(saved, 0), tools.length - 1) : 0;
  });
  const touchX = useRef<number | null>(null);
  const wheelLock = useRef(0);

  const go = (step: number) => setIndex((i) => (i + step + tools.length) % tools.length);
  const [launching, setLaunching] = useState(false);
  const openTool = (i: number) => {
    if (launching) return;
    try { localStorage.setItem(storageKey, String(i)); } catch { /* ignore */ }
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce || inline) { if (!home && !stay && !inline) onClose(); setIndex(i); tools[i].open(); return; }
    // The transformation: the slide powers up, flies towards you, and the tool opens behind it.
    setIndex(i);
    setLaunching(true);
    window.setTimeout(() => tools[i].open(), 380);
    window.setTimeout(() => { if (!home && !stay) onClose(); else setLaunching(false); }, 640);
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (launching) return;
      if (event.key === "ArrowRight") go(1);
      else if (event.key === "ArrowLeft") go(-1);
      else if (event.key === "Enter") openTool(index);
      else if (event.key === "Escape" && !home) onClose();
      else return;
      event.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const offset = (i: number) => {
    let d = i - index;
    if (d > tools.length / 2) d -= tools.length;
    if (d < -tools.length / 2) d += tools.length;
    return d;
  };

  return (
    <div
      className={`tool-deck ${home ? "is-home" : ""} ${inline ? "is-inline" : ""} ${launching ? "is-launching" : ""}`}
      role="dialog"
      aria-label={`Froja ${title}`}
      onWheel={(event) => {
        const now = Date.now();
        if (now - wheelLock.current < 280) return;
        const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
        if (Math.abs(delta) < 12) return;
        wheelLock.current = now;
        go(delta > 0 ? 1 : -1);
      }}
      onTouchStart={(event) => { touchX.current = event.touches[0].clientX; }}
      onTouchEnd={(event) => {
        if (touchX.current === null) return;
        const dx = event.changedTouches[0].clientX - touchX.current;
        if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1);
        touchX.current = null;
      }}
    >
      <header className="deck-top">
        <div className="deck-title">
          {brand || <span className="deck-led">FROJA</span>}
          <b>{title}</b>
        </div>
        {topRight && <div className="deck-extra">{topRight}</div>}
        <div className="deck-counter"><span className="deck-led">{String(index + 1).padStart(2, "0")}</span> / {tools.length}</div>
        {!home && !inline && <button className="pebble pebble-small" onClick={onClose} aria-label={closeLabel}>{stay ? "⌂" : "✕"}</button>}
      </header>

      <div className="deck-stage" key="stage">
        <div className="deck-spill" key={`spill-${index}`} />
        {tools.map((tool, i) => {
          const d = offset(i);
          if (Math.abs(d) > 2) return null;
          return (
            <article
              key={tool.name}
              className={`deck-card ${d === 0 ? "is-current" : ""} ${tool.cover || tool.symbol ? "has-cover" : ""}`}
              style={{ "--d": d, "--ad": Math.abs(d), "--s": Math.sign(d) } as CSSProperties}
              onClick={() => (d === 0 ? openTool(i) : setIndex(i))}
              aria-hidden={d !== 0}
            >
              {(tool.cover || tool.symbol) && <div className="deck-cover"><img src={tool.cover || `/covers/tool-${tool.symbol}.webp`} alt="" draggable={false}
                onError={(event) => { const fallback = `/deck-covers/${tool.symbol}.webp`; if (tool.symbol && !event.currentTarget.src.endsWith(fallback)) event.currentTarget.src = fallback; }} /></div>}
              <div className="deck-icon-well" key={d === 0 ? `on-${index}` : "off"}><span className="deck-ring" /><div className="deck-icon">{tool.symbol ? <DeckSymbol name={tool.symbol} /> : tool.icon}</div></div>
              <h2>{tool.name}</h2>
              <p>{tool.description}</p>
              {tool.badge !== undefined && tool.badge !== "" && <span className="deck-slot"><span className="deck-led">{tool.badge}</span></span>}
              {d === 0 && <button className="pebble pebble-open" onClick={(event) => { event.stopPropagation(); openTool(i); }}><span className="open-power"><DeckSymbol name="power" /></span>{actionLabel}</button>}
            </article>
          );
        })}
        <button className="pebble deck-arrow deck-prev" onClick={() => go(-1)} aria-label="Previous tool">‹</button>
        <button className="pebble deck-arrow deck-next" onClick={() => go(1)} aria-label="Next tool">›</button>
      </div>

      {tools.length <= 40 && <nav className="deck-dots" aria-label="All tools">
        {tools.map((tool, i) => (
          <button key={tool.name} className={i === index ? "on" : ""} title={tool.name} onClick={() => setIndex(i)} />
        ))}
      </nav>}
      <p className="deck-hint">Slide with ← → or the mouse wheel · Enter {inline ? "chooses" : "opens"}{home || inline ? "" : " · Esc closes"}</p>
    </div>
  );
}
