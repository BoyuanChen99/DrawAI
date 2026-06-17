import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createUploadBatch, generateImages } from "./api";
import type { BatchDetail, ImageGenerationRequest, ImageGenerationResponse } from "./types";

/**
 * Generation studio for the OpenAI Images API.
 *
 * Request shape (POST /v1/images/generations):
 *   model, prompt, size, quality, background, moderation,
 *   output_format, n
 */

const DEFAULT_MODEL = "gpt-image-2";
const DEFAULT_MODERATION = "auto";
const DEFAULT_OUTPUT_FORMAT = "png";

type Resolution = "1k" | "2k" | "4k";
type Quality = "auto" | "low" | "medium" | "high";
type Background = "auto" | "opaque" | "transparent";
type OutputFormat = "png";
type RightMode = "stage" | "grid";

const SIZE_PRESETS = [
  "auto",
  "1:1",
  "3:2",
  "2:3",
  "4:3",
  "3:4",
  "5:4",
  "4:5",
  "16:9",
  "9:16",
  "2:1",
  "1:2",
  "3:1",
  "1:3",
  "21:9",
  "9:21"
] as const;

const OPENAI_SIZE_BY_RATIO: Record<Resolution, Record<string, string>> = {
  "1k": {
    auto: "auto",
    "1:1": "1024x1024",
    "3:2": "1536x1024",
    "2:3": "1024x1536",
    "4:3": "1024x768",
    "3:4": "768x1024",
    "5:4": "1280x1024",
    "4:5": "1024x1280",
    "16:9": "1536x864",
    "9:16": "864x1536",
    "2:1": "2048x1024",
    "1:2": "1024x2048",
    "3:1": "1536x512",
    "1:3": "512x1536",
    "21:9": "2016x864",
    "9:21": "864x2016"
  },
  "2k": {
    auto: "auto",
    "1:1": "2048x2048",
    "3:2": "2048x1360",
    "2:3": "1360x2048",
    "4:3": "2048x1536",
    "3:4": "1536x2048",
    "5:4": "2560x2048",
    "4:5": "2048x2560",
    "16:9": "2048x1152",
    "9:16": "1152x2048",
    "2:1": "2688x1344",
    "1:2": "1344x2688",
    "3:1": "3072x1024",
    "1:3": "1024x3072",
    "21:9": "2688x1152",
    "9:21": "1152x2688"
  },
  "4k": {
    auto: "auto",
    "1:1": "2880x2880",
    "3:2": "3520x2336",
    "2:3": "2336x3520",
    "4:3": "3312x2480",
    "3:4": "2480x3312",
    "5:4": "3216x2576",
    "4:5": "2576x3216",
    "16:9": "3840x2160",
    "9:16": "2160x3840",
    "2:1": "3840x1920",
    "1:2": "1920x3840",
    "3:1": "3840x1280",
    "1:3": "1280x3840",
    "21:9": "3840x1648",
    "9:21": "1648x3840"
  }
};

const RESOLUTIONS: Array<{ value: Resolution; label: string; hint: string }> = [
  { value: "1k", label: "1K", hint: "1024" },
  { value: "2k", label: "2K", hint: "2048" },
  { value: "4k", label: "4K", hint: "3840" }
];

const QUALITIES: Array<{ value: Quality; label: string }> = [
  { value: "auto", label: "自动" },
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" }
];

const BACKGROUNDS: Array<{ value: Background; label: string }> = [
  { value: "auto", label: "自动" },
  { value: "opaque", label: "不透明" },
  { value: "transparent", label: "透明" }
];

interface GeneratedImage {
  id: string;
  url: string;
  size: string;
  resolution: Resolution;
  quality: Quality;
  format: OutputFormat;
  transparent: boolean;
  prompt: string;
}

export interface ImageGenConnectionSettings {
  baseUrl: string;
  apiKey: string;
  model: string;
}

export default function ImageGenStudio({
  connection,
  onCreated,
  onError
}: {
  connection: ImageGenConnectionSettings;
  onCreated: (detail: BatchDetail) => void | Promise<void>;
  onError: (message: string) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState<string>("4:3");
  const [resolution, setResolution] = useState<Resolution>("1k");
  const [quality, setQuality] = useState<Quality>("auto");
  const [background, setBackground] = useState<Background>("auto");
  const [count, setCount] = useState(1);

  const [images, setImages] = useState<GeneratedImage[]>([]);
  const [selected, setSelected] = useState(0);
  const [rightMode, setRightMode] = useState<RightMode>("stage");
  const [generating, setGenerating] = useState(false);
  const [generationError, setGenerationError] = useState("");
  const [multiSelect, setMultiSelect] = useState(false);
  const [selectedForSubmit, setSelectedForSubmit] = useState<number[]>([]);
  const [submittingSelection, setSubmittingSelection] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const stripRef = useRef<HTMLDivElement>(null);

  const effectiveSize = openAiSizeFromPreset(size, resolution);

  const request = useMemo<ImageGenerationRequest>(() => {
    const model = connection.model.trim() || DEFAULT_MODEL;
    const body: ImageGenerationRequest = {
      model,
      prompt,
      size: effectiveSize,
      quality,
      background,
      moderation: DEFAULT_MODERATION,
      output_format: DEFAULT_OUTPUT_FORMAT,
      n: count
    };
    const apiBaseUrl = connection.baseUrl.trim();
    const apiKey = connection.apiKey.trim();
    if (apiBaseUrl) body.api_base_url = apiBaseUrl;
    if (apiKey) body.api_key = apiKey;
    return body;
  }, [
    prompt,
    effectiveSize,
    quality,
    background,
    count,
    connection.apiKey,
    connection.baseUrl,
    connection.model
  ]);

  // Keep the selected thumbnail centered in the filmstrip. Clamping to the
  // scroll bounds means the first image rests at the left edge and the last at
  // the right edge automatically.
  useEffect(() => {
    if (rightMode !== "stage") return;
    const strip = stripRef.current;
    if (!strip) return;
    const thumb = strip.querySelector<HTMLElement>(`[data-thumb="${selected}"]`);
    if (!thumb) return;
    const target = thumb.offsetLeft - (strip.clientWidth - thumb.clientWidth) / 2;
    const max = strip.scrollWidth - strip.clientWidth;
    strip.scrollTo({ left: Math.max(0, Math.min(target, max)), behavior: "smooth" });
  }, [selected, rightMode, images.length]);

  // Arrow keys move the selection while in stage mode.
  useEffect(() => {
    if (rightMode !== "stage") return;
    function onKey(event: KeyboardEvent) {
      const tag = (event.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (event.key === "ArrowRight") setSelected((i) => Math.min(i + 1, images.length - 1));
      if (event.key === "ArrowLeft") setSelected((i) => Math.max(i - 1, 0));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rightMode, images.length]);

  useEffect(() => {
    setSelectedForSubmit((items) => items.filter((index) => index >= 0 && index < images.length));
  }, [images.length]);

  const generate = useCallback(async () => {
    if (!prompt.trim()) return;
    setGenerating(true);
    setGenerationError("");
    try {
      const payload = await generateImages(request);
      const next = imagesFromResponse(payload, request, resolution);
      if (next.length === 0) {
        throw new Error(imageGenerationEmptyMessage(payload));
      }
      setImages(next);
      setSelected(0);
      setRightMode("stage");
      setMultiSelect(false);
      setSelectedForSubmit([]);
      setSubmitError("");
    } catch (error) {
      setGenerationError(error instanceof Error ? error.message : String(error));
    } finally {
      setGenerating(false);
    }
  }, [prompt, request, resolution]);

  const selectFromGrid = useCallback((index: number) => {
    setSelected(index);
    setRightMode("stage");
  }, []);

  const selectedForSubmitSet = useMemo(() => new Set(selectedForSubmit), [selectedForSubmit]);
  const selectedImagesForSubmit = useMemo(
    () => selectedForSubmit.map((index) => images[index]).filter((image): image is GeneratedImage => Boolean(image)),
    [images, selectedForSubmit]
  );

  const toggleGridSelection = useCallback((index: number) => {
    setSelectedForSubmit((items) => (
      items.includes(index)
        ? items.filter((item) => item !== index)
        : [...items, index].sort((a, b) => a - b)
    ));
  }, []);

  const submitSelectedImages = useCallback(async () => {
    if (selectedImagesForSubmit.length === 0 || submittingSelection) return;
    setSubmittingSelection(true);
    setSubmitError("");
    try {
      const form = new FormData();
      form.set("name", generatedBatchTitle(selectedImagesForSubmit));
      form.set("input_mode", "upload");
      form.set("max_concurrent_cases", "10");
      form.set("auto_run_svg_after_analysis", "false");
      for (const [index, image] of selectedImagesForSubmit.entries()) {
        await appendGeneratedImageToForm(form, image, index);
      }
      const detail = await createUploadBatch(form);
      setMultiSelect(false);
      setSelectedForSubmit([]);
      await onCreated(detail);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setSubmitError(message);
      onError(message);
    } finally {
      setSubmittingSelection(false);
    }
  }, [onCreated, onError, selectedImagesForSubmit, submittingSelection]);

  const current = images[selected];

  return (
    <div className="gen-root">
      <aside className="gen-controls">
        <div className="gen-form">
          <div className="gen-prompt-block">
            <textarea
              className="gen-prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="描述你想要生成的画面，例如：赛博朋克风格的城市夜景，霓虹灯倒映在湿润的街道上…"
              rows={5}
            />
          </div>

          <Field label="尺寸 / 比例" hint={effectiveSize}>
            <div className="gen-ratio-grid">
              {SIZE_PRESETS.map((preset) => {
                const active = size === preset;
                return (
                  <button
                    key={preset}
                    type="button"
                    className={`gen-ratio${active ? " active" : ""}`}
                    onClick={() => setSize(preset)}
                  >
                    <RatioGlyph ratio={preset} />
                    <span className="gen-ratio-label">{sizePresetLabel(preset)}</span>
                  </button>
                );
              })}
            </div>
          </Field>

          <Field label="质量" hint="生成质量">
            <Segmented
              options={QUALITIES.map((q) => ({ value: q.value, label: q.label }))}
              value={quality}
              onChange={(v) => setQuality(v as Quality)}
            />
          </Field>

          <Field label="背景" hint="背景模式">
            <Segmented
              options={BACKGROUNDS.map((b) => ({ value: b.value, label: b.label }))}
              value={background}
              onChange={(v) => setBackground(v as Background)}
            />
          </Field>
        </div>

        <footer className="gen-controls-foot">
          <div className="gen-generate-row">
            <div className="gen-resolution-compact">
              <span className="gen-field-label">像素等级</span>
              <Segmented
                options={RESOLUTIONS.map((r) => ({ value: r.value, label: r.label }))}
                value={resolution}
                onChange={(v) => setResolution(v as Resolution)}
              />
            </div>
            <div className="gen-count-compact" aria-label="生成数量">
              <Stepper value={count} min={1} max={10} onChange={setCount} />
            </div>
            <button
              type="button"
              className={`primary gen-generate${generating ? " running" : ""}`}
              onClick={generate}
              disabled={generating || !prompt.trim()}
            >
              {generating ? <span className="button-spinner" /> : null}
              {generating ? "生成中…" : "生成"}
            </button>
          </div>
          {generationError && <p className="gen-error">{generationError}</p>}
        </footer>
      </aside>

      <section className={`gen-display ${rightMode}`}>
        {rightMode === "stage" ? (
          <>
            <div className="gen-stage">
              {current ? (
                <figure className={`gen-stage-figure${current.transparent ? " checker" : ""}`}>
                  <img src={current.url} alt={current.prompt || "生成图"} />
                </figure>
              ) : (
                <div className="gen-empty">还没有图片，填写提示词后点击生成</div>
              )}
              {current && (
                <div className="gen-stage-meta">
                  <span className="gen-meta-chip">{current.size}</span>
                  <span className="gen-meta-chip">{current.resolution.toUpperCase()}</span>
                  <span className="gen-meta-chip">{current.format.toUpperCase()}</span>
                  <span className="gen-meta-chip">质量 {optionLabel(QUALITIES, current.quality)}</span>
                  <span className="gen-meta-index">
                    {selected + 1} / {images.length}
                  </span>
                  <a className="gen-meta-download" href={current.url} download={`${current.id}.${current.format}`}>
                    下载
                  </a>
                </div>
              )}
            </div>

            <div className="gen-filmstrip-wrap">
              <div className="gen-filmstrip" ref={stripRef}>
                {images.map((img, i) => (
                  <button
                    key={img.id}
                    type="button"
                    data-thumb={i}
                    className={`gen-thumb${i === selected ? " active" : ""}${
                      img.transparent ? " checker" : ""
                    }`}
                    onClick={() => setSelected(i)}
                  >
                    <img src={img.url} alt="" />
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="gen-expand"
                title="全屏缩略图预览"
                onClick={() => setRightMode("grid")}
              >
                <ExpandIcon />
              </button>
            </div>
          </>
        ) : (
          <div className="gen-grid-mode">
            <div className="gen-grid-head">
              <div className="gen-grid-title">
                <span className="gen-grid-count">{images.length} 张图片</span>
                {multiSelect && <span className="gen-grid-selected">{selectedForSubmit.length} 张已选</span>}
              </div>
              <div className="gen-grid-actions">
                <button
                  type="button"
                  className={`gen-multi-toggle${multiSelect ? " active" : ""}`}
                  onClick={() => {
                    setMultiSelect((value) => !value);
                    setSelectedForSubmit([]);
                    setSubmitError("");
                  }}
                >
                  {multiSelect ? "取消多选" : "多选"}
                </button>
                <button
                  type="button"
                  className={`gen-submit-selection${submittingSelection ? " running" : ""}`}
                  disabled={!multiSelect || selectedImagesForSubmit.length === 0 || submittingSelection}
                  onClick={() => void submitSelectedImages()}
                >
                  {submittingSelection ? <span className="button-spinner" /> : null}
                  {submittingSelection ? "提交中" : "提交"}
                </button>
                <button type="button" className="gen-collapse" onClick={() => setRightMode("stage")}>
                  <CollapseIcon />
                  <span>退出</span>
                </button>
              </div>
            </div>
            {submitError && <p className="gen-submit-error">{submitError}</p>}
            <div className="gen-grid">
              {images.map((img, i) => (
                <button
                  key={img.id}
                  type="button"
                  className={`gen-grid-cell${i === selected ? " active" : ""}${selectedForSubmitSet.has(i) ? " selected" : ""}${
                    img.transparent ? " checker" : ""
                  }`}
                  onClick={() => {
                    if (multiSelect) {
                      toggleGridSelection(i);
                      return;
                    }
                    selectFromGrid(i);
                  }}
                  aria-pressed={multiSelect ? selectedForSubmitSet.has(i) : undefined}
                >
                  <img src={img.url} alt="" />
                  <span className="gen-grid-index">{i + 1}</span>
                  {multiSelect && (
                    <span className="gen-grid-check" aria-hidden="true" />
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="gen-field">
      <span className="gen-field-head">
        <span className="gen-field-label">{label}</span>
        {hint && <span className="gen-field-hint">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

function Segmented({
  options,
  value,
  onChange
}: {
  options: Array<{ value: string; label: string; sub?: string }>;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="gen-segmented" role="group">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={value === opt.value ? "active" : ""}
          onClick={() => onChange(opt.value)}
        >
          <span>{opt.label}</span>
          {opt.sub && <em>{opt.sub}</em>}
        </button>
      ))}
    </div>
  );
}

function Stepper({
  value,
  min,
  max,
  onChange
}: {
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="gen-stepper">
      <button type="button" disabled={value <= min} onClick={() => onChange(value - 1)}>
        −
      </button>
      <span>{value}</span>
      <button type="button" disabled={value >= max} onClick={() => onChange(value + 1)}>
        +
      </button>
    </div>
  );
}

function RatioGlyph({ ratio }: { ratio: string }) {
  const { w, h } = ratioDims(ratio);
  if (ratio === "auto") {
    return <span className="gen-ratio-glyph gen-ratio-auto">自</span>;
  }
  return (
    <span className="gen-ratio-glyph">
      <span style={{ width: w, height: h }} />
    </span>
  );
}

function ExpandIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M9 3H3v6M15 3h6v6M9 21H3v-6M15 21h6v-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CollapseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 10h6V4M20 10h-6V4M4 14h6v6M20 14h-6v6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ratioDims(ratio: string, max = 26): { w: number; h: number } {
  if (ratio === "auto") return { w: max, h: max };
  const [a, b] = ratio.split(":").map(Number);
  if (!a || !b) return { w: max, h: max };
  if (a >= b) return { w: max, h: Math.max(8, Math.round((max * b) / a)) };
  return { w: Math.max(8, Math.round((max * a) / b)), h: max };
}

function sizePresetLabel(preset: string): string {
  return preset === "auto" ? "自动" : preset;
}

function optionLabel<T extends string>(options: Array<{ value: T; label: string }>, value: T): string {
  return options.find((option) => option.value === value)?.label || value;
}

function openAiSizeFromPreset(ratio: string, resolution: Resolution): string {
  return OPENAI_SIZE_BY_RATIO[resolution]?.[ratio] || "1024x1024";
}

function generatedBatchTitle(images: GeneratedImage[]): string {
  const prompt = images[0]?.prompt.trim().replace(/\s+/g, " ") || "";
  const prefix = prompt ? `生成图 - ${prompt.slice(0, 24)}` : "生成图";
  return images.length > 1 ? `${prefix} (${images.length} 张)` : prefix;
}

async function appendGeneratedImageToForm(form: FormData, image: GeneratedImage, index: number): Promise<void> {
  const filename = `generated-${String(index + 1).padStart(3, "0")}.${extensionFromGeneratedImage(image)}`;
  try {
    const response = await fetch(image.url);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    const blob = await response.blob();
    if (!blob.type.startsWith("image/")) throw new Error(`not an image: ${blob.type || "unknown"}`);
    form.append("files", new File([blob], filename, { type: blob.type }), filename);
  } catch {
    form.append("generated_image_urls", image.url);
  }
}

function extensionFromGeneratedImage(image: GeneratedImage): string {
  return "png";
}

function imagesFromResponse(
  payload: ImageGenerationResponse,
  request: ImageGenerationRequest,
  resolution: Resolution
): GeneratedImage[] {
  const candidates = imageCandidates(payload);
  return candidates.flatMap((item, index) => {
    const urls = imageUrlsFromCandidate(item, request.output_format);
    if (!urls.length) return [];
    const record = objectRecord(item);
    return urls.map((url, urlIndex) => ({
      id: String(record.id || record.image_id || record.created || `image-${Date.now()}-${index + 1}-${urlIndex + 1}`),
      url,
      size: String(record.size || request.size),
      resolution,
      quality: request.quality as Quality,
      format: request.output_format as OutputFormat,
      transparent: request.background === "transparent",
      prompt: request.prompt
    }));
  });
}

function imageCandidates(payload: unknown): unknown[] {
  const candidates: unknown[] = [];
  collectImageCandidates(payload, candidates, 0);
  return candidates;
}

function collectImageCandidates(value: unknown, candidates: unknown[], depth: number): void {
  if (depth > 8 || value == null) return;
  if (Array.isArray(value)) {
    value.forEach((item) => collectImageCandidates(item, candidates, depth + 1));
    return;
  }
  const record = objectRecord(value);
  if (hasImagePayload(record)) {
    candidates.push(value);
    return;
  }
  for (const key of ["data", "result", "images", "output", "results"]) {
    collectImageCandidates(record[key], candidates, depth + 1);
  }
}

function hasImagePayload(record: Record<string, unknown>): boolean {
  return Boolean(record.url || record.urls || record.b64_json || record.base64 || record.image_base64 || record.image_url || record.output_url || record.uri);
}

function imageUrlsFromCandidate(item: unknown, format: string): string[] {
  if (typeof item === "string") return [item];
  const record = objectRecord(item);
  const direct = record.url || record.image_url || record.output_url || record.uri;
  const directUrls = stringList(direct);
  if (directUrls.length) return directUrls;
  const urls = stringList(record.urls);
  if (urls.length) return urls;
  const b64 = record.b64_json || record.base64 || record.image_base64;
  if (typeof b64 === "string" && b64) {
    const mime = format === "jpeg" ? "image/jpeg" : format === "webp" ? "image/webp" : "image/png";
    const normalized = b64.startsWith("data:") ? b64 : `data:${mime};base64,${b64}`;
    return [normalized];
  }
  return [];
}

function imageGenerationEmptyMessage(payload: ImageGenerationResponse): string {
  const { task, status } = imageGenerationStatusInfo(payload, 0);
  if (task || status) {
    return `图像生成请求还没有返回图片${task ? `（任务：${task}）` : ""}${status ? `，状态：${status}` : ""}。`;
  }
  return "图像生成响应里没有图片 URL 或 base64 内容。";
}

function imageGenerationStatusInfo(value: unknown, depth: number): { task: string; status: string } {
  if (depth > 8 || value == null) return { task: "", status: "" };
  if (Array.isArray(value)) {
    for (const item of value) {
      const info = imageGenerationStatusInfo(item, depth + 1);
      if (info.task || info.status) return info;
    }
    return { task: "", status: "" };
  }
  const record = objectRecord(value);
  const task = record.task_id || record.id || record.request_id;
  const status = record.status || record.state;
  if (task || status) {
    return {
      task: typeof task === "string" ? task : "",
      status: typeof status === "string" ? status : ""
    };
  }
  for (const key of ["data", "result", "images", "output", "results"]) {
    const info = imageGenerationStatusInfo(record[key], depth + 1);
    if (info.task || info.status) return info;
  }
  return { task: "", status: "" };
}

function stringList(value: unknown): string[] {
  if (typeof value === "string" && value) return [value];
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string" && Boolean(item));
  return [];
}

function objectRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? value as Record<string, unknown> : {};
}
