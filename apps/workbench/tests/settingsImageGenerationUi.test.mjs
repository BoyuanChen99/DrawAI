import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("settings engine includes image generation method cards and picker modal", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

  assert.match(source, /type WorkbenchSettingsCategory = "overview" \| "api" \| "agent" \| "llm" \| "imagegen" \| "processor";/);
  assert.match(source, /\{ id: "imagegen", label: "图像生成", icon: "imagegen" \}/);
  assert.match(source, /imageGenMethodCards\(imageGenConnectionDraft, apiDrafts, sortedAgents\)/);
  assert.match(source, /<div className="settings-model-grid" aria-label="图像生成方式">/);
  assert.match(source, /imageGenMethodCardsList\.map\(\(method\) =>/);
  assert.match(source, /className=\{`settings-model-card settings-imagegen-method-card\$\{method\.selected \? " active" : ""\}\$\{method\.available \? "" : " missing"\}`\}/);
  assert.match(source, /setImageGenDialogMode\("choose_method"\)/);
  assert.match(source, /aria-label="选择图像生成方式"/);
  assert.match(source, /imageGenMethodPickerOptions\(imageApiPresets, sortedAgents\)\.map\(\(option\) =>/);
  assert.match(source, /kind: "codex_builtin"/);
  assert.match(source, /kind: "api_preset"/);
  assert.match(source, /kind: "custom"/);
  assert.match(source, /settingsCategory === "imagegen"/);
  assert.match(source, /<span>模型<\/span>[\s\S]*?value=\{imageGenConnectionDraft\.model\}/);
  assert.match(source, /ImageGenStudio[\s\S]*?connection=\{imageGenConnection\}[\s\S]*?setWorkbenchSettingsInitialCategory\("imagegen"\)[\s\S]*?setWorkbenchSettingsOpen\(true\)/);
  assert.doesNotMatch(source, /<Segmented[\s\S]*?options=\{PROVIDERS\}/);

  assert.match(css, /\.settings-imagegen-method-card\s*\{/);
  assert.match(css, /\.settings-imagegen-summary\s*\{/);
  assert.match(css, /\.gen-method-summary\s*\{/);
});
