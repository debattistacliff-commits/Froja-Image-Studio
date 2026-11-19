import { useEffect, useRef, useState } from "react";
import { readImage, requestImage, type ImageJob } from "./image-jobs";
import "./mask-by-words.css";

const POLL_INTERVAL_MS = 2_000;
const TIMEOUT_MS = 6 * 60_000;

async function readMask(blob: Blob, requireProtectedArea: boolean): Promise<string> {
  const image = await createImageBitmap(blob);
  try {
    const canvas = document.createElement("canvas");
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Could not read the mask image. Try finding it again.");
    context.drawImage(image, 0, 0);
    const { data } = context.getImageData(0, 0, image.width, image.height);
    let pixel = 0;
    while (pixel < data.length && data[pixel] === 0) pixel += 4;
    if (pixel === data.length) {
      throw new Error("Nothing matched that description. Try naming the object more specifically.");
    }
    if (requireProtectedArea) {
      pixel = 0;
      while (pixel < data.length && data[pixel] !== 0) pixel += 4;
      if (pixel === data.length) throw new Error("Could not find an area to protect in this picture.");
    }
  } finally {
    image.close();
  }

  return readImage(blob);
}

export async function requestTextMask(
  { requireProtectedArea = false, ...payload }: {
    image: string; prompt: string; grow?: number; invert?: boolean; requireProtectedArea?: boolean;
  },
  signal: AbortSignal,
  onQueued?: (job: ImageJob) => void,
) {
  return readMask(await requestImage({
    endpoint: "/api/mask-from-text", engine: "extension", payload, signal, onQueued, pollMs: POLL_INTERVAL_MS,
  }), requireProtectedArea);
}

type Props = {
  source: string;
  mask: string;
  onUpload: (file: File | undefined) => void;
  onMaskChange: (mask: string) => void;
};

export default function MaskByWords({ source, mask, onUpload, onMaskChange }: Props) {
  const [prompt, setPrompt] = useState("");
  const [invert, setInvert] = useState(false);
  const [grow, setGrow] = useState("0");
  const [finding, setFinding] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => () => request.current?.abort(), [source]);

  async function findMask() {
    const description = prompt.trim();
    if (!source || !description || request.current) return;

    const controller = new AbortController();
    const timeout = AbortSignal.timeout(TIMEOUT_MS);
    const signal = AbortSignal.any([controller.signal, timeout]);
    request.current = controller;
    setFinding(true);
    setError("");

    try {
      const dataURL = await requestTextMask({ image: source, prompt: description, grow: Number(grow), invert }, signal);
      signal.throwIfAborted();
      if (fileInput.current) fileInput.current.value = "";
      onMaskChange(dataURL);
    } catch (failure) {
      if (controller.signal.aborted) return;
      if (timeout.aborted) {
        setError("Finding a mask timed out after six minutes. The first model download can take a few minutes. Try again shortly.");
      } else {
        setError(failure instanceof Error && !(failure instanceof TypeError || failure instanceof SyntaxError)
          ? failure.message
          : "Could not get a mask from the image engine. Try again in a moment.");
      }
    } finally {
      request.current = null;
      setFinding(false);
    }
  }

  return (
    <div className="mask-words-column">
      <label className="tool-upload">
        <b>Mask image</b>
        <small>White = replace, black = preserve</small>
        <input
          ref={fileInput}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={(event) => {
            request.current?.abort();
            setError("");
            onUpload(event.target.files?.[0]);
          }}
        />
        {mask ? <img src={mask} alt="Inpainting mask" /> : <span>Choose a matching mask</span>}
      </label>
      <form className="mask-words" onSubmit={(event) => { event.preventDefault(); void findMask(); }}>
        <label className="mask-words-description">
          <b>✨ Mask by words</b>
          <input
            type="text"
            placeholder="What should change? e.g. the shirt, the sky, the car"
            value={prompt}
            disabled={!source || finding}
            onChange={(event) => setPrompt(event.target.value)}
          />
        </label>
        <div className="mask-words-actions">
          <label>
            Grow (px)
            <input type="number" min={0} max={64} value={grow} disabled={!source || finding} onChange={(event) => setGrow(event.target.value)} />
          </label>
          <label><input type="checkbox" checked={invert} disabled={!source || finding} onChange={(event) => setInvert(event.target.checked)} /> Invert</label>
          <button className="mask-words-find" type="submit" disabled={!source || !prompt.trim() || finding}>Find it</button>
          {mask && <button type="button" onClick={() => {
            request.current?.abort();
            if (fileInput.current) fileInput.current.value = "";
            setError("");
            onMaskChange("");
          }}>Clear</button>}
        </div>
        {!finding && !mask && !error && <small>The first run downloads SAM2 and GroundingDINO (~1 GB) and can take a few minutes.</small>}
        {finding && <small role="status">Finding “{prompt.trim()}”… first time downloads models (~1 GB) and can take a few minutes.</small>}
        {error && <div className="error" role="alert">{error}</div>}
      </form>
    </div>
  );
}
