import { useState, type ReactNode } from "react";
import { readImage } from "./image-jobs";
import "./studio-4d-wardrobe.css";

const CATEGORIES = {
  top: { label: "👕 Top", item: "the jacket", target: "the shirt" },
  bottom: { label: "👖 Bottom", item: "the jeans", target: "the trousers" },
  outfit: { label: "🤵 Outfit", item: "the clothes", target: "the clothes" },
  shoes: { label: "👟 Shoes", item: "the shoes", target: "the shoes" },
  hair: { label: "💇 Hair", item: "the hairstyle", target: "the hair" },
  accessory: { label: "🧣 Accessory", item: "the accessory", target: "" },
  material: { label: "🧵 Material", item: "the fabric", target: "" },
};

const WARDROBE_KEY = "froja.4d.wardrobe";
const MAX_LOOKS = 24;
type Category = keyof typeof CATEGORIES;
export type WardrobeRequest = { category: Category; reference: string; item: string; target: string };
export type WardrobeResult = {
  image: string;
  reference_crop_url: string;
  reference_mask_url: string;
  target_mask_url: string;
};
type WardrobeStatus = Omit<WardrobeResult, "image"> & {
  status: "running" | "complete" | "failed" | "stopped";
  stage: string;
  error?: string;
  image_url?: string;
};
type SavedLook = Pick<WardrobeRequest, "category" | "item"> & { thumbnail: string };

const waitForWardrobe = () => new Promise<void>((resolve) => window.setTimeout(resolve, 1000));

async function wardrobeResponse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => { throw new Error("Could not reach Froja’s Wardrobe API."); });
  if (!response.ok) throw new Error(body.error || "The Wardrobe request failed.");
  return body;
}

export async function requestWardrobe(
  person: string, request: WardrobeRequest, signal: AbortSignal,
  onQueued: (id: string | undefined) => void, onProgress: (message: string) => void,
): Promise<WardrobeResult> {
  signal.throwIfAborted();
  // Get the job ID even when Stop is pressed during submission.
  const { job_id } = await wardrobeResponse<{ job_id: string }>(await fetch("/api/wardrobe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ person, ...request }),
    signal: AbortSignal.timeout(90_000),
  }));
  if (!job_id) throw new Error("Froja did not return a Wardrobe job.");
  onQueued(job_id);
  const url = `/api/wardrobe/${encodeURIComponent(job_id)}`;
  for (;;) {
    const result = await wardrobeResponse<WardrobeStatus>(await fetch(url, { signal }));
    if (result.status !== "running") {
      onQueued(undefined);
      if (result.status !== "complete" || !result.image_url) {
        throw new Error(result.error || "Wardrobe ended without a picture.");
      }
      const output = await fetch(result.image_url, { signal });
      if (!output.ok) throw new Error("Could not load the try-on picture.");
      return { ...result, image: await readImage(await output.blob()) };
    }
    onProgress(result.stage);
    await waitForWardrobe();
  }
}

export async function stopWardrobeJob(id: string) {
  const signal = AbortSignal.timeout(90_000);
  const url = `/api/wardrobe/${encodeURIComponent(id)}`;
  let status = await wardrobeResponse<WardrobeStatus>(await fetch(`${url}/stop`, { method: "POST", signal }));
  while (status.status === "running") {
    await waitForWardrobe();
    status = await wardrobeResponse<WardrobeStatus>(await fetch(url, { signal }));
  }
}

export function loadWardrobe(): SavedLook[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(WARDROBE_KEY) || "[]");
    if (!Array.isArray(stored)) return [];
    return stored.filter((look): look is SavedLook => look && Object.hasOwn(CATEGORIES, look.category)
      && typeof look.item === "string" && typeof look.thumbnail === "string"
      && /^data:image\/(webp|png);base64,/.test(look.thumbnail)).slice(0, MAX_LOOKS);
  } catch {
    return [];
  }
}

export async function saveWardrobeLook(crop: string, { category, item, reference }: WardrobeRequest) {
  const picture = new Image();
  picture.src = crop;
  await picture.decode();
  const scale = Math.min(1, 256 / Math.max(picture.naturalWidth, picture.naturalHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(picture.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(picture.naturalHeight * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Could not make a wardrobe thumbnail.");
  context.drawImage(picture, 0, 0, canvas.width, canvas.height);
  const thumbnail = canvas.toDataURL("image/webp", 0.82);
  const saved = loadWardrobe().filter((look) => look.thumbnail !== reference && look.thumbnail !== thumbnail);
  const next = [{ category, item: item.trim(), thumbnail }, ...saved].slice(0, MAX_LOOKS);
  localStorage.setItem(WARDROBE_KEY, JSON.stringify(next));
  return next;
}

export function WardrobeControls({ hasMaster, busy, result, looks, pickPicture, onTry, onKeep, onDiscard }: {
  hasMaster: boolean;
  busy: boolean;
  result?: WardrobeResult;
  looks: SavedLook[];
  pickPicture: (onImage: (image: string) => void) => ReactNode;
  onTry: (request: WardrobeRequest) => void;
  onKeep: () => void;
  onDiscard: () => void;
}) {
  const [category, setCategory] = useState<Category>("top");
  const [reference, setReference] = useState("");
  const [item, setItem] = useState("");
  const [target, setTarget] = useState<string>();
  const defaults = CATEGORIES[category];
  const replace = target ?? (category === "material" ? item.trim() : defaults.target);
  const locked = busy || Boolean(result);

  return <div className="studio-4d-wardrobe">
    <form className="studio-4d-form" onSubmit={(event) => {
      event.preventDefault();
      if (hasMaster && reference && !locked) onTry({ category, reference, item, target: target ?? (category === "top" ? "" : replace) });
    }}>
      <div className="studio-4d-pills wardrobe-categories" role="group" aria-label="Wardrobe category">
        {(Object.keys(CATEGORIES) as Category[]).map((key) => <button type="button" key={key}
          aria-pressed={key === category} disabled={locked} onClick={() => {
            setCategory(key);
            setItem("");
            setTarget(undefined);
          }}>{CATEGORIES[key].label}</button>)}
      </div>
      <div className="wardrobe-upload">
        {reference && <img src={reference} alt="Reference look" />}
        {pickPicture(setReference)}
      </div>
      <label>Which item?<input maxLength={200} disabled={locked} placeholder={defaults.item} value={item}
        onChange={(event) => setItem(event.target.value)} /></label>
      <label>Replace what?<input maxLength={200} disabled={locked} placeholder={category === "material" ? "the part to retexture" : "Optional"}
        value={replace} onChange={(event) => setTarget(event.target.value)} /></label>
      {result ? <div className="studio-4d-actions wardrobe-review">
        <button type="button" className="studio-4d-primary" onClick={onKeep}>Keep this</button>
        <button type="button" onClick={onDiscard}>Discard</button>
      </div> : <button type="submit" className="studio-4d-primary" disabled={!hasMaster || !reference || locked}>Try it on</button>}
      <p className="studio-4d-help">Use photos you have permission to use. Fit and folds are drawn by AI.</p>
    </form>
    {result && <details className="wardrobe-masks">
      <summary>Mask previews</summary>
      <div>
        <figure><img src={result.reference_mask_url} alt="White area used from the look" /><figcaption>Reference item</figcaption></figure>
        <figure><img src={result.target_mask_url} alt="White area blended into the master" /><figcaption>Replace area</figcaption></figure>
      </div>
    </details>}
    <div className="wardrobe-saved">
      <strong>My wardrobe</strong>
      {looks.length ? <div className="studio-4d-thumbs" role="group" aria-label="Saved looks">
        {looks.map((look) => <button type="button" key={look.thumbnail} disabled={locked}
          aria-label={look.item || CATEGORIES[look.category].item} aria-pressed={reference === look.thumbnail}
          onClick={() => {
            setReference(look.thumbnail);
            setCategory(look.category);
            setItem(look.item);
            setTarget(undefined);
          }}>
          <img src={look.thumbnail} alt="" />
        </button>)}
      </div> : <p className="studio-4d-help">Reference crops appear here after a try-on.</p>}
    </div>
  </div>;
}
