import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import ts from "../node_modules/typescript/lib/typescript.js";

const EXPECTED_PROCESSOR_IDS = [
  "no_process",
  "crop",
  "crop_nobg",
  "svg_self_draw",
  "image_generate",
  "image_edit",
  "chart_rebuild_reserved",
  "sam_parse",
  "ocr_parse",
  "page_spec_fuse",
  "asset_prepare",
  "asset_planner",
  "asset_processors"
];

test("processor icon mapping covers asset and workflow processors", async () => {
  const { PROCESSOR_ICON_URLS, processorIconUrlForId } = await loadProcessorIconUrlModule();

  for (const processorId of EXPECTED_PROCESSOR_IDS) {
    const iconUrl = processorIconUrlForId(processorId);
    assert.equal(iconUrl, PROCESSOR_ICON_URLS[processorId], processorId);
    assert.match(iconUrl, /^\/processor-icons\/.+\.svg$/, processorId);
    assert.equal(existsSync(new URL(`../public${iconUrl}`, import.meta.url)), true, iconUrl);
  }
});

test("processor icon lookup trims ids and returns null for unknown processors", async () => {
  const { processorIconUrlForId } = await loadProcessorIconUrlModule();

  assert.equal(processorIconUrlForId(" crop "), "/processor-icons/crop.svg");
  assert.equal(processorIconUrlForId("not_registered"), null);
});

let processorIconUrlModulePromise;

function loadProcessorIconUrlModule() {
  processorIconUrlModulePromise ||= loadTsModule("../src/processorIconUrls.ts");
  return processorIconUrlModulePromise;
}

async function loadTsModule(relativePath) {
  const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2020
    }
  });
  const dir = mkdtempSync(join(tmpdir(), "drawai-processor-icon-urls-"));
  const modulePath = join(dir, `${relativePath.split("/").at(-1).replace(/\.ts$/, "")}.mjs`);
  writeFileSync(modulePath, outputText);
  return import(pathToFileURL(modulePath).href);
}
