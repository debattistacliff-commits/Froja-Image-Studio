export type ImageEngine = "main" | "extension";
export type ImageJob = { engine: ImageEngine; prompt_id: string };

type JobResponse = {
  prompt_id?: string;
  status?: string;
  images?: string[];
  error?: string | { exception_message?: string };
  record?: { messages?: [string, { exception_message?: string }][] };
};

type ImageRequest = {
  endpoint: string;
  engine: ImageEngine;
  payload: object;
  signal: AbortSignal;
  onQueued?: (job: ImageJob) => void;
  pollMs?: number;
};

const wait = (milliseconds: number) => new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

async function postImageRequest(endpoint: string, payload: object, signal: AbortSignal) {
  return fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

function jobError(result: JobResponse, fallback: string) {
  const recorded = result.record?.messages?.find(([kind]) => kind === "execution_error")?.[1].exception_message;
  return new Error(typeof result.error === "string" ? result.error : result.error?.exception_message || recorded || fallback);
}

export async function requestImage({ endpoint, engine, payload, signal, onQueued, pollMs = 1500 }: ImageRequest): Promise<Blob> {
  signal.throwIfAborted();
  // A tracked submission must return its job ID even if the user presses Stop while it is queueing.
  const submitSignal = onQueued ? AbortSignal.timeout(180_000) : signal;
  let response = await postImageRequest(endpoint, payload, submitSignal);
  if (onQueued && response.status === 409) {
    // Engine history can report a completed image just before its queue releases the GPU.
    await wait(1500);
    signal.throwIfAborted();
    response = await postImageRequest(endpoint, payload, submitSignal);
  }
  const job: JobResponse = await response.json().catch(() => { throw new Error("Could not reach Froja’s image API."); });
  if (!response.ok || !job.prompt_id) throw jobError(job, "Could not start the image job.");
  onQueued?.({ engine, prompt_id: job.prompt_id });
  signal.throwIfAborted();

  const jobs = engine === "main" ? "jobs" : "extension-jobs";
  for (;;) {
    await wait(pollMs);
    const status = await fetch(`/api/${jobs}/${encodeURIComponent(job.prompt_id)}`, { signal });
    const result: JobResponse = await status.json();
    if (status.ok && result.status === "running") continue;
    if (!status.ok || result.status !== "complete" || !result.images?.[0]) {
      throw jobError(result, "The image engine finished without an image.");
    }
    const output = await fetch(result.images[0], { signal });
    if (!output.ok) throw new Error("Could not load the result from the image engine.");
    return output.blob();
  }
}

export async function stopImageJob(job: ImageJob) {
  const signal = AbortSignal.timeout(90_000);
  for (;;) {
    const response = await postImageRequest("/api/studio-4d/stop", job, signal);
    if (!response.ok) throw new Error("Could not stop the image job.");
    const result: { stopped: boolean } = await response.json();
    if (result.stopped) return;
    await wait(1500);
  }
}

export function readImage(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Could not read the picture."));
    reader.readAsDataURL(blob);
  });
}

export const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];

export async function openPicture(file: File): Promise<string> {
  if (!IMAGE_TYPES.includes(file.type) || file.size > 25 * 1024 * 1024) {
    throw new Error("Choose a PNG, JPEG, or WebP image up to 25 MB.");
  }
  const image = await readImage(file);
  const preview = new Image();
  preview.src = image;
  await preview.decode().catch(() => { throw new Error("Could not open this picture."); });
  return image;
}

export function downloadImageFile(url: string, name: string) {
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
}

export function imageExtension(type: string | null) {
  return type === "image/jpeg" ? "jpg" : type === "image/webp" ? "webp" : "png";
}

export async function downloadImageZip(entries: { name: string; image: string }[], filename: string) {
  const { zipSync } = await import("three/addons/libs/fflate.module.js");
  const files = await Promise.all(entries.map(async ({ name, image }) => {
    const response = await fetch(image);
    if (!response.ok) throw new Error("Could not load an image for the ZIP file.");
    const extension = imageExtension(response.headers.get("Content-Type")?.split(";")[0] ?? null);
    return [`${name}.${extension}`, new Uint8Array(await response.arrayBuffer())] as const;
  }));
  const archive = zipSync(Object.fromEntries(files), { level: 0 });
  const url = URL.createObjectURL(new Blob([new Uint8Array(archive)], { type: "application/zip" }));
  downloadImageFile(url, filename);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
