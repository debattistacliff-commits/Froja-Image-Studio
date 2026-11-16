import { useEffect, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";

/** A light placed in 3D around the subject. azimuth: 0 = from the camera, 90 = right, 180 = behind, 270 = left. */
export type StageLight = { id: string; name: string; on: boolean; azimuth: number; elevation: number; intensity: number; color: string; softness: "soft" | "hard" };

export const DEFAULT_LIGHTS: StageLight[] = [
  { id: "key", name: "Key", on: true, azimuth: 300, elevation: 30, intensity: 85, color: "#fff1dc", softness: "soft" },
  { id: "fill", name: "Fill", on: false, azimuth: 60, elevation: 10, intensity: 35, color: "#dfe9ff", softness: "soft" },
  { id: "rim", name: "Rim", on: false, azimuth: 165, elevation: 35, intensity: 70, color: "#9fd3ff", softness: "hard" },
];

const COLOURS = [
  { label: "Candle", value: "#ffa84d" },
  { label: "Tungsten", value: "#ffcf9e" },
  { label: "Daylight", value: "#fff6e8" },
  { label: "Cool", value: "#cfe3ff" },
  { label: "Cyan", value: "#46d9ff" },
  { label: "Pink", value: "#ff4fd8" },
];

type Preset = { name: string; ambient: number; lights: Partial<StageLight>[] };
const PRESETS: Preset[] = [
  { name: "Rembrandt", ambient: 8, lights: [{ on: true, azimuth: 315, elevation: 40, intensity: 90, color: "#ffe6c4", softness: "soft" }, { on: false }, { on: false }] },
  { name: "Butterfly", ambient: 15, lights: [{ on: true, azimuth: 0, elevation: 60, intensity: 85, color: "#fff6e8", softness: "soft" }, { on: true, azimuth: 0, elevation: -20, intensity: 25, color: "#fff6e8", softness: "soft" }, { on: false }] },
  { name: "Split", ambient: 4, lights: [{ on: true, azimuth: 270, elevation: 10, intensity: 95, color: "#fff6e8", softness: "hard" }, { on: false }, { on: false }] },
  { name: "Rim light", ambient: 6, lights: [{ on: true, azimuth: 330, elevation: 25, intensity: 50, color: "#fff1dc", softness: "soft" }, { on: false }, { on: true, azimuth: 165, elevation: 35, intensity: 90, color: "#cfe3ff", softness: "hard" }] },
  { name: "Golden hour", ambient: 18, lights: [{ on: true, azimuth: 250, elevation: 8, intensity: 90, color: "#ffa84d", softness: "soft" }, { on: true, azimuth: 70, elevation: 20, intensity: 25, color: "#cfe3ff", softness: "soft" }, { on: false }] },
  { name: "Neon", ambient: 6, lights: [{ on: true, azimuth: 280, elevation: 15, intensity: 85, color: "#ff4fd8", softness: "soft" }, { on: true, azimuth: 80, elevation: 15, intensity: 80, color: "#46d9ff", softness: "soft" }, { on: false }] },
];

const rad = (deg: number) => (deg * Math.PI) / 180;
const sideName = (az: number) => (az < 30 || az > 330 ? "front" : az < 150 ? "right" : az < 210 ? "behind" : "left");

export default function LightStage({ image, lights, ambient, onLights, onAmbient }: {
  image: string;
  lights: StageLight[];
  ambient: number;
  onLights: (lights: StageLight[]) => void;
  onAmbient: (ambient: number) => void;
}) {
  const [selected, setSelected] = useState("key");
  const [lightMap, setLightMap] = useState("");
  const plate = useRef<HTMLDivElement>(null);
  const light = lights.find((l) => l.id === selected) || lights[0];

  // The light map shown in the preview is the very same one IC-Light receives.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetch("/api/relight/light-map", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lights, ambient }) })
        .then((r) => r.json()).then((d) => d.image && setLightMap(d.image)).catch(() => undefined);
    }, 120);
    return () => window.clearTimeout(timer);
  }, [lights, ambient]);

  const update = (id: string, patch: Partial<StageLight>) => onLights(lights.map((l) => (l.id === id ? { ...l, ...patch } : l)));

  const dragOnPlate = (event: ReactPointerEvent<HTMLDivElement>) => {
    const box = plate.current?.getBoundingClientRect();
    if (!box) return;
    const dx = (event.clientX - (box.left + box.width / 2)) / (box.width / 2);
    const dy = (event.clientY - (box.top + box.height / 2)) / (box.height / 2);
    const az = ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
    update(selected, { azimuth: Math.round(az), on: true });
  };

  const applyPreset = (preset: Preset) => {
    onAmbient(preset.ambient);
    onLights(lights.map((l, i) => ({ ...l, ...(preset.lights[i] || {}) })));
  };

  return (
    <section className="light-stage">
      <div className="ls-room">
        <div className="ls-wall" />
        <div className="ls-plate" ref={plate}
          onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); dragOnPlate(e); }}
          onPointerMove={(e) => { if (e.currentTarget.hasPointerCapture(e.pointerId)) dragOnPlate(e); }}>
          <span className="ls-mark front">CAMERA</span><span className="ls-mark back">BACK</span>
          <span className="ls-mark left">LEFT</span><span className="ls-mark right">RIGHT</span>
          {lights.map((l) => {
            const x = 50 + 44 * Math.sin(rad(l.azimuth));
            const y = 50 + 44 * Math.cos(rad(l.azimuth));
            return (
              <div key={l.id} className={`ls-lamp ${l.on ? "on" : "off"} ${l.id === selected ? "picked" : ""}`}
                style={{ left: `${x}%`, top: `${y}%`, "--lamp": l.color, "--h": `${Math.max(0, l.elevation + 30) * 1.1}px` } as CSSProperties}
                onPointerDown={(e) => { e.stopPropagation(); setSelected(l.id); }}>
                <i className="ls-stand" />
                <b className="ls-bulb" title={`${l.name} light`}><em>{l.name[0]}</em></b>
              </div>
            );
          })}
          <div className="ls-subject">{image ? <img src={image} alt="" draggable={false} /> : <span>Your picture</span>}</div>
        </div>
        <small className="ls-help">Drag on the floor to move the {light.name.toLowerCase()} light around the subject</small>
      </div>

      <div className="ls-preview">
        <div className="ls-photo">
          {image ? <img src={image} alt="Picture to relight" /> : <span>Choose a picture to light</span>}
          {image && lightMap && <img className="ls-shade" src={lightMap} alt="" />}
          {image && lightMap && <img className="ls-glow" src={lightMap} alt="" />}
        </div>
        <div className="ls-map">{lightMap && <img src={lightMap} alt="Light map sent to IC-Light" />}<small>Light map · what IC-Light receives</small></div>
      </div>

      <div className="ls-controls">
        <div className="ls-presets">{PRESETS.map((p) => <button key={p.name} onClick={() => applyPreset(p)}>{p.name}</button>)}</div>
        <div className="ls-tabs">
          {lights.map((l) => (
            <button key={l.id} className={l.id === selected ? "selected" : ""} onClick={() => setSelected(l.id)}>
              <span className="ls-dot" style={{ background: l.on ? l.color : "#2a2c30" }} />{l.name}
            </button>
          ))}
        </div>
        <label className="style-enable-switch ls-onoff"><span>{light.name} light {light.on ? "on" : "off"}</span>
          <input type="checkbox" checked={light.on} onChange={(e) => update(light.id, { on: e.target.checked })} /></label>
        <p className="ls-where">From the <b>{sideName(light.azimuth)}</b> · {light.azimuth}° around · {light.elevation}° high</p>
        <label className="ls-row"><span>Height</span><input type="range" min={-30} max={85} value={light.elevation} onChange={(e) => update(light.id, { elevation: +e.target.value })} /><b>{light.elevation}°</b></label>
        <label className="ls-row"><span>Around</span><input type="range" min={0} max={359} value={light.azimuth} onChange={(e) => update(light.id, { azimuth: +e.target.value })} /><b>{light.azimuth}°</b></label>
        <label className="ls-row"><span>Strength</span><input type="range" min={0} max={100} value={light.intensity} onChange={(e) => update(light.id, { intensity: +e.target.value })} /><b>{light.intensity}%</b></label>
        <div className="ls-row"><span>Light</span>
          <div className="ls-toggle">
            <button className={light.softness === "soft" ? "selected" : ""} onClick={() => update(light.id, { softness: "soft" })}>Soft</button>
            <button className={light.softness === "hard" ? "selected" : ""} onClick={() => update(light.id, { softness: "hard" })}>Hard</button>
          </div>
        </div>
        <div className="ls-row"><span>Colour</span>
          <div className="ls-colours">
            {COLOURS.map((c) => <button key={c.value} title={c.label} aria-label={c.label} className={`ls-swatch ${light.color === c.value ? "picked" : ""}`} style={{ background: c.value }} onClick={() => update(light.id, { color: c.value })} />)}
            <input type="color" value={light.color} onChange={(e) => update(light.id, { color: e.target.value })} aria-label="Any colour" />
          </div>
        </div>
        <label className="ls-row"><span>Room light</span><input type="range" min={0} max={60} value={ambient} onChange={(e) => onAmbient(+e.target.value)} /><b>{ambient}%</b></label>
      </div>
    </section>
  );
}
