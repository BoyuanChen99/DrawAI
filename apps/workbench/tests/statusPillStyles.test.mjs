import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("batch rail status tags share the dark case status treatment", () => {
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  const statusPillBlock = css.match(/\.batch-row-main \.status-pill,\s*\.task-row \.status-pill\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const queuedBlock = css.match(/\.batch-row-main \.status-queued,[\s\S]*?\.task-row \.status-canceled\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const runningBlock = css.match(/\.batch-row-main \.status-running,[\s\S]*?\.task-row \.status-svg_running\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const completedBlock = css.match(/\.batch-row-main \.status-completed,\s*\.task-row \.status-completed\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const reviewBlock = css.match(/\.batch-row-main \.status-assets_review,[\s\S]*?\.task-row \.status-waiting_review\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";

  assert.match(statusPillBlock, /color:\s*#ffffff;/);
  assert.match(statusPillBlock, /font-weight:\s*650;/);
  assert.match(queuedBlock, /background:\s*#475569;/);
  assert.match(runningBlock, /background:\s*#2563eb;/);
  assert.match(completedBlock, /background:\s*#059669;/);
  assert.match(reviewBlock, /background:\s*#d97706;/);
});
