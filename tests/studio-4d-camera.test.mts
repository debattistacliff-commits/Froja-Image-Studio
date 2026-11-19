import assert from "node:assert/strict";
import { test } from "node:test";
import { dragCamera, snapCamera } from "../app/studio-4d-camera.ts";

const front = { azimuth: 0, elevation: "eye", distance: "medium" } as const;
const radius = 100;

test("a radius of horizontal travel rotates the camera by 90 degrees", () => {
  assert.deepEqual(dragCamera(front, radius, 30, radius), { ...front, azimuth: 90 });
  assert.equal(dragCamera(front, -radius, 0, radius).azimuth, 270);
  assert.equal(dragCamera({ ...front, azimuth: 315 }, radius, 0, radius).azimuth, 45);
});

test("the drag stays continuous and its target snaps to the nearest 45 degrees", () => {
  const drag = dragCamera(front, radius / 3, 0, radius);
  assert.equal(drag.azimuth, 30);
  assert.equal(snapCamera(drag).azimuth, 45);
  assert.equal(snapCamera(dragCamera(front, -10, 0, radius)).azimuth, 0);
});

test("height holds through 35% vertical drift and changes beyond it", () => {
  assert.equal(dragCamera(front, radius, 35, radius).elevation, "eye");
  assert.equal(dragCamera(front, radius, -35, radius).elevation, "eye");
  assert.equal(dragCamera(front, radius, 36, radius).elevation, "low");
  assert.equal(dragCamera(front, radius, -36, radius).elevation, "high");
  assert.equal(dragCamera({ ...front, elevation: "high" }, radius, 0, radius).elevation, "high");
});
