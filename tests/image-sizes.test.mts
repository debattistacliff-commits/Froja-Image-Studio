import { test } from "node:test";
import assert from "node:assert/strict";
import { SIZE_PRESETS, aspectName, describeSize, qualityName } from "../app/image-sizes.ts";

test("every preset is a size every model can make (multiples of 16)", () => {
  for (const p of SIZE_PRESETS) {
    assert.equal(p.w % 16, 0, `${p.label} width`);
    assert.equal(p.h % 16, 0, `${p.label} height`);
  }
});

test("well-known shapes get their usual names", () => {
  assert.equal(aspectName(1920, 1088), "16:9");
  assert.equal(aspectName(1088, 1920), "9:16");
  assert.equal(aspectName(1024, 1024), "1:1");
  assert.equal(aspectName(832, 1216), "2:3");
  assert.equal(aspectName(1216, 832), "3:2");
});

test("quality names follow video conventions", () => {
  assert.equal(qualityName(1280, 720), "HD 720p");
  assert.equal(qualityName(1920, 1088), "Full HD 1080p");
  assert.equal(qualityName(3840, 2160), "4K");
  assert.equal(qualityName(512, 512), "SD");
});

test("one readable line with the real size", () => {
  assert.equal(describeSize(1920, 1088), "1920 × 1088 px · 16:9 · Full HD 1080p · 2.1 MP");
  assert.equal(describeSize(0, 0), "");
});
