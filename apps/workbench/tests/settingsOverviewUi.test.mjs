import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("settings overview is split into engine choices and node settings", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

  assert.match(source, /selectedLlmPreset=\{selectedLlmPreset\}/);
  assert.match(source, /processorDefinitions=\{processorDefinitions\}/);
  assert.match(source, /processorDrafts=\{processorDrafts\}/);
  assert.match(source, /onChooseLlm=\{\(\) => openLlmSettings\(selectedLlmPresetId\)\}/);
  assert.match(source, /onOpenProcessorSettings=\{\(\) => \{\s*setSelectedProcessorId\(selectedProcessorId \|\| processorIds\[0\] \|\| ""\);\s*setSettingsDetailTarget\(null\);\s*setSettingsCategory\("processor"\);\s*\}\}/);
  assert.match(source, /const selectedLlmPresetTemplate = selectedLlmPreset \? apiPresetTemplateForPreset\(selectedLlmPreset\) : null;/);
  assert.match(source, /const enabledOverviewProcessors = processorIds\.filter\(\(processorId\) => processorDrafts\[processorId\]\?\.enabled\);/);
  assert.match(source, /<section className="settings-overview-section settings-overview-engines"/);
  assert.match(source, /aria-label="选择默认 Agent"/);
  assert.match(source, /aria-label="选择默认 LLM 配置"/);
  assert.match(source, /<section className="settings-overview-section settings-overview-nodes"/);
  assert.match(source, /className="settings-overview-node-icons"/);
  assert.match(source, /enabledOverviewProcessors\.map\(\(processorId\) =>/);
  assert.match(source, /className="settings-overview-node-icon"/);
  assert.match(source, /aria-label="打开处理器设置"/);
  assert.doesNotMatch(source, /settings-overview-hero/);
  assert.doesNotMatch(source, /settings-overview-lanes/);

  assert.match(css, /\.settings-overview-section\s*\{/);
  assert.match(css, /\.settings-overview-engines\s*\{/);
  assert.match(css, /\.settings-overview-engine\s*\{/);
  assert.match(css, /\.settings-overview-node-icons\s*\{/);
  assert.match(css, /\.settings-overview-node-icon\s*\{[\s\S]*?width:\s*34px;/);
});

test("LLM preset cards and detail surfaces show provider logos", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const llmGridBlock = source.match(/\{settingsCategory === "llm" && \([\s\S]*?<div className="settings-model-grid" aria-label="LLM 预设">[\s\S]*?\{llmPresets\.map\(\(preset\) =>[\s\S]*?\)\}\s*<\/div>/)?.[0] || "";
  const llmDetailBlock = source.match(/\{settingsCategory === "llm" && \([\s\S]*?<label className="settings-field">[\s\S]*?Extra Body/)?.[0] || "";

  assert.match(llmGridBlock, /const presetTemplate = apiPresetTemplateForPreset\(preset\);/);
  assert.match(llmGridBlock, /className=\{`settings-model-icon\$\{presetTemplate \? " settings-provider-logo-mini" : ""\}`\}/);
  assert.match(llmGridBlock, /presetTemplate \? <img src=\{presetTemplate\.icon_url\} alt="" \/> : <SettingsNavIcon icon="llm" \/>/);
  assert.match(llmDetailBlock, /settings-summary-row settings-llm-summary/);
  assert.match(llmDetailBlock, /selectedLlmPresetTemplate \? <img src=\{selectedLlmPresetTemplate\.icon_url\} alt="" \/> : <SettingsNavIcon icon="llm" \/>/);
});
