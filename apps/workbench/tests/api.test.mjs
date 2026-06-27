import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import ts from "../node_modules/typescript/lib/typescript.js";

test("Workbench agent settings URL keeps startup snapshot unless refresh is requested", async () => {
  const { workbenchAgentSettingsPath } = await loadApiModule();

  assert.equal(workbenchAgentSettingsPath(), "/api/workbench/agent-settings");
  assert.equal(workbenchAgentSettingsPath(true, true), "/api/workbench/agent-settings?refresh_agents=true");
  assert.equal(workbenchAgentSettingsPath(false, true), "/api/workbench/agent-settings?include_agents=false");
});

test("API preset logo resolver URL encodes the base URL", async () => {
  const { apiPresetLogoPath } = await loadApiModule();

  assert.equal(
    apiPresetLogoPath("https://api.apimart.ai/v1/images/generations"),
    "/api/workbench/api-preset-logo?base_url=https%3A%2F%2Fapi.apimart.ai%2Fv1%2Fimages%2Fgenerations"
  );
});

let apiModulePromise;

function loadApiModule() {
  apiModulePromise ||= loadTsModule("../src/api.ts");
  return apiModulePromise;
}

async function loadTsModule(relativePath) {
  const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2020
    }
  });
  const dir = mkdtempSync(join(tmpdir(), "drawai-workbench-api-"));
  const modulePath = join(dir, `${relativePath.split("/").at(-1).replace(/\.ts$/, "")}.mjs`);
  writeFileSync(modulePath, outputText);
  return import(pathToFileURL(modulePath).href);
}
