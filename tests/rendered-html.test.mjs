import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("builds a Froja production entry page", async () => {
  const html = await readFile(new URL("../dist/index.html", import.meta.url), "utf8");
  assert.match(html, /<title>Froja Image Studio<\/title>/i);
  assert.match(html, /<div id="root"><\/div>/i);
  assert.match(html, /\/assets\/index-[^"']+\.js/i);
  assert.match(html, /\/assets\/index-[^"']+\.css/i);
  assert.doesNotMatch(html, /CivilAI|Aether Image Studio/i);
});

test("keeps the main local workflows connected", async () => {
  const [page, backend] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../backend.py", import.meta.url), "utf8"),
  ]);

  for (const label of [
    "Froja Camera Lab",
    "Froja Relight",
    "Froja Repair Studio",
    "Froja Smart Edit",
    "Froja Face Studio",
    "Image to Image",
    "Inpainting",
    "Control Net",
  ]) assert.match(page, new RegExp(label));

  for (const route of [
    "/api/generate",
    "/api/image-tool",
    "/api/relight",
    "/api/repair",
    "/api/face-swap",
    "/api/joyai-edit",
    "/api/prompt-assist",
  ]) assert.match(backend, new RegExp(route.replaceAll("/", "\\/")));
});

test("keeps History, Favorites, accessibility, and enhancement actions connected", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  for (const feature of [
    "froja-generation-history",
    "Generation History",
    "Favorite Images",
    "toggleFavorite",
    "openHistoryRecord",
    "sendCurrentToEnhance",
    "previewZoomOpen",
    "froja-font-scale",
    "froja-language",
    "froja-custom-background",
  ]) assert.match(page, new RegExp(feature));
});

test("exposes every API used by the frontend", async () => {
  const [page, backend] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../backend.py", import.meta.url), "utf8"),
  ]);
  const frontendRoutes = [...page.matchAll(/fetch\((?:`|'|")(\/api\/[^`'"?$)]+)/g)]
    .map((match) => match[1]);
  assert.ok(frontendRoutes.length >= 10, "expected Froja's frontend API routes");
  for (const route of new Set(frontendRoutes)) {
    assert.ok(backend.includes(route), `backend route missing for ${route}`);
  }
});
