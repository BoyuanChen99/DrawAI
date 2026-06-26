import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("image result overlays stay inside their canvas stacking context", () => {
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  const block = css.match(/\.image-overlay-wrap\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";

  assert.match(block, /isolation:\s*isolate;/);
});

test("left task rail renders task time above the task title without moving status tags", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  const batchMainBlock = source.match(/<div className="batch-row-main">[\s\S]*?<span className=\{`status-pill status-\$\{batch\.status\}`\}>/)?.[0] || "";
  const taskMainBlock = source.match(/<div className="task-main">[\s\S]*?<strong>\{item\.name\}<\/strong>/)?.[0] || "";
  const batchRowMainCss = css.match(/\.batch-row-main\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const batchTitleCss = css.match(/\.batch-row-title\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const batchTimeCss = css.match(/\.batch-created-at\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";

  assert.match(batchMainBlock, /<div className="batch-row-title">[\s\S]*?<time className="batch-created-at" dateTime=\{batch\.created_at\}>\{submittedTimeText\(batch\.created_at\)\}<\/time>[\s\S]*?<strong>\{batch\.name\}<\/strong>[\s\S]*?<\/div>\s*<span className=\{`status-pill status-\$\{batch\.status\}`\}>/);
  assert.doesNotMatch(taskMainBlock, /task-created-at|batch-created-at|submittedTimeText|item\.created_at/);
  assert.match(batchRowMainCss, /grid-template-columns:\s*minmax\(0,\s*1fr\) auto;/);
  assert.match(batchTitleCss, /align-content:\s*center;/);
  assert.match(batchTitleCss, /gap:\s*2px;/);
  assert.match(batchTimeCss, /font-size:\s*10px;/);
  assert.match(batchTimeCss, /line-height:\s*1\.15;/);
});
