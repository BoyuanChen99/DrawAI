import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("settings overview is split into engine choices and node settings", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  const overviewCallBlock = source.match(/<SettingsOverviewPage[\s\S]*?\/>/)?.[0] || "";
  const overviewFunctionBlock = source.match(/function SettingsOverviewPage\([\s\S]*?\n}\n\nfunction apiPresetsWithImageGenMigration/)?.[0] || "";

  assert.match(source, /selectedLlmPreset=\{selectedLlmPreset\}/);
  assert.match(source, /processorDefinitions=\{processorDefinitions\}/);
  assert.match(source, /processorDrafts=\{processorDrafts\}/);
  assert.match(source, /onChooseLlm=\{\(\) => openLlmSettings\(selectedLlmPresetId\)\}/);
  assert.match(source, /onOpenProcessorSettings=\{\(\) => \{\s*setSelectedProcessorId\(selectedProcessorId \|\| processorIds\[0\] \|\| ""\);\s*setSettingsDetailTarget\(null\);\s*setSettingsCategory\("processor"\);\s*\}\}/);
  assert.match(source, /const selectedLlmPresetIcon = selectedLlmPreset\s*\?\s*apiPresetIconForPreset\(selectedLlmPreset, apiPresetResolvedLogo\(apiPresetLogoUrls, selectedLlmPreset\)\)\s*:\s*null;/);
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
  assert.doesNotMatch(overviewCallBlock, /selectedImageGenMethod|imageGenMethodCount|onChooseImageGen/);
  assert.doesNotMatch(overviewFunctionBlock, /选择图像生成方式|selectedImageGenMethod|imageGenMethodCount|onChooseImageGen/);

  assert.match(css, /\.settings-overview-section\s*\{/);
  assert.match(css, /\.settings-overview-engines\s*\{/);
  assert.match(css, /\.settings-overview-engine\s*\{/);
  assert.match(css, /\.settings-overview-node-icons\s*\{/);
  assert.match(css, /\.settings-overview-node-icon\s*\{[\s\S]*?width:\s*34px;/);
});

test("API and LLM preset cards and detail surfaces show provider logos", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const apiGridBlock = source.match(/\{settingsCategory === "api" && \([\s\S]*?<div className="settings-model-grid" aria-label="API 预设">[\s\S]*?\{apiDrafts\.map\(\(preset, presetIndex\) =>[\s\S]*?\)\}\s*<button/)?.[0] || "";
  const llmGridBlock = source.match(/\{settingsCategory === "llm" && \([\s\S]*?<div className="settings-model-grid" aria-label="LLM 预设">[\s\S]*?\{llmPresets\.map\(\(preset\) =>[\s\S]*?\)\}\s*<\/div>/)?.[0] || "";
  const llmDetailBlock = source.match(/\{settingsCategory === "llm" && \([\s\S]*?<label className="settings-field">[\s\S]*?Extra Body/)?.[0] || "";

  assert.match(apiGridBlock, /const presetIcon = apiPresetIconForPreset\(preset, apiPresetResolvedLogo\(apiPresetLogoUrls, preset\)\);/);
  assert.match(apiGridBlock, /<PresetIconImage icon=\{presetIcon\} fallback=\{<SettingsNavIcon icon="api" \/>\} \/>/);
  assert.match(llmGridBlock, /const presetIcon = apiPresetIconForPreset\(preset, apiPresetResolvedLogo\(apiPresetLogoUrls, preset\)\);/);
  assert.match(llmGridBlock, /className=\{`settings-model-icon\$\{presetIcon \? " settings-provider-logo-mini" : ""\}`\}/);
  assert.match(llmGridBlock, /<PresetIconImage icon=\{presetIcon\} fallback=\{<SettingsNavIcon icon="llm" \/>\} \/>/);
  assert.match(llmDetailBlock, /settings-summary-row settings-llm-summary/);
  assert.match(llmDetailBlock, /<PresetIconImage icon=\{selectedLlmPresetIcon\} fallback=\{<SettingsNavIcon icon="llm" \/>\} \/>/);
  assert.match(source, /resolveApiPresetLogo/);
  assert.match(source, /function PresetIconImage/);
  assert.match(source, /onError=\{\(\) => setFailedIconUrl\(icon\.icon_url\)\}/);
  assert.doesNotMatch(source, /<span>Logo URL<\/span>/);
  assert.doesNotMatch(source, /logo_url/);
});
