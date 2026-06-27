import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("upload LLM mode card shows a yellow warning tooltip", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  const llmCardBlock = source.match(/className=\{selectedExecutionMode === "llm"[\s\S]*?<\/button>/)?.[0] || "";
  const warningBlock = css.match(/\.upload-mode-warning\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const llmCardCss = css.match(/\.upload-mode-card-llm\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";

  assert.match(llmCardBlock, /upload-mode-card upload-mode-card-llm active/);
  assert.match(llmCardBlock, /data-tooltip="LLM使用单次调用，效果会显著弱于Agent模式"/);
  assert.match(llmCardBlock, /title="LLM使用单次调用，效果会显著弱于Agent模式"/);
  assert.match(llmCardBlock, /aria-label="LLM使用单次调用，效果会显著弱于Agent模式"/);
  assert.match(llmCardBlock, /<svg viewBox="0 0 24 24" aria-hidden="true">/);
  assert.match(llmCardCss, /grid-template-columns:\s*38px minmax\(0,\s*1fr\) 24px;/);
  assert.match(warningBlock, /background:\s*#fffbeb;/);
  assert.match(warningBlock, /color:\s*#b45309;/);
  assert.match(css, /\.upload-mode-warning\[data-tooltip\]::after\s*\{[\s\S]*?content:\s*attr\(data-tooltip\);/);
  assert.match(css, /\.upload-mode-warning:hover::after\s*\{/);
});
