# DrawAI SVG Generation Prompt Draft: Run1 + Free Refine Loop

## English Prompt Draft

```text
IMAGE VECTORIZATION TASK

Goal: convert one bitmap figure into an editable, PPT-stable SVG.

OVERALL DRAWAI PIPELINE

The full DrawAI task is split into three conceptual stages:

1. Asset parsing
   Split the bitmap figure into independent visual assets: text, icons, tables, frames, arrows, chart marks, screenshots, pictures, diagram components, formulas, axes, panels, and other meaningful regions.

2. Asset post-processing
   Refine the pre-parsed assets: adjust bboxes, split/merge elements, add missing elements, and decide the source strategy for each asset: svg_self_draw, crop, or crop_nobg.

3. Image editabilization
   Reconstruct the whole figure as an editable SVG/PPT representation by combining editable SVG primitives/text with allowed raster crop assets.

The current Codex turn executes stage 3 only. Do not redo stage 1 or stage 2. Use their outputs as evidence, especially run0 refined asset analysis and the run0 asset manifest. Your job is to create one complete first-pass SVG, then refine it for up to 3 rounds inside this same Codex turn.

You are inside the run workspace. Read the files yourself. Python only starts this Codex turn and later checks the files you write.

WORKFLOW
1. Run1: create a complete first-pass SVG as semantic_0.svg.
2. Refine loop: run up to 3 rounds. Each round has the same responsibility: inspect the current render, choose the most important fixes, edit the SVG, render, validate, and decide whether to stop.
3. Finalize: write semantic.svg/rendered.png, copy them to the required output paths, and write logs.

INPUT FILES AND HOW TO USE THEM

Primary inputs:
- Original image: {figure_path}
  Use this as the visual truth for layout, color, text placement, arrows, icons, images, tables, axes, and spacing.

- Run0 refined asset analysis: reports/element_analysis_codex/element_analysis.json
  Use this as the main structured plan. It defines refined element boundaries and source labels: svg_self_draw, crop, crop_nobg.

- Run0 asset manifest: svg_to_ppt/assets/asset_manifest.json
  Use this as the authoritative list of local raster image hrefs that may appear in your SVG.

- Native backfill request: {native_backfill_request_path}
  Use this only for listed candidates when the existing manifest does not provide a faithful crop/no-background source. It is a bounded option, not permission to crop arbitrary regions.

- Validator command: {validator_command}
  Run this after every SVG you write.

Auxiliary inputs:
- OCR boxes: ocr/ocr_boxes.json
  Read only when text content, text grouping, or text location needs confirmation.

- Secondary reference image: {reference_image_path}
  Use only as a secondary comparison aid. It must not override the original image.

- SVG template IR: svg/svg_template_ir.json
  Use only as a fallback geometry hint when the original image and run0 analysis leave ambiguity.

- Legacy layout IR: box_ir/box_ir.json
  Use only as a fallback debug hint if a run0 element is missing or unclear. Do not rebuild the task around layout IR boxes.

- Request context: {request_context_path}
  Read only for operational paths or optional response instructions.

SOURCE POLICY

Every visible region should follow the best final source strategy:

- svg_self_draw:
  Use editable SVG primitives/text. This is for text, formulas, arrows, frames, tables, axes, borders, simple charts, simple icons, and simple diagram components.

- crop:
  Use an exact local crop image when the region contains screenshots, photos, dense raster texture, heatmaps, complex small icons, or details that are not worth or not possible to faithfully redraw as SVG.

- crop_nobg:
  Use a no-background crop image when the foreground object is separable and should sit on top of reconstructed editable SVG background.

Use run0 source labels as the default. You may override run0 only when the original image and current render clearly show that another source strategy is more faithful. If you override, record the reason in the iteration log.

Raster image href rules:
- You may insert only hrefs listed in asset_manifest or native_backfill_request.
- Do not invent image paths, external URLs, file:// URLs, absolute paths, or base64 images.
- Do not use raster images to cover text, arrows, panels, tables, formulas, axes, or other structure that should remain editable.

Native backfill rules:
- For each selected native_backfill_request candidate, use at most one output: exact crop or no-background crop.
- Use the candidate's listed href exactly.
- Use crop_nobg only for separable foreground objects on removable plain/light/neutral backgrounds, or when the request/policy indicates transparent_subject.
- Use exact crop for photos, screenshots, dense textures, heatmaps, and background-coupled details.

RUN1 / COMPLETE FIRST PASS

Write semantic_0.svg.

Run1 should produce a complete whole-figure result. It should already look like the target figure at a rough but coherent level. It must not be a placeholder map, skeleton, gray-box map, or list of asset boxes.

Run1 requirements:
- Cover the whole canvas.
- Use SVG/text for svg_self_draw elements.
- Use manifest image hrefs for crop/crop_nobg elements when available.
- Preserve run0 refined bboxes unless visible evidence shows they need adjustment.
- Keep major objects separated and editable where appropriate.
- Avoid overfitting tiny details before the whole figure layout is coherent.

After writing semantic_0.svg:
- Render it to rendered_0.png.
- Validate it to validation_report_0.json.
- Log what was created, which obvious issues remain, and whether any crop/crop_nobg regions still need source decisions.

REFINE LOOP / MAX 3 ROUNDS

At the start of each round:
1. Use the latest SVG as input.
2. Render it.
3. Compare the render against the original image.
4. First inspect the whole figure, then inspect local regions.
5. Decide the highest-impact fixes yourself.

In each round, consider these issue types:
- Whole-figure layout mismatch: canvas scale, panel positions, major blocks, relative spacing, z-order.
- Text mismatch: missing text, wrong content, wrong grouping, wrong size, wrong baseline, wrong color.
- Connector/arrow mismatch: missing arrows, wrong direction, wrong endpoint, wrong arrowhead, wrong layering.
- Shape/table/axis mismatch: wrong borders, grids, ticks, legends, blocks, fills, strokes.
- Asset source mismatch: crop/crop_nobg region redrawn badly, missing image href, wrong crop/no-background choice, image placed at the wrong bbox.
- Editability regression: text/arrow/table/panel became raster when it should be editable.
- PPT stability issue: unsupported SVG feature, unsafe href, invalid image reference, bad structure for SVG-to-PPT conversion.
- Validator issue: parse error, blank render, asset_href_not_in_manifest, blocked feature, viewBox mismatch, or failed report.

You may fix any number of issues in one round. You may make large changes if the current SVG is globally wrong. You may make only small changes if the current SVG is already close.

Allowed refine actions:
- Edit SVG shapes, text, groups, arrow geometry, fills, strokes, transforms, z-order, and object IDs.
- Add or remove SVG elements when the original image supports it.
- Insert allowed manifest/backfill image hrefs for crop/crop_nobg regions.
- Replace an unfaithful SVG approximation with an allowed crop/crop_nobg image.
- Replace a crop with editable SVG only when the region is visually simple and the SVG version is faithful.
- Adjust manifest image placement/size to match run0 bboxes or visible evidence.
- Use OCR to correct text.
- Use Template IR or layout IR only as fallback geometry hints.

Round outputs:
- Round 1 writes semantic_1.svg, rendered_1.png, validation_report_1.json.
- Round 2 writes semantic_2.svg, rendered_2.png, validation_report_2.json.
- Round 3 writes semantic_3.svg, rendered_3.png, validation_report_3.json.

After each round, write to iteration_log.md and iteration_log.jsonl:
- round number
- input SVG
- output SVG/render/report
- issues found
- changes made
- asset source changes, if any
- validation status
- stop or continue decision

STOP CONDITION

Stop before 3 rounds if all of these are true:
- The whole-figure render is perfectly close to the original, or no further improvement is achievable under the current constraints.
- Text, arrows, panels, tables, axes, images, and icons all have correct style, position, and attributes.
- crop/crop_nobg regions use the right allowed image source, or any exception is explicitly logged.
- Editable structures remain editable.
- The latest validator report is status="ok".
- Another round would likely not make the figure better.

Continue to another round if any of these are true:
- The render is not perfectly close to the original and further improvement appears achievable under the current constraints.
- Any text, arrow, panel, table, axis, image, or icon has incorrect style, position, or attributes.
- A visible element is missing, malformed, or visibly misplaced.
- A crop/crop_nobg region uses the wrong source strategy, is redrawn poorly despite an allowed image source, or is placed at the wrong bbox.
- Editable structure has been lost where it should remain editable.
- The SVG uses unsupported features, invalid hrefs, unsafe image references, or a PPT-unstable structure.
- The validator fails.
- Another round is likely to make the figure better.

FINALIZATION

Choose the latest acceptable SVG as the final result.

Required final files:
- Attempt final SVG: semantic.svg
- Attempt final render: rendered.png
- Required final SVG output path: {output_svg_path}
- Required final rendered PNG path: {output_rendered_path}
- Stable Run1 template copy path: {template_svg_path}
- Stable Run1 template rendered copy path: {template_rendered_path}
- Human-readable log: {iteration_log_path}
- Machine-readable JSONL log: {iteration_log_jsonl_path}
- Final validator report: validation_report_final.json

Copy semantic_0.svg/rendered_0.png to the template copy paths. Copy the accepted final SVG/render to the required final output paths.

HARD SVG/PPT CONSTRAINTS

Keep editable:
- text, labels, formulas
- arrows and connectors
- panels, frames, borders
- tables, grids, axes, ticks
- simple diagrams and simple icons

Allowed raster usage:
- only manifest/backfill-listed crop or crop_nobg hrefs
- only for regions that should not be faithfully redrawn as editable SVG

Forbidden SVG features:
- CSS style blocks
- filters
- masks
- clipPath
- foreignObject
- textPath
- pattern fills
- base64 images
- absolute paths
- external URLs
- symbol/use
- browser-only or script-like features

Arrow/PPT rules:
- Thin connectors should use line/polyline/path with marker-end when possible.
- Filled block arrows should be one closed shape when possible.
- Keep arrow shaft and arrowhead together in the same z-order band.
- Do not split a simple arrow into unrelated shapes that may separate during PPT conversion.

FINAL CHECK BEFORE ENDING
- semantic_0.svg exists and has render/validation output.
- 0-3 refine rounds were run. If 0 rounds were run, explain why Run1 already met the stop condition.
- semantic.svg and rendered.png are the accepted final outputs.
- validation_report_final.json is status="ok".
- iteration_log.md and iteration_log.jsonl explain every round and stop/continue decision.
- Final response should be short. The files are the source of truth.

{attempt_feedback_section}
```

## 中文翻译

```text
图像矢量化任务

目标：把一张位图 figure 转成可编辑、PPT 稳定的 SVG。

DrawAI 整体 Pipeline

完整 DrawAI 任务分为三个概念阶段：

1. Assets 解析
   将位图 figure 拆分为独立视觉 assets：文本、图标、表格、框、箭头、图表标记、截图、图片、图示组件、公式、坐标轴、panels 以及其他有意义区域。

2. Assets 后处理
   Refine 预解析 assets：调整 bboxes，拆分/合并元素，补充缺失元素，并为每个 asset 决定来源策略：svg_self_draw、crop 或 crop_nobg。

3. 图像可编辑化
   组合可编辑 SVG primitives/text 和允许的 raster crop assets，把整张图重建成可编辑 SVG/PPT 表示。

当前 Codex turn 只执行第 3 阶段。不要重新做第 1 阶段或第 2 阶段。使用它们的输出作为证据，尤其是 run0 refined asset analysis 和 run0 asset manifest。你的任务是先创建完整第一版 SVG，然后在同一个 Codex turn 内最多 refine 3 轮。

你在 run workspace 里。你需要自己读取文件。Python 只负责启动这个 Codex turn，并在之后检查你写出的文件。

工作流
1. Run1：创建完整第一版 SVG，写成 semantic_0.svg。
2. Refine loop：最多 3 轮。每一轮职责相同：检查当前 render，自己选择最重要的问题，修改 SVG，渲染，验证，并决定是否停止。
3. Finalize：写出 semantic.svg/rendered.png，复制到 required output paths，并写日志。

输入文件及其使用方式

主要输入：
- 原图：{figure_path}
  作为 layout、颜色、文本位置、箭头、图标、图片、表格、坐标轴和间距的视觉真值。

- Run0 refined asset analysis：reports/element_analysis_codex/element_analysis.json
  作为主要结构化计划。它定义 refined element boundaries 和 source labels：svg_self_draw、crop、crop_nobg。

- Run0 asset manifest：svg_to_ppt/assets/asset_manifest.json
  作为 SVG 中允许出现的本地 raster image href 权威列表。

- Native backfill request：{native_backfill_request_path}
  只对列出的 candidates 使用，并且只在现有 manifest 没有提供忠实 crop/no-background source 时使用。它是有边界的选项，不允许任意裁剪区域。

- Validator command：{validator_command}
  每次写出 SVG 后都要运行。

辅助输入：
- OCR boxes：ocr/ocr_boxes.json
  只有文本内容、文本分组或文本位置需要确认时读取。

- 二级参考图：{reference_image_path}
  只作为辅助比较。不能覆盖原图。

- SVG template IR：svg/svg_template_ir.json
  只有当原图和 run0 analysis 留下歧义时，作为 fallback geometry hint。

- Legacy layout IR：box_ir/box_ir.json
  只有当 run0 element 缺失或不清楚时作为 fallback debug hint。不要围绕 layout IR boxes 重建任务。

- Request context：{request_context_path}
  只用于 operational paths 或 optional response instructions。

来源策略

每个可见区域都应该选择最合适的最终来源策略：

- svg_self_draw：
  使用可编辑 SVG primitives/text。适用于文本、公式、箭头、框、表格、坐标轴、边框、简单图表、简单图标和简单图示组件。

- crop：
  当区域包含截图、照片、密集 raster texture、heatmaps、复杂小图标，或者不值得/不可能用 SVG 忠实重画的细节时，使用精确本地裁剪图。

- crop_nobg：
  当前景对象可分离，并且应该放在重建的 editable SVG 背景上时，使用去背景裁剪图。

默认遵循 run0 source labels。只有当原图和当前 render 明确显示另一种来源策略更忠实时，才可以推翻 run0。如果推翻，必须在 iteration log 里记录理由。

Raster image href 规则：
- 只能插入 asset_manifest 或 native_backfill_request 中列出的 href。
- 不要发明 image paths、external URLs、file:// URLs、absolute paths 或 base64 images。
- 不要用 raster images 覆盖本应可编辑的 text、arrows、panels、tables、formulas、axes 或其他结构。

Native backfill 规则：
- 每个被选择的 native_backfill_request candidate，最多使用一个输出：exact crop 或 no-background crop。
- 精确使用 candidate 中列出的 href。
- 只有当前景对象可分离，并且背景是可移除的 plain/light/neutral background，或者 request/policy 指出 transparent_subject 时，才使用 crop_nobg。
- 对照片、截图、密集纹理、heatmaps 和背景耦合细节，使用 exact crop。

Run1 / 完整第一版

写出 semantic_0.svg。

Run1 应该产出整张图的完整结果。它在粗略但连贯的层面上应该已经像目标图。它不能是 placeholder map、skeleton、灰框图或 asset boxes 列表。

Run1 要求：
- 覆盖整个 canvas。
- 对 svg_self_draw elements 使用 SVG/text。
- 对 crop/crop_nobg elements，在可用时使用 manifest image hrefs。
- 除非可见证据显示需要调整，否则保留 run0 refined bboxes。
- 主要对象在合适时保持分离且可编辑。
- 在整图 layout 连贯之前，不要过度拟合微小细节。

写出 semantic_0.svg 之后：
- 渲染为 rendered_0.png。
- 验证为 validation_report_0.json。
- 记录创建了什么、还剩哪些明显问题，以及是否还有 crop/crop_nobg 区域需要来源决策。

Refine loop / 最多 3 轮

每轮开始时：
1. 使用最新 SVG 作为输入。
2. 渲染它。
3. 对照原图比较 render。
4. 先检查整图，再检查局部。
5. 自己决定影响最大的修复。

每轮都考虑这些问题类型：
- 整图 layout mismatch：canvas scale、panel positions、major blocks、relative spacing、z-order。
- 文本 mismatch：缺失文本、内容错误、分组错误、字号错误、baseline 错误、颜色错误。
- 连接线/箭头 mismatch：缺失箭头、方向错误、端点错误、箭头头错误、层级错误。
- shape/table/axis mismatch：边框、网格、ticks、legends、blocks、fills、strokes 错误。
- Asset source mismatch：crop/crop_nobg 区域被错误重画、缺少 image href、crop/no-background 选择错误、图片放在错误 bbox。
- 可编辑性退化：text/arrow/table/panel 在本应可编辑时变成 raster。
- PPT 稳定性问题：不支持的 SVG feature、unsafe href、无效 image reference、对 SVG-to-PPT 不友好的结构。
- Validator 问题：parse error、blank render、asset_href_not_in_manifest、blocked feature、viewBox mismatch 或 failed report。

一轮里可以修任意数量的问题。如果当前 SVG 整体错误，可以大改。如果当前 SVG 已经接近，可以只小修。

允许的 refine 操作：
- 修改 SVG shapes、text、groups、arrow geometry、fills、strokes、transforms、z-order 和 object IDs。
- 当原图支持时，添加或删除 SVG elements。
- 为 crop/crop_nobg regions 插入 allowed manifest/backfill image hrefs。
- 用 allowed crop/crop_nobg image 替换不忠实的 SVG approximation。
- 只有当区域视觉简单且 SVG 版本忠实时，才用 editable SVG 替换 crop。
- 调整 manifest image 的位置/尺寸，使其匹配 run0 bboxes 或可见证据。
- 使用 OCR 修正文本。
- Template IR 或 layout IR 只作为 fallback geometry hints。

每轮输出：
- 第 1 轮写 semantic_1.svg、rendered_1.png、validation_report_1.json。
- 第 2 轮写 semantic_2.svg、rendered_2.png、validation_report_2.json。
- 第 3 轮写 semantic_3.svg、rendered_3.png、validation_report_3.json。

每轮结束后，写入 iteration_log.md 和 iteration_log.jsonl：
- round number
- input SVG
- output SVG/render/report
- issues found
- changes made
- asset source changes，如果有
- validation status
- stop or continue decision

停止条件

如果以下全部满足，就在 3 轮前停止：
- 整图层面 render 已经完美接近原图，或者在现有约束下已经无法获得进一步提升。
- 文本、箭头、panels、tables、axes、images 和 icons 的样式、位置、属性全部正确。
- crop/crop_nobg regions 使用了正确 allowed image source，或明确记录了例外。
- 应可编辑结构仍然保持可编辑。
- 最新 validator report 是 status="ok"。
- 再跑一轮大概率不会让图变得更加好。

如果以下任一成立，就继续下一轮：
- render 还没有完美接近原图，并且在现有约束下看起来仍有进一步提升空间。
- 任意文本、箭头、panel、table、axis、image 或 icon 的样式、位置、属性不正确。
- 可见元素缺失、形状错误或明显错位。
- crop/crop_nobg 区域使用了错误 source strategy，在有 allowed image source 时仍被糟糕地重画，或放在了错误 bbox。
- 应可编辑结构在本应保持可编辑时丢失了可编辑性。
- SVG 使用了不支持 feature、无效 href、不安全 image reference，或对 PPT 不稳定的结构。
- Validator 失败。
- 再跑一轮大概率能让图变得更好。

Finalization

选择最新可接受 SVG 作为最终结果。

Required final files：
- Attempt final SVG：semantic.svg
- Attempt final render：rendered.png
- Required final SVG output path：{output_svg_path}
- Required final rendered PNG path：{output_rendered_path}
- Stable Run1 template copy path：{template_svg_path}
- Stable Run1 template rendered copy path：{template_rendered_path}
- Human-readable log：{iteration_log_path}
- Machine-readable JSONL log：{iteration_log_jsonl_path}
- Final validator report：validation_report_final.json

把 semantic_0.svg/rendered_0.png 复制到 template copy paths。把 accepted final SVG/render 复制到 required final output paths。

硬性 SVG/PPT 约束

保持可编辑：
- text、labels、formulas
- arrows 和 connectors
- panels、frames、borders
- tables、grids、axes、ticks
- simple diagrams 和 simple icons

允许 raster 的情况：
- 只能使用 manifest/backfill 中列出的 crop 或 crop_nobg hrefs
- 只能用于不应该被忠实重画成 editable SVG 的区域

禁止的 SVG features：
- CSS style blocks
- filters
- masks
- clipPath
- foreignObject
- textPath
- pattern fills
- base64 images
- absolute paths
- external URLs
- symbol/use
- browser-only 或 script-like features

Arrow/PPT 规则：
- Thin connectors 尽可能用 line/polyline/path with marker-end。
- Filled block arrows 尽可能用一个 closed shape。
- 让 arrow shaft 和 arrowhead 在同一个 z-order band 中保持一体。
- 不要把简单箭头拆成 PPT 转换后可能分离的无关 shapes。

结束前 final check
- semantic_0.svg 存在，并有 render/validation output。
- refine 轮数为 0-3。如果 0 轮，说明为什么 Run1 已满足停止条件。
- semantic.svg 和 rendered.png 是 accepted final outputs。
- validation_report_final.json 是 status="ok"。
- iteration_log.md 和 iteration_log.jsonl 解释每轮以及 stop/continue decision。
- 最终 response 保持简短。文件才是 source of truth。

{attempt_feedback_section}
```
