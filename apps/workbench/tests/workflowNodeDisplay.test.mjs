import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import ts from "../node_modules/typescript/lib/typescript.js";

test("DAG run heading uses task id instead of source filename", async () => {
  const { dagRunCaseIdentifier } = await loadDisplayModule();

  assert.equal(dagRunCaseIdentifier({ case_id: "case_abc123", name: "微信图片.png" }), "case_abc123");
});

test("workflow node info rows expose actual agent and API preset labels", async () => {
  const { workflowNodeExtraInfoRows } = await loadDisplayModule();
  const rows = workflowNodeExtraInfoRows({
    node: workflowNode("page_spec_refine", "agent", { provider_id: "codex_sdk", model: "codex-default" }),
    nodeRun: {
      node_id: "page_spec_refine",
      attempt_id: "001",
      status: "ok",
      provider_id: "hermes_acp",
      provider_label: "Hermes ACP",
      resource_id: "agent_provider:hermes_acp"
    },
    metadata: {
      node_id: "page_spec_refine",
      node_type: "agent",
      provider_id: "kimi_cli",
      provider_label: "Kimi CLI",
      model: "kimi-code/kimi-for-coding",
      api_presets: [
        {
          processing_type: "image_generate",
          api_preset_id: "apimart_images",
          api_preset_label: "Apimart Images"
        }
      ]
    }
  });

  assert.deepEqual(rows, [
    { label: "Agent", value: "Hermes ACP" },
    { label: "Provider ID", value: "hermes_acp" },
    { label: "Model", value: "kimi-code/kimi-for-coding" },
    { label: "API Preset", value: "Apimart Images" }
  ]);
});

let displayModulePromise;

function loadDisplayModule() {
  displayModulePromise ||= loadTsModule("../src/workflowNodeDisplay.ts");
  return displayModulePromise;
}

async function loadTsModule(relativePath) {
  const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2020
    }
  });
  const dir = mkdtempSync(join(tmpdir(), "drawai-workflow-node-display-"));
  const modulePath = join(dir, `${relativePath.split("/").at(-1).replace(/\.ts$/, "")}.mjs`);
  writeFileSync(modulePath, outputText);
  return import(pathToFileURL(modulePath).href);
}

function workflowNode(nodeId, nodeType, config = {}) {
  return {
    node_id: nodeId,
    node_type: nodeType,
    title: nodeId,
    inputs: [],
    outputs: [],
    config,
    position: {},
    description: ""
  };
}
