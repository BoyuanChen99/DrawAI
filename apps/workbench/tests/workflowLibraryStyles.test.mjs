import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("workflow library layout does not inherit case-list spacing", () => {
  const css = readFileSync(new URL("../src/workflowCanvas.css", import.meta.url), "utf8");

  const workspaceBlocks = [...css.matchAll(/\.workflow-workspace\s*\{(?<body>[^}]*)\}/g)].map((match) => match.groups?.body || "");
  const templateListBlock = css.match(/\.workflow-template-list\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const templateRowBlock = css.match(/\.workflow-template-row\s*\{(?<body>[^}]*)\}/)?.groups?.body || "";
  const workspaceGridRowBlocks = workspaceBlocks.filter((block) => /grid-row:/.test(block));

  assert.ok(workspaceBlocks.length >= 2);
  assert.ok(workspaceGridRowBlocks.length >= 2);
  for (const block of workspaceGridRowBlocks) {
    assert.match(block, /grid-row:\s*1;/);
    assert.doesNotMatch(block, /grid-row:\s*2;/);
  }
  assert.match(templateListBlock, /display:\s*grid;/);
  assert.match(templateListBlock, /grid-template-columns:\s*repeat\(auto-fill,\s*minmax\(248px,\s*1fr\)\);/);
  assert.match(templateListBlock, /align-content:\s*start;/);
  assert.match(templateListBlock, /align-items:\s*stretch;/);
  assert.match(templateListBlock, /padding:\s*24px;/);
  assert.doesNotMatch(templateListBlock, /padding:\s*104px|padding-top:\s*104px|display:\s*flex;/);
  assert.match(templateRowBlock, /width:\s*100%;/);
  assert.match(templateRowBlock, /max-width:\s*none;/);
  assert.match(templateRowBlock, /flex:\s*none;/);
});
