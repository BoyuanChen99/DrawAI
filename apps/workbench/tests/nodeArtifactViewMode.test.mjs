import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import ts from "../node_modules/typescript/lib/typescript.js";

test("node artifact viewer opens Agent log when no artifact is available but logs exist", async () => {
  const { defaultWorkflowNodeArtifactViewMode } = await loadViewModeModule();

  assert.equal(
    defaultWorkflowNodeArtifactViewMode({
      available: false,
      agent_logs: {
        files: [],
        trace_events: [],
        session_summary: null,
        session_events: [{ type: "message", summary: "done" }],
        runtime_log_tail: []
      }
    }),
    "agent_log"
  );
});

test("node artifact viewer opens artifact mode when non-bbox artifacts exist", async () => {
  const { defaultWorkflowNodeArtifactViewMode } = await loadViewModeModule();

  assert.equal(
    defaultWorkflowNodeArtifactViewMode({
      available: false,
      artifacts: [
        {
          artifact_id: "output:nodes/svg_compose/runs/001/output/semantic.svg",
          kind: "svg",
          role: "accepted",
          exists: true,
          url: "/api/cases/case/files/nodes/svg_compose/runs/001/output/semantic.svg"
        }
      ],
      agent_logs: {
        files: [],
        trace_events: [],
        session_summary: null,
        session_events: [{ type: "message", summary: "done" }],
        runtime_log_tail: []
      }
    }),
    "artifact"
  );
});

test("node artifact viewer keeps artifact mode for drawable output", async () => {
  const { defaultWorkflowNodeArtifactViewMode } = await loadViewModeModule();

  assert.equal(
    defaultWorkflowNodeArtifactViewMode({
      available: true,
      agent_logs: {
        files: [],
        trace_events: [],
        session_summary: { final_response: "done" },
        session_events: [],
        runtime_log_tail: []
      }
    }),
    "artifact"
  );
});

test("node artifact viewer keeps artifact mode when neither artifact nor logs exist", async () => {
  const { defaultWorkflowNodeArtifactViewMode } = await loadViewModeModule();

  assert.equal(
    defaultWorkflowNodeArtifactViewMode({
      available: false,
      agent_logs: {
        files: [],
        trace_events: [],
        session_summary: null,
        session_events: [],
        runtime_log_tail: []
      }
    }),
    "artifact"
  );
});

let viewModeModulePromise;

function loadViewModeModule() {
  viewModeModulePromise ||= loadTsModule("../src/nodeArtifactViewMode.ts");
  return viewModeModulePromise;
}

async function loadTsModule(relativePath) {
  const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2020
    }
  });
  const dir = mkdtempSync(join(tmpdir(), "drawai-node-artifact-view-mode-"));
  const modulePath = join(dir, `${relativePath.split("/").at(-1).replace(/\.ts$/, "")}.mjs`);
  writeFileSync(modulePath, outputText);
  return import(pathToFileURL(modulePath).href);
}
