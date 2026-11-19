import { useId, useRef, useState } from "react";
import type { CSSProperties, KeyboardEvent, PointerEvent } from "react";
import { GLOBE_CENTER, OrbitScene, dragOrbit, orbitDirection, projectOrbit, wrapAzimuth } from "./orbit-sphere";

/** A light placed in 3D around the subject. azimuth: 0 = from the camera, 90 = right, 180 = behind, 270 = left. */
const LIGHT_TYPES = ["Softbox", "Spot", "Sky"] as const;
type LightType = Lowercase<(typeof LIGHT_TYPES)[number]>;
export type StageLight = { id: string; name: string; on: boolean; azimuth: number; elevation: number; intensity: number; color: string; softness: "soft" | "hard"; type?: LightType };

const LIGHT_SLOTS: StageLight[] = [
  { id: "key", name: "Key", on: true, azimuth: 300, elevation: 30, intensity: 85, color: "#fff1dc", softness: "soft", type: "softbox" },
  { id: "fill", name: "Fill", on: false, azimuth: 60, elevation: 10, intensity: 35, color: "#dfe9ff", softness: "soft", type: "softbox" },
  { id: "rim", name: "Rim", on: false, azimuth: 165, elevation: 35, intensity: 70, color: "#9fd3ff", softness: "hard", type: "spot" },
];
export const DEFAULT_LIGHTS: StageLight[] = LIGHT_SLOTS.slice(0, 1);

const COLOURS = [
  { label: "Warm white", value: "#fff1dc" },
  { label: "Daylight", value: "#ffffff" },
  { label: "Amber", value: "#ffb454" },
  { label: "Red", value: "#ff6561" },
  { label: "Blue", value: "#76a9ff" },
  { label: "Pink", value: "#f78fcd" },
];

type Preset = { name: string; ambient: number; lights: Partial<StageLight>[] };
const PRESETS: Preset[] = [
  { name: "Rembrandt", ambient: 8, lights: [{ on: true, azimuth: 315, elevation: 40, intensity: 90, color: "#ffe6c4", softness: "soft" }, { on: false }, { on: false }] },
  { name: "Butterfly", ambient: 15, lights: [{ on: true, azimuth: 0, elevation: 60, intensity: 85, color: "#fff6e8", softness: "soft" }, { on: true, azimuth: 0, elevation: -20, intensity: 25, color: "#fff6e8", softness: "soft" }, { on: false }] },
  { name: "Split", ambient: 4, lights: [{ on: true, azimuth: 270, elevation: 10, intensity: 95, color: "#fff6e8", softness: "hard" }, { on: false }, { on: false }] },
  { name: "Rim", ambient: 6, lights: [{ on: true, azimuth: 330, elevation: 25, intensity: 50, color: "#fff1dc", softness: "soft" }, { on: false }, { on: true, azimuth: 165, elevation: 35, intensity: 90, color: "#cfe3ff", softness: "hard" }] },
  { name: "Golden hour", ambient: 18, lights: [{ on: true, azimuth: 250, elevation: 8, intensity: 90, color: "#ffa84d", softness: "soft" }, { on: true, azimuth: 70, elevation: 20, intensity: 25, color: "#cfe3ff", softness: "soft" }, { on: false }] },
  { name: "Neon", ambient: 6, lights: [{ on: true, azimuth: 280, elevation: 15, intensity: 85, color: "#ff4fd8", softness: "soft" }, { on: true, azimuth: 80, elevation: 15, intensity: 80, color: "#46d9ff", softness: "soft" }, { on: false }] },
];

const clampElevation = (elevation: number) => Math.max(-30, Math.min(85, Math.round(elevation)));
const lightType = (light: StageLight): LightType => light.softness === "hard" ? "spot" : light.type === "sky" ? "sky" : "softbox";

function projectLight(light: StageLight) {
  return { light, ...projectOrbit(light) };
}

function LampHead({ position, selected, beamId }: {
  position: ReturnType<typeof projectLight>;
  selected: boolean;
  beamId: string;
}) {
  const { light, x, y, behind } = position;
  const dx = GLOBE_CENTER - x;
  const dy = GLOBE_CENTER - y;
  const distance = Math.hypot(dx, dy);
  const angle = Math.atan2(dy, dx) * 180 / Math.PI;
  const spread = light.softness === "hard" ? 20 : 39;
  const size = (selected ? 1 : 0.7) * (behind ? 0.85 : 1);
  const opacity = (selected ? 1 : 0.5) * (behind ? 0.55 : 1) * (light.on ? 1 : 0.54);

  return (
    <g transform={`translate(${x} ${y}) rotate(${angle})`} opacity={opacity}>
      {selected && light.on && light.intensity > 0 && (
        <path className="ls-beam" d={`M 4 -8 L ${distance + 17} ${-spread} L ${distance + 17} ${spread} L 4 8 Z`}
          fill={`url(#${beamId})`} opacity={0.25 + light.intensity / 140} />
      )}
      <g className="ls-lamp-head" transform={`scale(${size})`} style={{ "--lamp-color": light.color } as CSSProperties}>
        <path className="ls-lamp-body" d="M -13 -10 L 7 -12 V 12 L -13 9 Z" />
        <path className="ls-lamp-side" d="M -13 -10 L -18 -5 V 10 L -13 9 Z" />
        <path className="ls-lamp-side" d="M -13 9 L 7 12 L 3 16 L -18 10 Z" />
        <path className="ls-lamp-face" d="M 7 -12 L 10 -8 V 13 L 7 12 Z" />
      </g>
    </g>
  );
}

function LightPreview({ light, ambient }: { light: StageLight; ambient: number }) {
  const { x, y, z } = orbitDirection(light);
  const intensity = light.on ? light.intensity : 0;
  const shadowShift = 1 - y * 0.55;
  const style = {
    "--highlight-x": `${50 + x * 39}%`,
    "--highlight-y": `${48 - y * 39 - z * 8}%`,
    "--highlight-color": `color-mix(in srgb, ${light.color} 34%, #fff)`,
    "--highlight-strength": intensity * (0.67 + z * 0.33) / 100,
    "--highlight-size": light.softness === "hard" ? "46%" : "70%",
    "--ambient-level": Math.round(46 + ambient / 2),
    "--shadow-x": `${50 - x * 30 * shadowShift}%`,
    "--shadow-y": `${45 + z * 22 * shadowShift}%`,
    "--shadow-strength": 0.3 + intensity / 180,
  } as CSSProperties;

  return <div className="ls-light-preview" style={style} aria-hidden="true"><i /><b /></div>;
}

function LightSlider({ label, value, min = 0, max = 100, unit = "%", onChange }: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  unit?: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="ls-slider">
      <span className="ls-slider-label"><span>{label}</span><b aria-hidden="true">{value}{unit}</b></span>
      <input type="range" min={min} max={max} value={value} aria-valuetext={`${value}${unit}`}
        style={{ "--range-fill": `${(value - min) * 100 / (max - min)}%` } as CSSProperties}
        onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

export default function LightStage({ image, lights, ambient, onLights, onAmbient }: {
  image: string;
  lights: StageLight[];
  ambient: number;
  onLights: (lights: StageLight[]) => void;
  onAmbient: (ambient: number) => void;
}) {
  const stageId = useId();
  const beamId = `${stageId}-beam`;
  const pictureId = `${stageId}-picture`;
  const helpId = `${stageId}-help`;
  const [selectedId, setSelectedId] = useState(DEFAULT_LIGHTS[0].id);
  const drag = useRef<{ pointerId: number; x: number; y: number; light: StageLight } | null>(null);
  const selectedIndex = Math.max(0, lights.findIndex((light) => light.id === selectedId));
  const light = lights[selectedIndex];
  const currentType = light && lightType(light);
  const positions = lights.map(projectLight).sort((a, b) => a.depth - b.depth);

  const update = (id: string, patch: Partial<StageLight>) => {
    onLights(lights.map((item) => item.id === id ? { ...item, ...patch } : item));
  };

  const addLight = () => {
    if (lights.length >= LIGHT_SLOTS.length) return;
    const slot = LIGHT_SLOTS.find((candidate) => !lights.some((item) => item.id === candidate.id));
    if (!slot) return;
    const next = lights[0]
      ? { ...slot, on: true, azimuth: wrapAzimuth(lights[0].azimuth + 180), color: "#ffffff" }
      : { ...slot, on: true };
    onLights([...lights, next]);
    setSelectedId(next.id);
  };

  const applyPreset = (preset: Preset) => {
    const lastActive = preset.lights.reduce((last, settings, index) => settings.on ? index : last, 0);
    const nextLights = LIGHT_SLOTS.slice(0, Math.max(lights.length, lastActive + 1)).map((slot, index) => {
      const settings = preset.lights[index];
      const next = { ...(lights[index] ?? slot), ...settings };
      if (settings.softness) next.type = settings.softness === "hard" ? "spot" : "softbox";
      return next;
    });
    onAmbient(preset.ambient);
    onLights(nextLights);
    setSelectedId(nextLights[0].id);
  };

  const setType = (type: LightType) => {
    if (type === "sky") {
      update(light.id, {
        type,
        softness: "soft",
        elevation: Math.max(60, light.elevation),
        color: light.color.toLowerCase() === "#ffffff" ? "#dceaff" : light.color,
      });
      return;
    }
    update(light.id, { type, softness: type === "spot" ? "hard" : "soft" });
  };

  const startDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (!light || event.button !== 0 || drag.current) return;
    event.currentTarget.focus();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, light };
  };

  const moveLight = (event: PointerEvent<HTMLDivElement>) => {
    const start = drag.current;
    if (!start || start.pointerId !== event.pointerId) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const { azimuth, elevation } = dragOrbit(start.light, event.clientX - start.x, event.clientY - start.y, bounds);
    update(start.light.id, { azimuth: wrapAzimuth(azimuth), elevation: clampElevation(elevation) });
  };

  const endDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (drag.current?.pointerId === event.pointerId) drag.current = null;
  };

  const moveLightWithKeys = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!light) return;
    switch (event.key) {
      case "ArrowLeft": update(light.id, { azimuth: wrapAzimuth(light.azimuth - 5) }); break;
      case "ArrowRight": update(light.id, { azimuth: wrapAzimuth(light.azimuth + 5) }); break;
      case "ArrowUp": update(light.id, { elevation: clampElevation(light.elevation + 5) }); break;
      case "ArrowDown": update(light.id, { elevation: clampElevation(light.elevation - 5) }); break;
      default: return;
    }
    event.preventDefault();
  };

  const renderLamps = (behind: boolean) => positions.filter((position) => position.behind === behind).map((position) => (
    <LampHead key={position.light.id} position={position} selected={position.light.id === light?.id} beamId={beamId} />
  ));

  return (
    <section className="light-stage" id="relight-light-controls" aria-label="Relight light controls"
      onKeyDown={(event) => { if (event.key.startsWith("Arrow") || event.key === "Enter") event.stopPropagation(); }}>
      <div className="ls-panel">
        <div className="ls-tabs" role="group" aria-label="Lights">
          {lights.map((item, index) => (
            <div className="ls-light-tab" key={item.id} data-selected={index === selectedIndex}>
              <button className="ls-tab-label" type="button" aria-pressed={index === selectedIndex} onClick={() => setSelectedId(item.id)}>
                Light {index + 1}
              </button>
              <button className="ls-light-switch" type="button" aria-label={`Light ${index + 1} power`} aria-pressed={item.on}
                title={`Turn light ${index + 1} ${item.on ? "off" : "on"}`}
                style={{ "--lamp-color": item.color } as CSSProperties} onClick={() => update(item.id, { on: !item.on })}>
                <span />
              </button>
            </div>
          ))}
          <button className="ls-add-light" type="button" aria-label="Add light" title="Add light" disabled={lights.length >= LIGHT_SLOTS.length} onClick={addLight}>+</button>
        </div>

        <div className="ls-stage-section">
          <div className="ls-globe" tabIndex={light ? 0 : undefined} role="group" aria-describedby={helpId}
            aria-label={light ? `Light ${selectedIndex + 1} direction. Azimuth ${light.azimuth}°, height ${light.elevation}°. Use arrow keys to adjust.` : "Light direction"}
            aria-keyshortcuts="ArrowLeft ArrowRight ArrowUp ArrowDown"
            onPointerDown={startDrag} onPointerMove={moveLight} onLostPointerCapture={endDrag} onKeyDown={moveLightWithKeys}>
            <svg viewBox="0 0 360 360" aria-hidden="true">
              <defs>
                <linearGradient id={beamId}>
                  <stop stopColor="#fff" stopOpacity="0.54" />
                  <stop offset="0.56" stopColor="#fff" stopOpacity="0.22" />
                  <stop offset="1" stopColor="#fff" stopOpacity="0" />
                </linearGradient>
              </defs>
              <OrbitScene image={image} pictureId={pictureId} behind={renderLamps(true)} />
              {renderLamps(false)}
            </svg>
          </div>
          <p className="ls-help" id={helpId}>Hold and drag to change light direction</p>
        </div>

        {light && <>
          <div className="ls-type-row">
            <div>
              <h3>Light type</h3>
              <div className="ls-segments" role="group" aria-label="Light type">
                {LIGHT_TYPES.map((label) => {
                  const type = label.toLowerCase() as LightType;
                  return <button type="button" key={type} aria-pressed={currentType === type} onClick={() => setType(type)}>{label}</button>;
                })}
              </div>
            </div>
            <LightPreview light={light} ambient={ambient} />
          </div>

          <div className="ls-colour-row">
            <div>
              <h3>Light color</h3>
              <div className="ls-colours">
                <input className="ls-custom-colour" type="color" value={light.color} aria-label="Custom light color" title="Custom light color"
                  onChange={(event) => update(light.id, { color: event.target.value })} />
                <div className="ls-swatches" role="group" aria-label="Light color swatches">
                  {COLOURS.map(({ label, value }) => (
                    <button type="button" key={value} className="ls-swatch" style={{ "--swatch": value } as CSSProperties} title={label}
                      aria-label={label} aria-pressed={light.color.toLowerCase() === value} onClick={() => update(light.id, { color: value })} />
                  ))}
                </div>
              </div>
            </div>
            <div>
              <h3>Shadow edge</h3>
              <div className="ls-edges" role="group" aria-label="Shadow edge">
                <button type="button" aria-pressed={light.softness === "soft"} onClick={() => { if (light.softness !== "soft") setType("softbox"); }}>Soft</button>
                <button type="button" aria-pressed={light.softness === "hard"} onClick={() => setType("spot")}>Hard</button>
              </div>
            </div>
          </div>

          <div className="ls-sliders">
            <LightSlider label="Brightness" value={light.intensity} onChange={(intensity) => update(light.id, { intensity })} />
            <LightSlider label="Height" value={light.elevation} min={-30} max={85} unit="°" onChange={(elevation) => update(light.id, { elevation })} />
          </div>
        </>}
      </div>

      <div className="ls-presets" role="group" aria-label="Lighting presets">
        {PRESETS.map((preset) => <button type="button" key={preset.name} onClick={() => applyPreset(preset)}>{preset.name}</button>)}
      </div>
      <div className="ls-ambient">
        <LightSlider label="Ambient" value={ambient} max={60} onChange={onAmbient} />
      </div>
    </section>
  );
}

