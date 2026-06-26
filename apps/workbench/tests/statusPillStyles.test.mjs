import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("batch status lights use tag colors while case status tags stay visible", () => {
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  const statusLightBlock = css.match(/\.status-light\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const queuedBlock = css.match(/\.status-light\.status-queued,[\s\S]*?\.status-light\.status-canceled\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const runningBlock = css.match(/\.status-light\.status-running,[\s\S]*?\.status-light\.status-svg_running\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const completedBlock = css.match(/\.status-light\.status-completed\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const reviewBlock = css.match(/\.status-light\.status-assets_review,[\s\S]*?\.status-light\.status-waiting_review\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const caseStatusPillBlock = css.match(/\.task-row \.status-pill\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const caseCompletedBlock = css.match(/\.task-row \.status-completed\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const statusBarRunningBlock = css.match(/\.task-batch-status-bar\.batch-status-running \.task-batch-status-dot,[\s\S]*?\.task-batch-status-bar\.batch-status-svg_running \.task-batch-status-dot\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const statusBarCompletedBlock = css.match(/\.task-batch-status-bar\.batch-status-completed \.task-batch-status-dot\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";

  assert.match(statusLightBlock, /width:\s*10px;/);
  assert.match(statusLightBlock, /height:\s*10px;/);
  assert.match(queuedBlock, /background:\s*#475569;/);
  assert.match(runningBlock, /background:\s*#2563eb;/);
  assert.match(completedBlock, /background:\s*#059669;/);
  assert.match(reviewBlock, /background:\s*#d97706;/);
  assert.match(caseStatusPillBlock, /color:\s*#ffffff;/);
  assert.match(caseStatusPillBlock, /font-weight:\s*650;/);
  assert.match(caseCompletedBlock, /background:\s*#059669;/);
  assert.match(statusBarRunningBlock, /background:\s*#2563eb;/);
  assert.match(statusBarCompletedBlock, /background:\s*#059669;/);
});
