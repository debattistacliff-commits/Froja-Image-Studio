import { useEffect, useState } from "react";
import "./studio-4d-animate.css";

const DEFAULT_PROMPT = "gentle natural motion: clouds drift, water shimmers, leaves and hair move in a light breeze, soft light changes, subtle slow camera push-in";
const REAL_PROMPT = "The person smiles naturally, turns their head slightly and looks back at the camera, with small natural gestures. The background moves gently: leaves sway, light flickers. Realistic motion, steady camera.";
const REAL_SOUND = "gentle natural ambience matching the scene";

const PRESETS = [
  ["orbit", "Orbit"],
  ["push-in", "Push-in"],
  ["crane", "Crane"],
  ["bullet-time", "Bullet-time"],
] as const;

type Preset = typeof PRESETS[number][0];
export type AnimateView = { azimuth: number; image: string };
export type AnimateRequest =
  | { mode: "real"; prompt: string; sound: string; seconds: number }
  | { mode: "life"; prompt: string; protect: boolean; protect_words?: string }
  | { mode: "camera"; preset: Preset; views?: string[]; azimuths?: number[] };
export type AnimateResult = { video: string; blender: string | null; upscaler: string | null };
type AnimateStatus = {
  status: "running" | "complete" | "failed" | "stopped";
  progress: string;
  error: string | null;
  video: string | null;
  blender: string | null;
  upscaler: string | null;
};
type MiniMaxStatus = {
  enabled: boolean;
  installed: boolean;
  supported: boolean;
  missing: string[];
  label: string;
  max_seconds: number;
};

const pollInterval = () => new Promise<void>((resolve) => window.setTimeout(resolve, 1000));

async function animationResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => { throw new Error("Could not reach Froja’s animation API."); });
  if (!response.ok) throw new Error(data.error || "Froja could not process the animation request.");
  return data;
}

export async function requestAnimation(
  image: string,
  request: AnimateRequest,
  signal: AbortSignal,
  onQueued: (id: string | undefined) => void,
  onProgress: (message: string) => void,
): Promise<AnimateResult> {
  signal.throwIfAborted();
  // Keep the submission alive long enough to get a job ID if Stop is pressed while uploading.
  const { job_id } = await animationResponse<{ job_id: string }>(await fetch("/api/animate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image, ...request }),
    signal: AbortSignal.timeout(90_000),
  }));
  if (!job_id) throw new Error("Froja did not return an animation job.");
  onQueued(job_id);
  const url = `/api/animate/${encodeURIComponent(job_id)}`;
  while (true) {
    signal.throwIfAborted();
    const status = await animationResponse<AnimateStatus>(await fetch(url, { signal }));
    if (status.status !== "running") {
      onQueued(undefined);
      if (status.status === "complete" && status.video) {
        return { video: status.video, blender: status.blender, upscaler: status.upscaler };
      }
      throw new Error(status.error || status.progress || "The animation ended without a video.");
    }
    onProgress(status.progress);
    await pollInterval();
  }
}

export async function stopAnimationJob(id: string) {
  const signal = AbortSignal.timeout(90_000);
  const url = `/api/animate/${encodeURIComponent(id)}`;
  let status = await animationResponse<AnimateStatus>(await fetch(`${url}/stop`, { method: "POST", signal }));
  while (status.status === "running") {
    await pollInterval();
    status = await animationResponse<AnimateStatus>(await fetch(url, { signal }));
  }
}

export function AnimateControls({ hasMaster, views, busy, onAnimate, onMakeViews }: {
  hasMaster: boolean;
  views: AnimateView[];
  busy: boolean;
  onAnimate: (request: AnimateRequest) => void;
  onMakeViews: () => void;
}) {
  const [realPrompt, setRealPrompt] = useState(REAL_PROMPT);
  const [sound, setSound] = useState(REAL_SOUND);
  const [seconds, setSeconds] = useState(3);
  const [h3, setH3] = useState<MiniMaxStatus>();
  const [h3Error, setH3Error] = useState("");
  const [enablingH3, setEnablingH3] = useState(false);
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [protect, setProtect] = useState(true);
  const [objects, setObjects] = useState("");
  const [preset, setPreset] = useState<Preset>("orbit");
  const needsViews = preset === "orbit" || preset === "bullet-time";
  const disabled = busy || !hasMaster;
  const h3Available = h3?.installed && h3.supported;
  const realDisabled = disabled || !h3Available || !h3?.enabled;

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/minimax-video/status", { signal: controller.signal })
      .then(animationResponse<MiniMaxStatus>)
      .then(setH3)
      .catch(() => { if (!controller.signal.aborted) setH3Error("Could not check MiniMax H3 availability."); });
    return () => controller.abort();
  }, []);

  async function enableH3() {
    setEnablingH3(true);
    setH3Error("");
    try {
      const response = await fetch("/api/minimax-video/enable", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: true }),
      });
      setH3(await animationResponse<MiniMaxStatus>(response));
    } catch (error) {
      setH3Error(error instanceof Error ? error.message : "Could not switch on MiniMax H3.");
    } finally {
      setEnablingH3(false);
    }
  }

  return <div className="studio-4d-animate">
    <form className="studio-4d-form studio-4d-animate-card studio-4d-animate-real" onSubmit={(event) => {
      event.preventDefault();
      if (!realDisabled) onAnimate({ mode: "real", prompt: realPrompt, sound, seconds });
    }}>
      <h3>Real motion (H3)</h3>
      {h3 ? <p className="studio-4d-help">
        {!h3.installed ? `MiniMax H3 is not installed. Missing ${h3.missing.join(", ")}.`
          : h3.supported ? `${h3.label}. Froja sharpens the video automatically.` : h3.label}
      </p> : !h3Error && <p className="studio-4d-help">Checking MiniMax H3…</p>}
      {h3Error && <p role="alert" className="studio-4d-help studio-4d-animate-warning">{h3Error}</p>}
      {h3Available && !h3?.enabled && <label className="studio-4d-animate-protect">
        <input type="checkbox" role="switch" checked={enablingH3} disabled={busy || enablingH3} onChange={() => void enableH3()} />
        {enablingH3 ? "Switching on MiniMax H3…" : "Switch on MiniMax H3"}
      </label>}
      <label>Motion prompt
        <textarea rows={4} value={realPrompt} onChange={(event) => setRealPrompt(event.target.value)} maxLength={2000} disabled={realDisabled} />
      </label>
      <label>Sound (optional)
        <input value={sound} maxLength={500} disabled={realDisabled} onChange={(event) => setSound(event.target.value)} />
      </label>
      {h3Available && h3 && <label>Duration
        <select value={seconds} disabled={realDisabled} onChange={(event) => setSeconds(Number(event.target.value))}>
          {Array.from({ length: h3.max_seconds }, (_, index) => index + 1).map((value) =>
            <option key={value} value={value}>{value} {value === 1 ? "second" : "seconds"}</option>)}
        </select>
      </label>}
      <button type="submit" className="studio-4d-primary" disabled={realDisabled}>Animate real motion</button>
    </form>

    <form className="studio-4d-form studio-4d-animate-card" onSubmit={(event) => {
      event.preventDefault();
      if (!disabled) onAnimate({ mode: "life", prompt, protect, protect_words: protect ? objects.trim() || undefined : undefined });
    }}>
      <h3>Bring to life (fast · background only)</h3>
      <label>Motion prompt
        <textarea rows={4} value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={2000} disabled={disabled} />
      </label>
      <label className="studio-4d-animate-protect">
        <input type="checkbox" role="switch" checked={protect} disabled={disabled}
          onChange={(event) => setProtect(event.target.checked)} />
        Protect the person
      </label>
      {protect ? <label>Also protect (optional)
        <input value={objects} maxLength={500} placeholder="e.g. the guitar" disabled={disabled}
          onChange={(event) => setObjects(event.target.value)} />
      </label> : <p role="status" className="studio-4d-help studio-4d-animate-warning">The face may change.</p>}
      <button type="submit" className="studio-4d-primary" disabled={disabled}>Animate (≈3 min)</button>
    </form>

    <form className="studio-4d-form studio-4d-animate-card" onSubmit={(event) => {
      event.preventDefault();
      if (disabled || (needsViews && views.length < 3)) return;
      onAnimate(needsViews ? {
        mode: "camera", preset,
        views: views.map(({ image }) => image), azimuths: views.map(({ azimuth }) => azimuth),
      } : { mode: "camera", preset });
    }}>
      <h3>Camera move</h3>
      <div className="studio-4d-pills" role="group" aria-label="Camera move preset">
        {PRESETS.map(([value, label]) => <button key={value} type="button" aria-pressed={preset === value}
          disabled={busy} onClick={() => setPreset(value)}>{label}</button>)}
      </div>
      <p className="studio-4d-help">Orbit and Bullet-time use the camera views you made.</p>
      {needsViews && views.length < 3 ? <>
        <p className="studio-4d-help">Add views from at least three different angles, including the master.</p>
        <button type="button" onClick={onMakeViews} disabled={busy}>Make 360° views first</button>
      </> : <button type="submit" className="studio-4d-primary" disabled={disabled}>Animate camera move</button>}
    </form>
  </div>;
}

export function AnimationPreview({ result }: { result: AnimateResult }) {
  return <>
    <div className="studio-4d-preview studio-4d-animation-preview">
      <video aria-label="Animation preview" src={result.video} controls loop playsInline preload="metadata" />
    </div>
    <div className="studio-4d-actions studio-4d-animation-downloads">
      <a href={result.video} download="froja-animation.mp4">Download video</a>
      {result.blender && <a href={result.blender} download="froja-camera.py">Download camera for Blender (.py)</a>}
      {result.upscaler && <span className="studio-4d-help">Upscaled 2× with {result.upscaler}</span>}
    </div>
  </>;
}
