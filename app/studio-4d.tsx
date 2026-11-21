import { useEffect, useId, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import {
  downloadImageFile, downloadImageZip, IMAGE_TYPES, imageExtension, openPicture, readImage, requestImage, stopImageJob, type ImageJob,
} from "./image-jobs";
import { requestTextMask } from "./mask-by-words";
import { GLOBE_CENTER, GLOBE_RADIUS, OrbitScene, projectOrbit, wrapAzimuth } from "./orbit-sphere";
import { generateSpin, generateView, SpinViewer, type CameraPosition, type SpinFrame } from "./spin-360";
import { CAMERA_ELEVATIONS, dragCamera, snapCamera } from "./studio-4d-camera";
import {
  AnimateControls, AnimationPreview, requestAnimation, stopAnimationJob,
  type AnimateRequest, type AnimateResult,
} from "./studio-4d-animate";
import {
  WardrobeControls, loadWardrobe, requestWardrobe, saveWardrobeLook, stopWardrobeJob,
  type WardrobeRequest, type WardrobeResult,
} from "./studio-4d-wardrobe";
import "./studio-4d.css";

const SECTIONS = ["Camera", "Clothes", "Wardrobe", "Person", "Background", "360°", "Animate"] as const;
const AZIMUTHS = ["Front", "Front right", "Right side", "Rear right", "Back", "Rear left", "Left side", "Front left"];
const CAMERA_ANGLES = ["Front", "Front-right", "Right side", "Back-right", "Back", "Back-left", "Left side", "Front-left"];
const HEIGHTS = { low: -32, eye: 0, high: 32 };
const HEIGHT_OPTIONS = { low: "Low", eye: "Eye level", high: "High" };
const HEIGHT_LABELS = { low: "low angle", eye: "eye level", high: "high angle" };
const DISTANCES = { wide: "Wide", medium: "Medium", closeup: "Close-up" } as const;
const DISTANCE_LABELS = { wide: "wide shot", medium: "medium shot", closeup: "close-up" };
const REAR_GUIDES: Partial<Record<number, number>> = { 135: 90, 180: 90, 225: 270 };
const DEFAULT_CAMERA: CameraPosition = { azimuth: 0, elevation: "eye", distance: "medium" };

type Section = typeof SECTIONS[number];
type View = { id: string; camera: CameraPosition; image: string };
type Master = { name: string; image: string; views: View[]; spin: SpinFrame[] };
type StudioRun = {
  controller: AbortController;
  job?: ImageJob;
  wardrobeJob?: string;
  animationJob?: string;
  animation?: boolean;
  stopping?: boolean;
  ending?: boolean;
  message?: string;
};
type ImageTask = (signal: AbortSignal, queued: (job: ImageJob) => void) => Promise<string>;

const angleName = (angle: number) => AZIMUTHS[angle / 45];
const angleFile = (angle: number) => String(angle).padStart(3, "0");
const cameraDirectionLabel = ({ azimuth, elevation }: CameraPosition) =>
  `${CAMERA_ANGLES[azimuth / 45]} · ${HEIGHT_LABELS[elevation]}`;
const cameraLabel = (camera: CameraPosition) => `${cameraDirectionLabel(camera)} · ${DISTANCE_LABELS[camera.distance]}`;
const newMaster = (name: string, image: string): Master => ({ name, image, views: [], spin: [] });

function cameraMarkerPosition(camera: CameraPosition) {
  const projected = projectOrbit({ azimuth: camera.azimuth, elevation: HEIGHTS[camera.elevation] });
  const dx = projected.x - GLOBE_CENTER;
  const dy = projected.y - GLOBE_CENTER;
  const radius = Math.hypot(dx, dy);
  const scale = Math.max(1, 68 / Math.max(radius, 1));
  const x = GLOBE_CENTER + dx * scale;
  const y = GLOBE_CENTER + (radius < 1 ? 68 : dy * scale);
  const pointing = Math.atan2(GLOBE_CENTER - y, GLOBE_CENTER - x) * 180 / Math.PI;
  return { x, y, pointing, behind: projected.behind };
}

function CameraMarker({ position, ghost = false }: { position: ReturnType<typeof cameraMarkerPosition>; ghost?: boolean }) {
  const { x, y, pointing, behind } = position;
  return <g className={ghost ? "studio-4d-camera-handle studio-4d-camera-ghost" : "studio-4d-camera-handle"}
    data-behind={behind} transform={`translate(${x} ${y}) rotate(${pointing})`}>
    {!ghost && <circle r="24" className="studio-4d-hit-area" />}
    <rect x="-15" y="-10" width="23" height="20" rx="4" />
    <path d="M 8 -4 L 17 -9 V 9 L 8 4 Z M -11 -10 L -8 -15 H 0 L 3 -10" />
    <circle cx="-8" cy="0" r="2.5" className="studio-4d-camera-led" />
  </g>;
}

function CameraSphere({ image, camera, disabled, onCamera }: {
  image: string; camera: CameraPosition; disabled: boolean; onCamera: (camera: CameraPosition) => void;
}) {
  const pictureId = useId();
  const helpId = useId();
  const drag = useRef<{ pointer: number; x: number; y: number; radius: number; camera: CameraPosition } | null>(null);
  const [preview, setPreview] = useState<CameraPosition | null>(null);
  const position = cameraMarkerPosition(preview ?? camera);
  const target = preview ? snapCamera(preview) : camera;

  function draggedCamera(event: PointerEvent<HTMLDivElement>) {
    const start = drag.current;
    if (disabled || start?.pointer !== event.pointerId) return;
    return dragCamera(start.camera, event.clientX - start.x, event.clientY - start.y, start.radius);
  }

  function clearDrag() {
    drag.current = null;
    setPreview(null);
  }

  return <>
    <div className="studio-4d-globe" data-dragging={Boolean(preview)} role="group" tabIndex={disabled ? undefined : 0}
      aria-label={`Camera position. ${cameraLabel(target)}`} aria-describedby={helpId}
      aria-keyshortcuts="ArrowLeft ArrowRight ArrowUp ArrowDown"
      onPointerDown={(event) => {
        if (disabled || event.button !== 0 || drag.current || !(event.target instanceof Element) ||
          !event.target.closest(".studio-4d-camera-handle")) return;
        event.currentTarget.focus();
        event.currentTarget.setPointerCapture(event.pointerId);
        const radius = event.currentTarget.getBoundingClientRect().width * GLOBE_RADIUS / (2 * GLOBE_CENTER);
        drag.current = { pointer: event.pointerId, x: event.clientX, y: event.clientY, radius, camera };
        setPreview(camera);
      }}
      onPointerMove={(event) => {
        const next = draggedCamera(event);
        if (next) setPreview(next);
      }}
      onPointerUp={(event) => {
        const next = draggedCamera(event);
        if (next) onCamera(snapCamera(next));
      }}
      onLostPointerCapture={(event) => { if (drag.current?.pointer === event.pointerId) clearDrag(); }}
      onKeyDown={(event) => {
        if (disabled) return;
        const next = { ...camera };
        const height = CAMERA_ELEVATIONS.indexOf(camera.elevation);
        switch (event.key) {
          case "ArrowLeft": next.azimuth = wrapAzimuth(camera.azimuth - 45); break;
          case "ArrowRight": next.azimuth = wrapAzimuth(camera.azimuth + 45); break;
          case "ArrowUp": next.elevation = CAMERA_ELEVATIONS[Math.min(height + 1, CAMERA_ELEVATIONS.length - 1)]; break;
          case "ArrowDown": next.elevation = CAMERA_ELEVATIONS[Math.max(height - 1, 0)]; break;
          default: return;
        }
        event.preventDefault();
        if (drag.current) clearDrag();
        onCamera(next);
      }}>
      <svg viewBox="0 0 360 360" aria-hidden="true">
        <OrbitScene image={image} pictureId={pictureId} behind={
          <line className="studio-4d-sightline" x1={position.x} y1={position.y} x2={GLOBE_CENTER} y2={GLOBE_CENTER} />
        } />
        {preview && <CameraMarker position={cameraMarkerPosition(target)} ghost />}
        <CameraMarker position={position} />
      </svg>
    </div>
    <p className="studio-4d-help" id={helpId}>Drag the camera or use the arrow keys</p>
    <div className="studio-4d-camera-options">
      <strong>Angle</strong>
      <div className="studio-4d-pills" role="group" aria-label="Camera angle">
        {CAMERA_ANGLES.map((label, index) => {
          const azimuth = index * 45;
          return <button key={azimuth} type="button" disabled={disabled} aria-pressed={camera.azimuth === azimuth}
            onClick={() => onCamera({ ...camera, azimuth })}>{label}</button>;
        })}
      </div>
    </div>
    <div className="studio-4d-camera-options">
      <strong>Height</strong>
      <div className="studio-4d-pills" role="group" aria-label="Camera height">
        {CAMERA_ELEVATIONS.map((elevation) => <button key={elevation} type="button" disabled={disabled}
          aria-pressed={camera.elevation === elevation} onClick={() => onCamera({ ...camera, elevation })}>{HEIGHT_OPTIONS[elevation]}</button>)}
      </div>
    </div>
    <div className="studio-4d-camera-options">
      <strong>Distance</strong>
      <div className="studio-4d-pills" role="group" aria-label="Camera distance">
        {(Object.keys(DISTANCES) as CameraPosition["distance"][]).map((distance) => <button key={distance} type="button"
          disabled={disabled} aria-pressed={camera.distance === distance} onClick={() => onCamera({ ...camera, distance })}>{DISTANCES[distance]}</button>)}
      </div>
    </div>
    <p className="studio-4d-camera-readout" aria-live="polite">{cameraDirectionLabel(target)}</p>
  </>;
}

function PicturePicker({ label, disabled, onFile }: { label: string; disabled: boolean; onFile: (file: File) => void }) {
  return <label className="studio-4d-picker">
    <input type="file" accept={IMAGE_TYPES.join(",")} disabled={disabled} onChange={(event) => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (file) onFile(file);
    }} />
    <span>{label}</span>
  </label>;
}

export default function Studio4D({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const run = useRef<StudioRun | null>(null);
  const uploading = useRef(false);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<Master[]>([]);
  const [version, setVersion] = useState(0);
  const [section, setSection] = useState<Section>("Camera");
  const [camera, setCamera] = useState(DEFAULT_CAMERA);
  const [viewId, setViewId] = useState("");
  const [before, setBefore] = useState(false);
  const [clothesArea, setClothesArea] = useState("");
  const [clothesMask, setClothesMask] = useState("");
  const [clothesPrompt, setClothesPrompt] = useState("");
  const [background, setBackground] = useState("");
  const [face, setFace] = useState("");
  const [spinCurrent, setSpinCurrent] = useState(0);
  const [progress, setProgress] = useState("");
  const [stopping, setStopping] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [animation, setAnimation] = useState<{ image: string; result: AnimateResult }>();
  const [wardrobeResult, setWardrobeResult] = useState<WardrobeResult>();
  const [looks, setLooks] = useState(loadWardrobe);

  const busy = Boolean(progress) || loading;
  const master = history[version];
  const animationResult = section === "Animate" && animation?.image === master?.image ? animation?.result : undefined;
  const previous = history[version - 1];
  const wardrobePreview = section === "Wardrobe" ? wardrobeResult : undefined;
  const selectedView = master?.views.find((view) => view.id === viewId);
  const spinFrame = section === "360°" ? master?.spin.find(({ angle }) => angle === spinCurrent && angle !== 0) : undefined;
  const image = wardrobePreview ? (before ? master?.image : wardrobePreview.image)
    : before ? previous?.image : selectedView?.image ?? spinFrame?.image ?? master?.image;
  const imageLabel = wardrobePreview ? (before ? "Master before try-on" : "Wardrobe try-on")
    : before ? "Before last edit" : selectedView ? cameraLabel(selectedView.camera)
      : spinFrame ? `${angleName(spinFrame.angle)} · 360° spin` : "Master";
  const maskPreview = section === "Clothes" && !before && !selectedView ? clothesMask : "";

  useEffect(() => {
    const element = dialog.current;
    if (open && !element?.open) element?.showModal();
    if (!open && element?.open) element.close();
  }, [open]);

  function showMaster(index: number) {
    setVersion(index);
    setViewId("");
    setSpinCurrent(0);
    setBefore(false);
    setClothesMask("");
    setWardrobeResult(undefined);
    setError("");
    setNotice("");
  }

  async function loadPicture(file: File, acceptImage: (image: string) => void) {
    if (run.current || uploading.current) return;
    uploading.current = true;
    setLoading(true);
    setError("");
    try {
      acceptImage(await openPicture(file));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not open this picture.");
    } finally {
      uploading.current = false;
      setLoading(false);
    }
  }

  function finishRun() {
    run.current = null;
    setProgress("");
    setStopping(false);
  }

  async function finishStop(active: StudioRun) {
    if (active.stopping) return;
    active.stopping = true;
    setProgress(active.animation ? "Stopping animation…" : "Stopping image job…");
    setStopping(true);
    try {
      if (active.job) await stopImageJob(active.job);
      if (active.wardrobeJob) await stopWardrobeJob(active.wardrobeJob);
      if (active.animationJob) await stopAnimationJob(active.animationJob);
      setError(active.message ?? "");
      if (!active.message) setNotice("Job stopped.");
      finishRun();
    } catch {
      setError("Froja could not confirm the job stopped. Press Stop to check again.");
      setProgress(active.animation ? "Waiting for the animation to stop…" : "Waiting for the image engine…");
      setStopping(false);
      active.stopping = false;
    }
  }

  async function start(label: string, work: (active: StudioRun) => Promise<void>, animation = false) {
    if (run.current || uploading.current) return;
    const active: StudioRun = { controller: new AbortController(), animation };
    run.current = active;
    setError("");
    setNotice("");
    setProgress(label);
    try {
      await work(active);
      finishRun();
    } catch (failure) {
      active.ending = true;
      if (!active.controller.signal.aborted) {
        active.message = failure instanceof DOMException && failure.name === "TimeoutError" ? "The job took too long. Try again."
          : failure instanceof Error && !(failure instanceof TypeError || failure instanceof SyntaxError) ? failure.message
          : "Could not get a result from Froja. Check that it is running and try again.";
      }
      if (active.job || active.wardrobeJob || active.animationJob || active.controller.signal.aborted) {
        await finishStop(active);
      } else {
        setError(active.message ?? "");
        finishRun();
      }
    }
  }

  function stop() {
    const active = run.current;
    if (!active) return;
    setStopping(true);
    setProgress(active.animation ? "Stopping animation…" : "Stopping image job…");
    if (active.ending) void finishStop(active);
    else active.controller.abort();
  }

  async function runImage(active: StudioRun, task: ImageTask, timeout = 6 * 60_000) {
    const signal = AbortSignal.any([active.controller.signal, AbortSignal.timeout(timeout)]);
    const image = await task(signal, (job) => { active.job = job; });
    active.job = undefined;
    signal.throwIfAborted();
    return image;
  }

  function editImage(active: StudioRun, endpoint: string, payload: object) {
    return runImage(active, async (signal, onQueued) => readImage(await requestImage({
      endpoint, engine: "extension", payload, signal, onQueued,
    })));
  }

  function applyEdit(name: string, image: string) {
    setHistory((versions) => [...versions.slice(0, version + 1), newMaster(name, image)]);
    showMaster(version + 1);
    setNotice(`${name} saved as the new master.`);
  }

  function updateViews(update: (current: Master) => Master) {
    setHistory((versions) => versions.map((item, index) => index === version ? update(item) : item));
  }

  function takeView() {
    if (!master) return;
    const { azimuth, elevation, distance } = camera;
    const guide = master.views.find(({ camera }) => camera.azimuth === REAR_GUIDES[azimuth] &&
      camera.distance === "medium" && camera.elevation === "eye");
    void start("Taking camera view…", async (active) => {
      const image = await runImage(active, (signal, queued) => generateView({
        image: master.image, azimuth, elevation, distance, guide_image: guide?.image,
      }, signal, queued), 8 * 60_000);
      const view = { id: crypto.randomUUID(), camera, image };
      updateViews((item) => ({ ...item, views: [...item.views, view] }));
      setViewId(view.id);
      setBefore(false);
      setNotice("Camera view ready.");
    });
  }

  function findClothes() {
    if (!master || !clothesArea.trim()) return;
    void start("Finding the clothes…", async (active) => {
      const mask = await runImage(active, (signal, queued) => requestTextMask({
        image: master.image, prompt: clothesArea.trim(),
      }, signal, queued));
      setClothesMask(mask);
      setBefore(false);
      setViewId("");
    });
  }

  function inpaint(active: StudioRun, master: Master, mask: string, prompt: string, strength: number) {
    return editImage(active, "/api/image-tool", {
      mode: "inpaint", source_image: master.image, mask_image: mask, prompt, strength, preserve_unmasked: true,
    });
  }

  function changeClothes() {
    if (!master || !clothesMask || !clothesPrompt.trim()) return;
    void start("Changing the clothes…", async (active) => {
      applyEdit("Clothes", await inpaint(active, master, clothesMask, clothesPrompt.trim(), 0.95));
    });
  }

  function tryWardrobe(request: WardrobeRequest) {
    if (!master) return;
    void start("Starting Wardrobe…", async (active) => {
      const signal = AbortSignal.any([active.controller.signal, AbortSignal.timeout(20 * 60_000)]);
      const result = await requestWardrobe(master.image, request, signal,
        (id) => { active.wardrobeJob = id; }, setProgress);
      signal.throwIfAborted();
      setWardrobeResult(result);
      setBefore(false);
      setNotice("Try-on ready.");
      void saveWardrobeLook(result.reference_crop_url, request).then(setLooks).catch(() => {
        setNotice("The browser could not save the reference to My wardrobe.");
      });
    });
  }

  function changePerson() {
    if (!master || !face) return;
    void start("Swapping the face…", async (active) => {
      const image = await editImage(active, "/api/face-swap", { source_image: face, target_image: master.image });
      applyEdit("Face swap", image);
    });
  }

  function changeBackground() {
    if (!master || !background.trim()) return;
    void start("Finding the person to keep…", async (active) => {
      const mask = await runImage(active, (signal, queued) => requestTextMask({
        image: master.image, prompt: "the person", invert: true, requireProtectedArea: true,
      }, signal, queued));
      setProgress("Changing the background…");
      applyEdit("Background", await inpaint(active, master, mask, background.trim(), 1));
    });
  }

  function makeSpin() {
    if (!master) return;
    void start("Starting 360° spin…", async (active) => {
      const front = { angle: 0, image: master.image };
      updateViews((item) => ({ ...item, spin: [front] }));
      setSpinCurrent(0);
      setBefore(false);
      await generateSpin(master.image, (request, number, total) => {
        setProgress(`Generating spin view ${number} of ${total}…`);
        return runImage(active, (signal, queued) => generateView(request, signal, queued), 8 * 60_000);
      }, (frame) => {
        updateViews((item) => ({ ...item, spin: [...item.spin, frame].sort((a, b) => a.angle - b.angle) }));
        setSpinCurrent(frame.angle);
      }, () => active.controller.signal.aborted);
      active.controller.signal.throwIfAborted();
      setNotice("All 8 spin views are ready.");
    });
  }

  function makeAnimation(request: AnimateRequest) {
    if (!master) return;
    void start("Starting animation…", async (active) => {
      const result = await requestAnimation(master.image, request, active.controller.signal,
        (id) => { active.animationJob = id; }, setProgress);
      setAnimation({ image: master.image, result });
      setNotice("Animation ready.");
    }, true);
  }

  function animationViews() {
    if (!master) return [];
    const views = new Map<number, string>();
    for (const view of master.views) views.set(view.camera.azimuth, view.image);
    for (const frame of master.spin) views.set(frame.angle, frame.image);
    views.set(0, master.image);
    return Array.from(views, ([azimuth, image]) => ({ azimuth, image })).sort((a, b) => a.azimuth - b.azimuth);
  }

  async function downloadAll() {
    if (!master) return;
    setError("");
    try {
      await downloadImageZip([
        { name: `master-${version}`, image: master.image },
        ...master.views.map(({ camera, image }, index) => ({ name: `camera-${angleFile(camera.azimuth)}-${camera.elevation}-${camera.distance}-${index + 1}`, image })),
        ...master.spin.filter(({ angle }) => angle !== 0).map(({ angle, image }) => ({ name: `spin-${angleFile(angle)}`, image })),
      ], "froja-4d-views.zip");
    } catch {
      setError("Could not prepare the ZIP file. Try downloading again.");
    }
  }

  function downloadCurrent() {
    if (!image) return;
    const name = wardrobePreview ? (before ? `master-${version}` : "wardrobe-try-on")
      : before ? `master-${version - 1}` : selectedView ? `camera-${angleFile(selectedView.camera.azimuth)}`
      : spinFrame ? `spin-${angleFile(spinFrame.angle)}` : `master-${version}`;
    const extension = imageExtension(/^data:([^;]+);/.exec(image)?.[1] ?? null);
    downloadImageFile(image, `froja-${name}.${extension}`);
  }

  return <dialog id="studio-4d" className="studio-4d" ref={dialog} aria-labelledby="studio-4d-title"
    onKeyDown={(event) => event.stopPropagation()} onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
    <header className="studio-4d-header">
      <div><span className="studio-4d-led" aria-hidden="true" /><h2 id="studio-4d-title">4D Studio</h2></div>
      <div className="studio-4d-actions">
        <PicturePicker label={master ? "New master picture" : "Choose master picture"} disabled={busy} onFile={(file) => {
          void loadPicture(file, (image) => {
            setHistory([newMaster("Original", image)]);
            showMaster(0);
            setCamera(DEFAULT_CAMERA);
            setFace("");
          });
        }} />
        <button type="button" className="studio-4d-close" aria-label="Close 4D Studio" disabled={busy} onClick={onClose}>×</button>
      </div>
    </header>

    <div className="studio-4d-layout">
      <section className="studio-4d-card studio-4d-main" aria-label="Current view and master history">
        <div className="studio-4d-preview-bar">
          <strong>{animationResult ? "Animation preview" : image ? imageLabel : "Current view"}</strong>
          {(wardrobePreview || previous) && !animationResult && <div className="studio-4d-pills" role="group"
            aria-label={wardrobePreview ? "Compare the try-on" : "Compare the last edit"}>
            <button type="button" aria-pressed={before} onClick={() => setBefore(true)}>Before</button>
            <button type="button" aria-pressed={!before} onClick={() => setBefore(false)}>After</button>
          </div>}
        </div>
        {animationResult ? <AnimationPreview result={animationResult} /> : <div className="studio-4d-preview mask-words-source">
          {image ? <img src={image} alt={imageLabel} draggable={false} /> : <p>Choose a picture of one person to start.</p>}
          {maskPreview && <span className="mask-words-overlay" role="img" aria-label="Clothes selected in blue"
            style={{ "--inpaint-mask": `url("${maskPreview}")` } as CSSProperties} />}
        </div>}
        {master && <div className="studio-4d-history">
          <div className="studio-4d-preview-bar">
            <strong>Master history</strong>
            <div className="studio-4d-actions">
              <button type="button" disabled={busy || version === 0} onClick={() => showMaster(version - 1)}>Undo</button>
              <button type="button" disabled={busy || version === history.length - 1} onClick={() => showMaster(version + 1)}>Redo</button>
            </div>
          </div>
          <div className="studio-4d-thumbs" role="group" aria-label="Master versions">
            {history.map(({ name, image }, index) => <button type="button" key={index} aria-pressed={index === version} disabled={busy}
              onClick={() => showMaster(index)} aria-label={`Master version ${index + 1}, ${name}`}>
              <img src={image} alt="" /><span>{name}</span>
            </button>)}
          </div>
        </div>}
      </section>

      <section className="studio-4d-card studio-4d-panel" aria-label="Studio controls">
        <div className="studio-4d-pills studio-4d-sections" role="group" aria-label="Studio sections">
          {SECTIONS.map((item) => <button key={item} type="button" disabled={busy} aria-pressed={section === item} onClick={() => {
            setSection(item);
            setViewId("");
            setBefore(false);
            setError("");
            setNotice("");
          }}>{item}</button>)}
        </div>

        {section === "Camera" && <div className="studio-4d-camera">
          <CameraSphere image={master?.image ?? ""} camera={camera} disabled={busy} onCamera={setCamera} />
          <button type="button" className="studio-4d-primary" disabled={busy || !master} onClick={takeView}>Take this view</button>
          {Boolean(master?.views.length) && <div className="studio-4d-thumbs" role="group" aria-label="Generated camera views">
            <button type="button" disabled={busy} aria-pressed={!viewId} onClick={() => { setViewId(""); setBefore(false); }}>
              <img src={master.image} alt="" /><span>Master</span>
            </button>
            {master.views.map((view) => <button type="button" key={view.id} aria-label={cameraLabel(view.camera)} title={cameraLabel(view.camera)}
              aria-pressed={viewId === view.id} disabled={busy} onClick={() => { setViewId(view.id); setBefore(false); }}>
              <img src={view.image} alt="" /><span>{view.camera.azimuth}° · {DISTANCES[view.camera.distance]}</span>
            </button>)}
          </div>}
        </div>}

        {section === "Clothes" && <>
          <form className="studio-4d-form" onSubmit={(event) => { event.preventDefault(); findClothes(); }}>
            <label>What to change?<input value={clothesArea} placeholder="the t-shirt" disabled={busy || !master}
              onChange={(event) => { setClothesArea(event.target.value); setClothesMask(""); }} /></label>
            <button type="submit" disabled={busy || !master || !clothesArea.trim()}>Find clothes</button>
          </form>
          <form className="studio-4d-form" onSubmit={(event) => { event.preventDefault(); changeClothes(); }}>
            <label>Change into…<input value={clothesPrompt} placeholder="a black hoodie" disabled={busy || !master}
              onChange={(event) => setClothesPrompt(event.target.value)} /></label>
            <button type="submit" className="studio-4d-primary" disabled={busy || !clothesMask || !clothesPrompt.trim()}>Change clothes</button>
          </form>
        </>}

        <div hidden={section !== "Wardrobe"}>
          <WardrobeControls hasMaster={Boolean(master)} busy={busy} result={wardrobeResult} looks={looks}
            pickPicture={(acceptImage) => <PicturePicker label="Upload a look" disabled={busy || Boolean(wardrobeResult)}
              onFile={(file) => { void loadPicture(file, acceptImage); }} />}
            onTry={tryWardrobe} onKeep={() => {
              if (wardrobeResult && !busy) applyEdit("Wardrobe", wardrobeResult.image);
            }} onDiscard={() => {
              setWardrobeResult(undefined);
              setBefore(false);
              setNotice("");
            }} />
        </div>

        {section === "Person" && <div className="studio-4d-form">
          <PicturePicker label="Upload a face photo" disabled={busy || !master} onFile={(file) => { void loadPicture(file, setFace); }} />
          {face && <img className="studio-4d-face" src={face} alt="Face to use" />}
          <p className="studio-4d-help">Use only photos you have permission to use.</p>
          <button type="button" className="studio-4d-primary" disabled={busy || !master || !face} onClick={changePerson}>Swap face onto master</button>
        </div>}

        {section === "Background" && <form className="studio-4d-form" onSubmit={(event) => { event.preventDefault(); changeBackground(); }}>
          <label>New background<input value={background} placeholder="a sunny beach with blue sea" disabled={busy || !master}
            onChange={(event) => setBackground(event.target.value)} /></label>
          <button type="submit" className="studio-4d-primary" disabled={busy || !master || !background.trim()}>Change background</button>
        </form>}

        {section === "360°" && <div className="studio-4d-form">
          <button type="button" className="studio-4d-primary" disabled={busy || !master} onClick={makeSpin}>Make 360° spin from this master</button>
          {master && <div className="studio-4d-spin spin-360">
            <SpinViewer frames={master.spin.length ? master.spin : [{ angle: 0, image: master.image }]} current={spinCurrent}
              setCurrent={setSpinCurrent} sourceLabel="Master" open={open} key={version} />
          </div>}
        </div>}

        {section === "Animate" && <AnimateControls hasMaster={Boolean(master)} busy={busy} onAnimate={makeAnimation}
          views={animationViews()} onMakeViews={() => setSection("360°")} />}
      </section>
    </div>

    <div className="studio-4d-status">
      <div role="status">{progress && <progress aria-label={progress} />}{progress || notice || (loading && "Opening picture…")}</div>
      {progress && <button type="button" disabled={stopping} onClick={stop}>Stop</button>}
      {error && <p role="alert">{error}</p>}
    </div>
    <footer className="studio-4d-actions studio-4d-footer">
      <button type="button" disabled={!image} onClick={downloadCurrent}>Download current view</button>
      <button type="button" disabled={!master} onClick={downloadAll}>Download all views (.zip)</button>
      <button type="button" disabled>Dots view — coming soon</button>
      <button type="button" disabled>Send to Blender — coming soon</button>
    </footer>
  </dialog>;
}
