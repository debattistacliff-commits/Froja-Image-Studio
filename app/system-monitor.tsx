import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

type Gpu = { name: string; temp: number | null; load: number | null; vram_used_mb: number | null; vram_total_mb: number | null; power_w: number | null; fan: number | null };
type Advice = { level: "info" | "warn" | "danger"; text: string };
type SystemData = {
  cpu: { temp?: number | null; temp_source?: "cpu" | "board" | "none"; load?: number; cores?: number };
  ram: { used_gb?: number; total_gb?: number; percent?: number };
  gpus: Gpu[];
  drives: { name: string; free_gb: number; total_gb: number; percent: number }[];
  advice: Advice[];
};
export type MonitoredModel = { name: string; size: number; architecture: string } | undefined;

/** Plain-language checks for the model that is selected right now. */
function modelAdvice(model: MonitoredModel, gpu?: Gpu): Advice[] {
  if (!model) return [];
  const out: Advice[] = [];
  const gb = model.size / 2 ** 30;
  const vram = (gpu?.vram_total_mb || 0) / 1024;
  if (vram && gb > vram * 1.05) {
    out.push({ level: "warn", text: `The selected model (${gb.toFixed(1)} GB) is bigger than your graphics card (${vram.toFixed(0)} GB). It will run slowly or may fail. A GGUF, Q4 or FP8 version of the same model will fit better.` });
  } else if (vram && gb > vram * 0.85) {
    out.push({ level: "info", text: `The selected model (${gb.toFixed(1)} GB) nearly fills your ${vram.toFixed(0)} GB graphics card. Keep the image size moderate and avoid many LoRAs at once.` });
  }
  if (model.architecture === "Checkpoint" || !model.architecture) {
    out.push({ level: "info", text: `Froja cannot tell which family "${model.name}" belongs to. If it fails, choose a model marked Krea-2, Flux, SDXL or Z-Image.` });
  }
  return out;
}

const level = (value: number | null | undefined, warn: number, danger: number) =>
  value === null || value === undefined ? "" : value >= danger ? "danger" : value >= warn ? "warn" : "";

export default function SystemMonitor({ model }: { model?: MonitoredModel }) {
  const [data, setData] = useState<SystemData | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () => {
      if (document.hidden) return;
      fetch("/api/system").then((r) => (r.ok ? r.json() : null)).then((d) => { if (alive && d) setData(d); }).catch(() => undefined);
    };
    load();
    const timer = window.setInterval(load, 4000);
    return () => { alive = false; window.clearInterval(timer); };
  }, []);

  if (!data) return null;
  const gpu = data.gpus[0];
  const vramUsed = (gpu?.vram_used_mb || 0) / 1024, vramTotal = (gpu?.vram_total_mb || 0) / 1024;
  const vramPct = vramTotal ? (vramUsed / vramTotal) * 100 : 0;
  const advice = [...modelAdvice(model, gpu), ...data.advice];
  const worst = advice.some((a) => a.level === "danger") ? "danger" : advice.some((a) => a.level === "warn") ? "warn" : "";
  const cpuTempLabel = data.cpu.temp_source === "cpu" ? "CPU" : "Board";

  return (
    <>
      <button className={`sysmon-strip ${worst}`} onClick={() => setOpen(true)} title="System monitor — click for details">
        <span className={level(data.cpu.load, 85, 97)}><i>CPU</i><b>{Math.round(data.cpu.load || 0)}%</b></span>
        {gpu && <span className={level(gpu.temp, 76, 83)}><i>GPU</i><b>{gpu.temp ?? "–"}°</b></span>}
        {gpu && <span className={level(vramPct, 101, 101)}><i>VRAM</i><b>{vramUsed.toFixed(1)}/{vramTotal.toFixed(0)}</b></span>}
        <span className={level(data.ram.percent, 90, 97)}><i>RAM</i><b>{Math.round(data.ram.percent || 0)}%</b></span>
        {worst && <em className="sysmon-alert" aria-label="Warnings">!</em>}
      </button>

      {open && (
        <div className="sysmon-modal" onClick={() => setOpen(false)}>
          <section className="sysmon-panel" onClick={(e) => e.stopPropagation()} aria-label="System monitor">
            <header>
              <h2>System</h2>
              <small>Live · updates every few seconds</small>
              <button className="sysmon-close" onClick={() => setOpen(false)} aria-label="Close">✕</button>
            </header>
            <div className="sysmon-gauges">
              <Gauge label="CPU load" value={data.cpu.load || 0} text={`${Math.round(data.cpu.load || 0)}%`} sub={`${data.cpu.cores || "?"} threads`} cls={level(data.cpu.load, 85, 97)} />
              <Gauge label={`${cpuTempLabel} temp`} value={data.cpu.temp ?? 0} max={100} text={data.cpu.temp != null ? `${Math.round(data.cpu.temp)}°C` : "–"} sub={data.cpu.temp_source === "cpu" ? "CPU package" : "motherboard sensor"} cls={data.cpu.temp_source === "cpu" ? level(data.cpu.temp, 85, 92) : ""} />
              {gpu && <Gauge label="GPU temp" value={gpu.temp || 0} max={100} text={`${gpu.temp ?? "–"}°C`} sub={`fan ${gpu.fan ?? 0}% · ${Math.round(gpu.power_w || 0)} W`} cls={level(gpu.temp, 76, 83)} />}
              {gpu && <Gauge label="GPU load" value={gpu.load || 0} text={`${Math.round(gpu.load || 0)}%`} sub={gpu.name.replace("NVIDIA GeForce ", "")} cls="" />}
              {gpu && <Gauge label="VRAM" value={vramPct} text={`${vramUsed.toFixed(1)} GB`} sub={`of ${vramTotal.toFixed(0)} GB`} cls="" />}
              <Gauge label="RAM" value={data.ram.percent || 0} text={`${Math.round(data.ram.percent || 0)}%`} sub={`${data.ram.used_gb} / ${data.ram.total_gb} GB`} cls={level(data.ram.percent, 90, 97)} />
            </div>
            <h3>Drives</h3>
            <div className="sysmon-drives">
              {data.drives.map((d) => (
                <div key={d.name} className={`sysmon-drive ${level(d.percent, 88, 95)}`}>
                  <b>{d.name}</b>
                  <span className="bar"><span style={{ width: `${d.percent}%` }} /></span>
                  <small>{d.free_gb >= 1024 ? `${(d.free_gb / 1024).toFixed(1)} TB` : `${Math.round(d.free_gb)} GB`} free of {d.total_gb >= 1024 ? `${(d.total_gb / 1024).toFixed(1)} TB` : `${Math.round(d.total_gb)} GB`}</small>
                </div>
              ))}
            </div>
            <h3>Advice</h3>
            <ul className="sysmon-advice">
              {advice.length === 0 && <li className="ok">Everything looks healthy.</li>}
              {advice.map((a, i) => <li key={i} className={a.level}>{a.text}</li>)}
            </ul>
          </section>
        </div>
      )}
    </>
  );
}

function Gauge({ label, value, max = 100, text, sub, cls }: { label: string; value: number; max?: number; text: string; sub: string; cls: string }) {
  const pct = Math.max(0, Math.min(1, value / max));
  return (
    <div className={`sysmon-gauge ${cls}`} style={{ "--p": pct } as CSSProperties}>
      <div className="ring"><b>{text}</b></div>
      <span>{label}</span>
      <small>{sub}</small>
    </div>
  );
}
