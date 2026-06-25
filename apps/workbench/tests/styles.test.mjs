import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("image result overlays stay inside their canvas stacking context", () => {
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  const block = css.match(/\.image-overlay-wrap\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";

  assert.match(block, /isolation:\s*isolate;/);
});
