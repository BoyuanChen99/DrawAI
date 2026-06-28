import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("deleting the active batch clears stale selection before the next refresh", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const body = source.match(/async function deleteTaskBatch\(batchId: string\) \{(?<body>[\s\S]*?)\n  \}/)?.groups?.body || "";

  assert.match(body, /const deletingActiveBatch = activeBatch\?\.batch\.batch_id === batchId;/);
  assert.match(body, /if \(deletingActiveBatch\) \{\s*clearActiveBatchSelection\(\);\s*\}/);
  assert.ok(body.indexOf("clearActiveBatchSelection();") < body.indexOf("const nextBatches = await refreshBatches();"));
});

test("polling a deleted active batch clears state instead of surfacing batch not found", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const body = source.match(/const timer = window\.setInterval\(async \(\) => \{(?<body>[\s\S]*?)\n    \}, 2500\);/)?.groups?.body || "";

  assert.match(body, /catch \(err\) \{\s*if \(isDrawAiApiStatus\(err, 404\)\) \{\s*clearActiveBatchSelection\(\);\s*return;\s*\}/);
  assert.ok(body.indexOf("const detail = await getBatch(activeBatch.batch.batch_id);") < body.indexOf("clearActiveBatchSelection();"));
});
