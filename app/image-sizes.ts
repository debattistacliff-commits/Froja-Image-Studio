/** Picture sizes with names people know (720p, 1080p, Stories...). Sizes are multiples of 16 so every model can make them. */
export type SizePreset = { w: number; h: number; label: string; group: "Square" | "Portrait" | "Landscape" };

export const SIZE_PRESETS: SizePreset[] = [
  { w: 512, h: 512, label: "Small square · quick tests", group: "Square" },
  { w: 768, h: 768, label: "Square", group: "Square" },
  { w: 1024, h: 1024, label: "Square · 1 MP", group: "Square" },
  { w: 1088, h: 1088, label: "Instagram square (≈1080 × 1080)", group: "Square" },
  { w: 832, h: 1216, label: "Portrait 2:3", group: "Portrait" },
  { w: 1024, h: 1536, label: "Portrait 2:3 · large", group: "Portrait" },
  { w: 768, h: 1344, label: "Vertical 9:16", group: "Portrait" },
  { w: 1088, h: 1920, label: "Full HD vertical · Stories / Reels (≈1080 × 1920)", group: "Portrait" },
  { w: 1216, h: 832, label: "Landscape 3:2", group: "Landscape" },
  { w: 1536, h: 1024, label: "Landscape 3:2 · large", group: "Landscape" },
  { w: 1344, h: 768, label: "Widescreen 16:9", group: "Landscape" },
  { w: 1280, h: 720, label: "HD 720p", group: "Landscape" },
  { w: 1920, h: 1088, label: "Full HD 1080p (≈1920 × 1080)", group: "Landscape" },
];

function gcd(a: number, b: number): number {
  return b ? gcd(b, a % b) : a;
}

/** Nearest well-known shape name, e.g. 1920×1088 -> "16:9". */
export function aspectName(w: number, h: number): string {
  if (!w || !h) return "";
  const known: [string, number][] = [["1:1", 1], ["16:9", 16 / 9], ["9:16", 9 / 16], ["3:2", 1.5], ["2:3", 2 / 3], ["4:3", 4 / 3], ["3:4", 0.75], ["21:9", 21 / 9], ["4:5", 0.8], ["5:4", 1.25]];
  const ratio = w / h;
  const [name, value] = known.reduce((best, item) => (Math.abs(item[1] - ratio) < Math.abs(best[1] - ratio) ? item : best));
  if (Math.abs(value - ratio) / value < 0.03) return name;
  const g = gcd(w, h);
  return `${w / g}:${h / g}`;
}

/** Video-style quality name from the short side: 720p, 1080p, 2K, 4K... */
export function qualityName(w: number, h: number): string {
  const short = Math.min(w, h), long = Math.max(w, h);
  if (short >= 2100 || long >= 3800) return "4K";
  if (short >= 1400 || long >= 2500) return "2K / QHD";
  if (short >= 1060 || long >= 1900) return "Full HD 1080p";
  if (short >= 700 || long >= 1260) return "HD 720p";
  return "SD";
}

/** One readable line for a picture: "1920 × 1088 px · 16:9 · Full HD 1080p · 2.1 MP". */
export function describeSize(w: number, h: number): string {
  if (!w || !h) return "";
  const mp = (w * h) / 1_000_000;
  return `${w} × ${h} px · ${aspectName(w, h)} · ${qualityName(w, h)} · ${mp.toFixed(1)} MP`;
}

export function presetFor(w: number, h: number): SizePreset | undefined {
  return SIZE_PRESETS.find((p) => p.w === w && p.h === h);
}
