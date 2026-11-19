import { useEffect, useRef, useState, type Dispatch, type PointerEvent, type SetStateAction } from "react";
import { downloadImageZip, IMAGE_TYPES, openPicture, readImage, requestImage, type ImageJob } from "./image-jobs";
import "./spin-360.css";

const SPIN_PLAN = [
  { angle: 45, instruction: "rotate_right_45", guide: null },
  { angle: 90, instruction: "rotate_right_90", guide: 45 },
  { angle: 315, instruction: "rotate_left_45", guide: 45 },
  { angle: 270, instruction: "rotate_left_90", guide: 315 },
  { angle: 135, instruction: "rear_right", guide: 90 },
  { angle: 225, instruction: "rear_left", guide: 270 },
  { angle: 180, instruction: "back", guide: 90 },
] as const;
const VIEW_COUNT = SPIN_PLAN.length + 1;
const DRAG_STEP = 44;
const VIEW_TIMEOUT_MS = 8 * 60_000;
const INITIAL_VIEW_MS = 4 * 60_000;

export type SpinFrame = { angle: number; image: string };
export type CameraPosition = { azimuth: number; elevation: "low" | "eye" | "high"; distance: "wide" | "medium" | "closeup" };
type SpinRequest = {
  image: string;
  instruction: typeof SPIN_PLAN[number]["instruction"];
  seed: number;
  guide_image?: string;
};

export async function generateView(
  payload: SpinRequest | (CameraPosition & { image: string; guide_image?: string }),
  signal: AbortSignal,
  onQueued?: (job: ImageJob) => void,
) {
  return readImage(await requestImage({ endpoint: "/api/camera-view", engine: "main", payload, signal, onQueued }));
}

export async function generateSpin(
  source: string,
  generate: (request: SpinRequest, number: number, total: number) => Promise<string>,
  onFrame: (frame: SpinFrame) => void,
  shouldStop: () => boolean,
) {
  const seed = crypto.getRandomValues(new Uint32Array(1))[0];
  const generated = new Map<number, string>();
  for (const { angle, instruction, guide } of SPIN_PLAN) {
    if (shouldStop()) break;
    const image = await generate({
      image: source, instruction, seed, guide_image: guide === null ? undefined : generated.get(guide),
    }, generated.size + 2, VIEW_COUNT);
    generated.set(angle, image);
    onFrame({ angle, image });
  }
}

export function SpinViewer({ frames, current, setCurrent, open = true, sourceLabel = "Original picture", onDownload }: {
  frames: SpinFrame[];
  current: number;
  setCurrent: Dispatch<SetStateAction<number>>;
  open?: boolean;
  sourceLabel?: string;
  onDownload?: () => void;
}) {
  const frameCount = frames.length;
  const [autoRotate, setAutoRotate] = useState(false);
  const drag = useRef<{ pointer: number; x: number } | null>(null);
  const currentFrame = frames.find((frame) => frame.angle === current);

  useEffect(() => {
    if (!open || !autoRotate || frames.length < 2) return;
    const timer = window.setInterval(() => {
      setCurrent((angle) => frames[(frames.findIndex((frame) => frame.angle === angle) + 1) % frames.length].angle);
    }, 700);
    return () => window.clearInterval(timer);
  }, [open, autoRotate, frames, setCurrent]);

  function turn(steps: number) {
    if (frameCount < 2) return;
    setCurrent((angle) => {
      const index = frames.findIndex((frame) => frame.angle === angle);
      return frames[((index + steps) % frameCount + frameCount) % frameCount].angle;
    });
  }

  function dragView(event: PointerEvent<HTMLDivElement>) {
    const start = drag.current;
    if (!start || start.pointer !== event.pointerId) return;
    const steps = Math.trunc((start.x - event.clientX) / DRAG_STEP);
    if (steps === 0) return;
    start.x -= steps * DRAG_STEP;
    turn(steps);
  }

  return (
    <>
      <div
        className="spin-360-stage"
        data-draggable={frameCount > 1}
        tabIndex={frameCount > 1 ? 0 : undefined}
        role="group"
        aria-label="Spin viewer. Drag or use the left and right arrow keys to rotate."
        onKeyDown={(event) => {
          if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
          event.preventDefault();
          setAutoRotate(false);
          turn(event.key === "ArrowLeft" ? -1 : 1);
        }}
        onPointerDown={(event) => {
          if (frameCount < 2 || !event.isPrimary || event.button !== 0) return;
          setAutoRotate(false);
          drag.current = { pointer: event.pointerId, x: event.clientX };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={dragView}
        onLostPointerCapture={() => { drag.current = null; }}
      >
        {currentFrame ? <img src={currentFrame.image} alt={current === 0 ? sourceLabel : `AI camera view at ${current}°`} draggable={false} />
          : <p>Choose a picture to start.</p>}
        {frameCount > 0 && (
          <div className="spin-360-angle" role="img" aria-label={`Requested angle ${current} degrees`}>
            <span className="spin-360-dial" aria-hidden="true">
              <i style={{ transform: `rotate(${current}deg)` }} />
            </span>
            <span>{current}°</span>
          </div>
        )}
      </div>
      <div className="spin-360-toolbar spin-360-controls">
        <button type="button" className="spin-360-icon" aria-label="Previous view" disabled={frameCount < 2} onClick={() => { setAutoRotate(false); turn(-1); }}>‹</button>
        <button type="button" className="spin-360-icon" aria-label="Next view" disabled={frameCount < 2} onClick={() => { setAutoRotate(false); turn(1); }}>›</button>
        <label className="spin-360-auto">
          <input type="checkbox" disabled={frameCount < 2} checked={autoRotate} onChange={(event) => setAutoRotate(event.target.checked)} />
          Auto-rotate
        </label>
        {onDownload && frameCount === VIEW_COUNT && <button type="button" className="spin-360-download" onClick={onDownload}>Download all views (.zip)</button>}
      </div>
      {frameCount > 0 && (
        <div className="spin-360-frames" role="group" aria-label="Available views">
          {frames.map(({ angle, image }) => (
            <button key={angle} type="button" aria-label={angle === 0 ? "Original view, 0 degrees" : `View at ${angle} degrees`}
              aria-pressed={current === angle} onClick={() => { setAutoRotate(false); setCurrent(angle); }}>
              <img src={image} alt="" draggable={false} />
              <span>{angle}°</span>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

export default function Spin360({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [sourceName, setSourceName] = useState("");
  const [frames, setFrames] = useState<SpinFrame[]>([]);
  const [current, setCurrent] = useState(0);
  const [viewerVersion, setViewerVersion] = useState(0);
  const [phase, setPhase] = useState<"idle" | "loading" | "generating" | "stopping">("idle");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [timing, setTiming] = useState({ started: 0, average: INITIAL_VIEW_MS });
  const [clock, setClock] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const run = useRef<{ controller: AbortController; stop: boolean } | null>(null);
  const generating = phase === "generating" || phase === "stopping";
  const frameCount = frames.length;

  useEffect(() => {
    const element = dialog.current;
    if (open && !element?.open) element?.showModal();
    if (!open && element?.open) element.close();
  }, [open]);

  useEffect(() => () => run.current?.controller.abort(), []);

  useEffect(() => {
    if (!open || !generating) return;
    const timer = window.setInterval(() => setClock(performance.now()), 1_000);
    return () => window.clearInterval(timer);
  }, [open, generating]);

  async function choosePicture(file: File) {
    setError("");
    setPhase("loading");
    try {
      const image = await openPicture(file);
      setFrames([{ angle: 0, image }]);
      setSourceName(file.name);
      setCurrent(0);
      setViewerVersion((version) => version + 1);
      setNotice("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not open this picture.");
    } finally {
      setPhase("idle");
    }
  }

  async function makeSpin() {
    const source = frames[0];
    if (!source || run.current) return;
    const active = { controller: new AbortController(), stop: false };
    run.current = active;
    let lastArrival = 0;
    let elapsed = 0;
    let completed = 1;
    setFrames([source]);
    setCurrent(0);
    setViewerVersion((version) => version + 1);
    setNotice("");
    setError("");
    setPhase("generating");

    try {
      await generateSpin(source.image, async (request) => {
        const started = performance.now();
        setClock(started);
        setTiming({ started, average: completed > 1 ? elapsed / (completed - 1) : INITIAL_VIEW_MS });
        const timeout = AbortSignal.timeout(VIEW_TIMEOUT_MS);
        const image = await generateView(
          request,
          AbortSignal.any([active.controller.signal, timeout]),
        );
        active.controller.signal.throwIfAborted();
        elapsed += performance.now() - started;
        completed += 1;
        return image;
      }, (frame) => {
        setFrames((views) => [...views, frame].sort((left, right) => left.angle - right.angle));
        const previousArrival = lastArrival;
        setCurrent((selected) => selected === previousArrival ? frame.angle : selected);
        lastArrival = frame.angle;
      }, () => active.stop);
      setNotice(completed === VIEW_COUNT ? "All 8 views ready." : `Stopped · ${completed} of ${VIEW_COUNT} views ready.`);
    } catch (failure) {
      if (!active.controller.signal.aborted) {
        setError(failure instanceof DOMException && failure.name === "TimeoutError"
          ? "This view took too long. Check the engine before trying again."
          : failure instanceof Error ? failure.message : "Could not generate the spin.");
      }
    } finally {
      run.current = null;
      if (!active.controller.signal.aborted) setPhase("idle");
    }
  }

  function stopSpin() {
    if (!run.current) return;
    run.current.stop = true;
    setPhase("stopping");
  }

  async function downloadViews() {
    setError("");
    try {
      await downloadImageZip(frames.map(({ angle, image }) => ({ name: `view-${String(angle).padStart(3, "0")}`, image })), "froja-360-spin.zip");
    } catch {
      setError("Could not prepare the ZIP file.");
    }
  }

  const remaining = Math.max(0, timing.average - (clock - timing.started)) +
    Math.max(0, VIEW_COUNT - frameCount - 1) * timing.average;
  const minutes = Math.max(1, Math.round(remaining / 60_000));
  const progress = phase === "stopping" ? "Stopping after this view…"
    : phase === "generating" ? `View ${Math.min(frameCount + 1, VIEW_COUNT)} of ${VIEW_COUNT} · about ${minutes} min left`
      : notice;

  return (
    <dialog
      className="spin-360"
      ref={dialog}
      aria-labelledby="spin-360-title"
      onKeyDown={(event) => event.stopPropagation()}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header className="spin-360-header">
        <div>
          <h2 id="spin-360-title">360° Spin</h2>
          <p>Sides and back are imagined by AI; small details may change between angles.</p>
        </div>
        <button type="button" className="spin-360-icon" aria-label="Close 360° Spin" onClick={onClose}>×</button>
      </header>
      <div className="spin-360-toolbar">
        <label className="spin-360-picker">
          <input type="file" accept={IMAGE_TYPES.join(",")} disabled={phase !== "idle"} onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void choosePicture(file);
          }} />
          <span>Choose picture</span>
        </label>
        {sourceName && <span className="spin-360-filename" title={sourceName}>{sourceName}</span>}
        <button type="button" className="spin-360-primary" disabled={!frameCount || phase !== "idle"} onClick={makeSpin}>
          Make 360° spin
        </button>
        {generating && <button type="button" disabled={phase === "stopping"} onClick={stopSpin}>Stop</button>}
      </div>
      <div className="spin-360-progress" role="status">{progress}</div>
      {error && <p className="spin-360-error" role="alert">{error}</p>}
      <SpinViewer frames={frames} current={current} setCurrent={setCurrent} open={open}
        onDownload={downloadViews} key={viewerVersion} />
    </dialog>
  );
}
