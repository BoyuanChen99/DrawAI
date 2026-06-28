from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

RUN0_ELEMENT_REFINE_TASK = """DrawAI asset post-processing and element-plans task.

We are performing an image vectorization task: a bitmap image will eventually be transformed into an editable representation. The whole process has three parts:
- Asset parsing: divide the image into independent assets. Each asset may be text, an icon, table, frame, arrow, and so on.
- Asset post-processing: refine the pre-parsed assets.
- Editable reconstruction: combine assets and finish the final visual result.

Some assets should become editable forms, such as text, frames, arrows, and simple vector graphics. Some assets should instead be cropped from the original image and pasted back into their original positions. The parser/OCR/fusion outputs are evidence, not truth. Execute the second stage, asset post-processing, and produce refined DrawAI element plans that later asset materialization and SVG generation will consume.

Required evidence:
- Original image from the connected input, when available.
- Current DrawAI asset-plan overlay or parser/fusion visualization, when connected.
- Compact candidate table or element candidate JSON.
- Machine-readable request / element candidates / element plans from connected parser or fusion nodes.
- OCR text boxes when visible text content, grouping, or bbox needs confirmation.
- Mask preview sheet and individual mask previews when mask candidates exist.

Task 1: refine the connected candidates into minimum independent assets.
Each output element should be the smallest independent visual part, such as one icon, image, frame, arrow, text line, chart mark, chart block, or diagram component.
- Split a candidate when one box contains multiple independent parts, for example several icons/images inside one block.
- Add a new element when an asset is visible in the original image but not covered by any current candidate.
- Adjust the bbox when the current position is wrong or misses part of a component.
- Remove or merge a candidate only when it is clearly duplicate, noise, or wholly represented by another retained element.
- Preserve traceability. For unchanged or adjusted elements, keep source_candidate_ids pointing to the original candidate ID. For split elements, use stable IDs like B012_S01 with source_candidate_ids ["B012"]. For newly added elements, use stable IDs like N001 with source_candidate_ids [].
- Bboxes must be visual extents in image pixels. For straight lines or dividers, give at least 1 pixel of thickness so width and height are positive.
- Pay close attention to coordinate accuracy and whether each bbox tightly contains the corresponding asset.
- For geometry_kind="mask", use mask_preview PNGs and the mask preview sheet as visual evidence. Do not adjust or resize the mask region; preserve its bbox/geometry when keeping it. Remove or merge a mask candidate only when it is clearly duplicate or noise. Do not read or rely on raw mask files.

Task 2: repeat a bounded visualization/refinement loop until the asset parsing quality is good enough, all elements are reasonable assets, and bbox coordinates are accurate. Run at most 3 iterations.
1. Write the current element-plans JSON for the iteration to reports/element_plans_codex/refine_iteration_<N>.json, where <N> starts at 1.
2. Run assets_visualization.py with the original image and that iteration JSON, using color-mode action and label-mode id_type.
3. Inspect reports/element_plans_codex/assets_visualization_iteration_<N>.png.
4. Correct Task 1 results from the visualization. You may add assets, remove assets, split assets, merge accidental duplicates, and adjust bbox coordinates. One iteration may change any number of assets.
5. Repeat until the assets are correct or 3 iterations have completed.
6. Save the final refined element-plans JSON to the declared output path, normally output/elements.json.

Task 3: classify every final retained output element into exactly one processing intent.
- svg_self_draw: use editable SVG primitives/text/paths directly. Use this for text, arrows, boxes, lines, charts, simple geometric diagrams, and visually simple icons that can be faithfully redrawn.
- crop: use a precise source-image crop with local background preserved. Use this for screenshots, photographs, dense texture, heatmaps, complex small raster icons, or visual details whose background is coupled with the object.
- crop_nobg: use a precise crop after background removal/transparent subject extraction. Use this when the foreground object is separable and should sit over reconstructed SVG background.

Important classification and coverage rules:
- Treat SAM/OCR/current asset plan as evidence, not truth. You may disagree with current_pipeline_method if the image supports it.
- Output only retained final element plans. Do not output removal_records, strategy_summary, refinement_summary, categories, notes, or old element_analysis fields.
- Do not skip real visual assets. Every retained or merged original candidate should appear in source_candidate_ids on at least one output element. Clearly duplicate/noise candidates may be omitted.
- The element_type field must be a concrete DrawAI element type: text, icon, picture, table, chart, diagram, arrow, frame, grid, symbol, content_box, or unknown. For newly added elements, do not use a meta type such as added_asset.
- New IDs are allowed only for split or added refined elements. Keep IDs short and stable.
- If uncertain, choose the most faithful final-source strategy and mark confidence as low or medium.
- After the visualization loop, complete classification in one pass. Write the final JSON file first. Keep change_reason concise.

The final JSON must use format drawai.element_plans.v1 and contain:
- top-level schema="drawai.element_plans.v1"
- elements: array of retained element plans only

Each element plan must contain:
- schema="drawai.element_plan.v1"
- element_id: stable short ID
- source_candidate_ids: list of source candidate IDs; [] only for newly added visual assets
- element_type: text|icon|picture|table|chart|diagram|arrow|frame|grid|symbol|content_box|unknown
- bbox: [x, y, width, height] in image pixels, with positive width and height
- geometry: object; for ordinary boxes use {"kind":"bbox","bbox":[x,y,width,height],"coordinate_system":"figure_image_pixels"}
- z_order: integer, lower values behind higher values
- confidence: low|medium|high
- processing_intent: {"object_type": element_type or a more specific object name, "processing_type": svg_self_draw|crop|crop_nobg, "parameters": {}}
- review_status: agent_refined
- created_by_stage: refine_elements
- change_reason: concise explanation of keep/split/merge/add/bbox/source decision

The declared output JSON file is the source of truth."""

RUN0_ELEMENT_REFINE_CONSTRAINTS = (
    "Use only the connected input files listed in this prompt and explicitly declared built-in script files.",
    "Do not render final SVG/PPT and do not modify repository code. This node only refines/classifies assets.",
    "Do not use MCP tools, apps, web search, memories, skills, hooks, or multi-agent delegation.",
    "Do not print full request JSON to the terminal or logs; start from compact candidate tables and read exact details only when needed.",
    "Output only drawai.element_plans.v1 JSON; do not output codex element analysis, summaries, notes, or removal records.",
    "Write the declared output files exactly, in UTF-8 JSON or markdown according to the output declaration.",
)


@dataclass(frozen=True)
class PageSpecProcessingOperation:
    processing_type: str
    meaning: str
    choose_when: str
    avoid_when: str


PAGE_SPEC_PROCESSING_OPERATIONS = {
    "no_process": PageSpecProcessingOperation(
        processing_type="no_process",
        meaning=(
            "Do not materialize this element in the processing stage. Keep it as PageSpec structure for "
            "downstream SVG Compose to draw from its text, style, geometry, coordinates, and semantics."
        ),
        choose_when=(
            "Choose for text, lines, arrows, shapes, tables, ordinary chart structure, simple vector icons, "
            "background panels, diagrams that should remain structural, and any element that does not need "
            "an independent processed asset."
        ),
        avoid_when=(
            "Do not choose for photos, screenshots, textures, complex raster regions, foreground objects that "
            "need background removal, tiny raster thumbnails, conceptual illustration icons, future-state preview "
            "images, low-quality semantic thumbnails, or elements that require a dedicated processor before SVG Compose."
        ),
    ),
    "crop": PageSpecProcessingOperation(
        processing_type="crop",
        meaning=(
            "Crop the element region from the original image and preserve source pixels, local background, "
            "and raster detail as an independent asset."
        ),
        choose_when=(
            "Choose for photos, screenshots, heatmaps, complex textures, dense raster tiles, small complex "
            "raster icons that must preserve exact source pixels, and regions whose subject is visually coupled "
            "to its local background. Use crop for low-resolution thumbnails only when exact source-pixel "
            "preservation is visibly more important than cleanup or regeneration."
        ),
        avoid_when=(
            "Do not choose for editable text, lines, arrows, simple shapes, ordinary table structure, "
            "transparent foreground objects, elements that SVG Compose can draw directly, or low-resolution "
            "conceptual icons/thumbnails that should be cleaned by image_edit or regenerated by image_generate. "
            "Do not default source-grounded conceptual preview thumbnails to crop when image_edit or "
            "image_generate is enabled and a cleaner asset would preserve the intended visual role better."
        ),
    ),
    "crop_nobg": PageSpecProcessingOperation(
        processing_type="crop_nobg",
        meaning=(
            "Crop the element region and remove its background, producing a transparent foreground asset."
        ),
        choose_when=(
            "Choose for logos, products, people, standalone objects, foreground illustrations, transparent "
            "icons, and visually separable subjects with clear boundaries."
        ),
        avoid_when=(
            "Do not choose for screenshots, heatmaps, textures, software UI, photos whose background must "
            "remain attached, editable structures, or objects whose boundary is too ambiguous for background removal."
        ),
    ),
    "chart_rebuild_reserved": PageSpecProcessingOperation(
        processing_type="chart_rebuild_reserved",
        meaning=(
            "Reserve the element as a future structured chart-rebuild target. It does not produce an asset in "
            "the current processing stage."
        ),
        choose_when="Choose only for chart elements that clearly need future structured chart reconstruction.",
        avoid_when=(
            "Do not choose for non-chart elements, ordinary chart structures that SVG Compose can draw, or "
            "chart screenshots that should be preserved with a crop."
        ),
    ),
    "svg_self_draw": PageSpecProcessingOperation(
        processing_type="svg_self_draw",
        meaning=(
            "Use an SVG processor to generate an independent SVG asset for this element during the processing stage."
        ),
        choose_when=(
            "Choose for complex vector elements that must be generated as standalone SVG assets before final composition."
        ),
        avoid_when=(
            "Do not choose for ordinary text, lines, shapes, tables, or elements that can be drawn by downstream "
            "SVG Compose without an independent asset."
        ),
    ),
    "image_generate": PageSpecProcessingOperation(
        processing_type="image_generate",
        meaning=(
            "Generate a new raster image asset from the element's semantic role, nearby labels, "
            "page context, and target box size. The result will be scaled back into the original PageSpec box."
        ),
        choose_when=(
            "Choose for image-like conceptual graphics, illustrative icons, predicted/future representation "
            "thumbnails, missing or low-quality visual assets, and regions where copying source pixels would "
            "preserve noise rather than a clean representation. Prefer image_generate when the source crop is "
            "missing, too tiny, too noisy, or semantically clear enough to synthesize from labels and surrounding "
            "context. Keep the classifier selective: not every image-like element should be generated if crop, "
            "crop_nobg, image_edit, or no_process is the more faithful operation."
        ),
        avoid_when=(
            "Do not choose for editable text, lines, simple shapes, tables, charts, source pixels that are already "
            "acceptable as crops and must remain pixel-identical, or foreground objects that only need background removal."
        ),
    ),
    "image_edit": PageSpecProcessingOperation(
        processing_type="image_edit",
        meaning=(
            "Crop the source element and edit it into a cleaner raster asset while preserving its original composition, "
            "visual role, colors, aspect, and placement constraints."
        ),
        choose_when=(
            "Choose when the source crop already contains the target object but needs cleanup, redraw, deblurring, "
            "background adjustment, style harmonization, higher-quality reconstruction, or readable preservation "
            "of a tiny conceptual icon. Prefer image_edit over crop for source-grounded thumbnails, previews, "
            "and illustrative icons when the crop is visibly low-resolution but the original composition should "
            "stay recognizable. Keep the classifier selective: use crop/crop_nobg/no_process when source-pixel "
            "preservation, transparent extraction, or structural reconstruction is more faithful."
        ),
        avoid_when=(
            "Do not choose for elements that should remain structural, direct crops that are already good enough "
            "and must remain pixel-identical, fully missing assets better suited to image_generate, or standalone "
            "foreground objects where crop_nobg is sufficient."
        ),
    ),
}

DEFAULT_PAGE_SPEC_REFINE_PROCESSING_TYPES = (
    "no_process",
    "crop",
    "crop_nobg",
    "image_edit",
)


def normalize_page_spec_processing_types(
    processing_types: Sequence[str] | None = None,
    operation_catalog: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    raw_types = (
        DEFAULT_PAGE_SPEC_REFINE_PROCESSING_TYPES
        if processing_types is None
        else processing_types
    )
    if isinstance(raw_types, str):
        raise ValueError("PageSpec processing types must be an array of strings")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, raw_type in enumerate(raw_types):
        if not isinstance(raw_type, str):
            raise ValueError(f"page_spec_processing_types[{index}] must be a string")
        processing_type = raw_type.strip()
        if not processing_type:
            continue
        if processing_type not in PAGE_SPEC_PROCESSING_OPERATIONS and (
            operation_catalog is None or processing_type not in operation_catalog
        ):
            raise ValueError(f"unsupported PageSpec processing type: {processing_type}")
        if processing_type in seen:
            continue
        normalized.append(processing_type)
        seen.add(processing_type)
    if not normalized:
        raise ValueError("at least one PageSpec processing type must be enabled")
    return tuple(normalized)


def render_page_spec_processing_operations(
    processing_types: Sequence[str] | None = None,
    operation_catalog: Mapping[str, Any] | None = None,
) -> str:
    sections: list[str] = ["## Available Processing Operations"]
    for processing_type in normalize_page_spec_processing_types(
        processing_types,
        operation_catalog=operation_catalog,
    ):
        operation = _page_spec_processing_operation(processing_type, operation_catalog)
        sections.append(
            "\n".join(
                (
                    f"### {operation.processing_type}",
                    "",
                    f"Meaning: {operation.meaning}",
                    "",
                    f"Choose when: {operation.choose_when}",
                    "",
                    f"Do not choose when: {operation.avoid_when}",
                )
            )
        )
    return "\n\n".join(sections)


def _page_spec_processing_operation(
    processing_type: str,
    operation_catalog: Mapping[str, Any] | None,
) -> PageSpecProcessingOperation:
    if operation_catalog is not None and processing_type in operation_catalog:
        raw = operation_catalog[processing_type]
        if isinstance(raw, PageSpecProcessingOperation):
            return raw
        if not isinstance(raw, Mapping):
            raise ValueError(f"page_spec_processing_operations.{processing_type} must be an object")
        return PageSpecProcessingOperation(
            processing_type=processing_type,
            meaning=_operation_text(raw, "meaning", processing_type),
            choose_when=_operation_text(raw, "choose_when", processing_type),
            avoid_when=_operation_text(raw, "avoid_when", processing_type),
        )
    if processing_type not in PAGE_SPEC_PROCESSING_OPERATIONS:
        raise ValueError(f"unsupported PageSpec processing type: {processing_type}")
    return PAGE_SPEC_PROCESSING_OPERATIONS[processing_type]


def _operation_text(raw: Mapping[str, Any], field_name: str, processing_type: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"page_spec_processing_operations.{processing_type}.{field_name} must be a non-empty string")
    return value.strip()


PAGE_SPEC_REFINE_TASK_PREFIX = """DrawAI PageSpec refinement task.

You are operating on one page. The connected PageSpec is the only structured page model for this node. The refined PageSpec elements array is the handoff to every downstream node.

DrawAI's overall task is to vectorize an input image. This node is in the visual element parsing and correction stage. Your job is to refine the previous PageSpec result against the original page image.

Goal: read the original page image and the connected drawai.page_spec.v1 file, then write the refined drawai.page_spec.v1 file to the declared output path. The refinement must correct all page elements: add missing elements, delete redundant elements, split or merge elements, adjust kind, role, coordinates, z-order, text, style, and processing operation.

Required operations:
- Treat the original image as visual truth and the connected PageSpec as evidence.
- Do not inspect DrawAI repository source code, import internal DrawAI modules, or call internal Python APIs to learn schema behavior. Use the declared DrawAI CLI tools, especially `format describe` and `format validate`, for format contracts and validation.
- Keep the PageSpec top-level model page-level only: schema, page_id, source, canvas, background, elements, and metadata.
- Check for redundant and missing elements. Add elements that are visible in the page but missing from the input PageSpec. Remove elements that are duplicate, noise, false positives, or fully represented by another retained element.
- Deletions must be actual deletions from elements. Do not keep deleted elements with a removed flag.
- Check for elements that should be split or merged. Split an element when one box contains multiple independent visual parts that should not share one processing operation. Keep the original id for one dominant split child when appropriate, and create new ids for split-out parts.
- Merge elements when multiple boxes describe the same visual object. Keep the clearest existing id, delete redundant boxes, and adjust the kept element's type, bbox, and processing operation.
- Do not merge elements that require different processing operations. If one element contains parts that require different operations, split it.
- For every retained or new element, set build.processing_type. Use only the processing operations provided in this task prompt. Do not invent or use unavailable operations.
- If an element does not need an independent processed asset, use the processing operation that means no processing/materialization.
- Preserve useful source_refs from upstream PageSpec evidence. For adjusted/new/split/merged elements, add element metadata.refine_action with one of adjusted, added, split_child, or merged_result; add metadata.refine_reason as a short reason; and add metadata.refine_source_ids when the element came from previous element ids.
- Preserve stable ids. Keep the original id for retained or adjusted elements. Do not globally renumber. For added visual elements, continue the existing id style with the next unused E### when possible. For splits, keep the source id on the dominant child if it still represents that child, and create new ids only for the additional children. For merges, keep the clearest existing source id.
- Record a compact top-level metadata.refine_changes object with this shape:
  {"adjusted":[{"id":"E001","fields":["box_px"],"reason":"..."}],"added":[{"id":"E200","reason":"..."}],"split":[{"source_id":"E010","new_ids":["E010","E201"],"reason":"..."}],"merged":[{"source_ids":["E011","E012"],"kept_id":"E011","reason":"..."}],"deleted":[{"id":"E013","reason":"..."}]}
  Use empty arrays when a category has no changes. This is an audit trail only; the refined elements array is the source of truth.

Element field guide:
- id: stable unique element id.
- kind: one of text, shape, image, diagram, connector, table, chart, formula, or unknown.
- role: a more specific semantic role such as title, body_text, logo, photo, icon, axis, legend, diagram, or background_panel.
- box_px: [x, y, width, height] in source image pixels. Width and height must be positive.
- points_px: key points for lines, arrows, or connectors when useful.
- polygon_px: polygon points for non-rectangular regions when useful.
- z_index: visual layer; larger values appear above smaller values.
- text: visible text for text elements only.
- geometry: more precise geometry such as bbox, mask, polygon, or connector endpoints.
- style: visual style such as color, font, size, stroke, fill, opacity, and alignment when known.
- measurement: OCR confidence, text measurement, size estimates, and compact visual evidence.
- source_refs: upstream evidence references. Preserve useful references.
- build.mode: construction mode, such as editable_text, vector, asset_ref, or structured.
- build.processing_type: processing operation. It must be one of the available operations in this prompt.
- build.asset_id: required when the selected processing operation produces an independent asset.
- materialization: generated by a later processing node. Do not write or fake it in this refine node.
- metadata: compact refinement audit fields such as refine_action, refine_reason, and refine_source_ids.

Field updates:
- When adjusting an element, update only fields supported by visual evidence: box_px, geometry, points_px, polygon_px, kind, role, text, z_index, build.mode, build.processing_type, build.asset_id, style, measurement, source_refs, and metadata.
- When adding an element, include id, kind, role, box_px, z_index, source_refs, build.mode, build.processing_type, metadata.refine_action="added", and metadata.refine_reason. Include text for text elements. Include build.asset_id when the operation produces an independent asset.
- When deleting an element, remove it from elements and record the deletion in metadata.refine_changes.deleted.
- When splitting an element, every split child must have its own box_px, kind, role, and build.processing_type. Each split child should preserve source_refs to the source element or source evidence.
- When merging elements, keep one stable id, expand box_px to cover the complete object, merge source_refs without duplicates, delete the redundant elements, and record metadata.refine_action="merged_result".

JSON examples:

Adjusted element:
```json
{
  "id": "E001",
  "kind": "image",
  "role": "logo",
  "box_px": [120, 40, 88, 32],
  "z_index": 20,
  "source_refs": [{"kind": "page_spec_element", "id": "E001"}],
  "build": {"mode": "asset_ref", "processing_type": "crop_nobg", "asset_id": "A001"},
  "metadata": {
    "refine_action": "adjusted",
    "refine_reason": "original bbox missed the right edge of the logo",
    "refine_source_ids": ["E001"]
  }
}
```

Added text element:
```json
{
  "id": "E203",
  "kind": "text",
  "role": "axis_label",
  "box_px": [88, 512, 140, 24],
  "z_index": 15,
  "text": "Accuracy",
  "source_refs": [],
  "build": {"mode": "editable_text", "processing_type": "no_process"},
  "measurement": {"text": "Accuracy", "confidence": "medium"},
  "metadata": {
    "refine_action": "added",
    "refine_reason": "visible axis label was missing from the input PageSpec"
  }
}
```

Top-level audit shape:
```json
{
  "metadata": {
    "refine_changes": {
      "adjusted": [{"id": "E001", "fields": ["box_px", "build.processing_type"], "reason": "..."}],
      "added": [{"id": "E203", "reason": "..."}],
      "split": [{"source_id": "E010", "new_ids": ["E010", "E201"], "reason": "..."}],
      "merged": [{"source_ids": ["E011", "E012"], "kept_id": "E011", "reason": "..."}],
      "deleted": [{"id": "E013", "reason": "..."}]
    }
  }
}
```

"""

PAGE_SPEC_REFINE_TASK_SUFFIX = """Output requirements:

- Write exactly one JSON object with schema drawai.page_spec.v1.
- The output PageSpec must validate under drawai.page_spec.v1.
- Before finishing, run the DrawAI format tool against the declared output path: format validate --format-id drawai.page_spec.v1 --path <declared PageSpec output path>. Finish only after validation reports ok.
- Do not write a sidecar planning or analysis file for this node. Put the final decisions directly in PageSpec elements and metadata.
- Do not embed any other full schema, upstream payload, or compatibility artifact inside metadata; metadata should stay compact and audit-oriented."""


def render_page_spec_refine_task(
    processing_types: Sequence[str] | None = None,
    operation_catalog: Mapping[str, Any] | None = None,
) -> str:
    processing_operations = render_page_spec_processing_operations(
        processing_types,
        operation_catalog=operation_catalog,
    )
    return "\n\n".join(
        (
            PAGE_SPEC_REFINE_TASK_PREFIX.strip(),
            processing_operations,
            PAGE_SPEC_REFINE_TASK_SUFFIX.strip(),
        )
    )


PAGE_SPEC_REFINE_TASK = render_page_spec_refine_task()

PAGE_SPEC_REFINE_TASK_PREFIX_ZH = """DrawAI PageSpec 精修任务。

你正在处理单页图像。连接进来的 PageSpec 是此节点唯一的结构化页面模型。精修后的 PageSpec elements 数组会交给所有下游节点使用。

DrawAI 的整体任务是把输入图像向量化。本节点处于视觉元素解析和校正阶段。你的工作是对照原始页面图像，精修上游 PageSpec 结果。

目标：读取原始页面图像和连接进来的 drawai.page_spec.v1 文件，然后把精修后的 drawai.page_spec.v1 文件写到声明的输出路径。精修必须校正所有页面元素：补充缺失元素、删除冗余元素、拆分或合并元素、调整 kind、role、坐标、z-order、文本、样式和 processing operation。

必须执行的操作：
- 把原始图像当成视觉真值，把连接进来的 PageSpec 当成证据。
- 不要检查 DrawAI 仓库源码、不要导入内部 DrawAI 模块、不要调用内部 Python API 来学习 schema 行为。使用声明的 DrawAI CLI 工具，尤其是 `format describe` 和 `format validate`，来获取格式契约和做校验。
- PageSpec 顶层模型只保留页面级字段：schema、page_id、source、canvas、background、elements 和 metadata。
- 检查冗余和缺失元素。对页面中可见但输入 PageSpec 缺失的元素要新增；对重复、噪声、误检或已经被另一个保留元素完整表示的元素要删除。
- 删除必须是真正从 elements 中删除。不要保留带 removed 标记的 deleted element。
- 检查是否有需要拆分或合并的元素。当一个 box 内包含多个独立视觉部分，且它们不应共享同一个 processing operation 时，要拆分该元素。合适时保留原 id 给主导 split child，并给拆出的其他部分创建新 id。
- 当多个 box 描述同一个视觉对象时要合并。保留最清晰的现有 id，删除冗余 box，并调整保留元素的类型、bbox 和 processing operation。
- 不要合并需要不同 processing operation 的元素。如果一个元素包含需要不同 operation 的部分，应拆分它。
- 对每个保留或新增元素，都设置 build.processing_type。只能使用本 task prompt 中提供的 processing operations。不要发明或使用不可用的 operation。
- 如果某个元素不需要独立处理资产，就使用表示不处理/不 materialize 的 processing operation。
- 保留来自上游 PageSpec 证据中有用的 source_refs。对 adjusted/new/split/merged 元素，在 element metadata 中加入 metadata.refine_action，取值为 adjusted、added、split_child 或 merged_result；加入简短的 metadata.refine_reason；当元素来自之前的 element id 时加入 metadata.refine_source_ids。
- 保持 id 稳定。保留或调整元素时保留原 id。不要全局重编号。对新增视觉元素，尽量沿用现有 id 风格并使用下一个未使用的 E###。拆分时，如果 source id 仍代表主导 child，就保留给它；只给额外 child 创建新 id。合并时保留最清晰的 source id。
- 在顶层 metadata.refine_changes 中记录紧凑变更，形状如下：
  {"adjusted":[{"id":"E001","fields":["box_px"],"reason":"..."}],"added":[{"id":"E200","reason":"..."}],"split":[{"source_id":"E010","new_ids":["E010","E201"],"reason":"..."}],"merged":[{"source_ids":["E011","E012"],"kept_id":"E011","reason":"..."}],"deleted":[{"id":"E013","reason":"..."}]}
  某类没有变更时使用空数组。这只是审计日志；精修后的 elements 数组才是事实来源。

元素字段指南：
- id：稳定且唯一的元素 id。
- kind：text、shape、image、diagram、connector、table、chart、formula 或 unknown 之一。
- role：更具体的语义角色，例如 title、body_text、logo、photo、icon、axis、legend、diagram 或 background_panel。
- box_px：源图像像素坐标中的 [x, y, width, height]。宽高必须为正。
- points_px：对线、箭头或 connector 有帮助时记录关键点。
- polygon_px：对非矩形区域有帮助时记录 polygon points。
- z_index：视觉层级；数值越大越靠上。
- text：仅 text 元素使用的可见文本。
- geometry：更精确的几何，例如 bbox、mask、polygon 或 connector endpoints。
- style：视觉样式，例如 color、font、size、stroke、fill、opacity 和 alignment。
- measurement：OCR confidence、文本测量、尺寸估计和紧凑视觉证据。
- source_refs：上游证据引用。保留有用引用。
- build.mode：构造模式，例如 editable_text、vector、asset_ref 或 structured。
- build.processing_type：processing operation。必须是本 prompt 中可用的 operation 之一。
- build.asset_id：当选择的 processing operation 会产生独立 asset 时必填。
- materialization：由后续 processing node 生成。不要在 refine 节点中写入或伪造。
- metadata：紧凑的 refinement 审计字段，例如 refine_action、refine_reason 和 refine_source_ids。

字段更新：
- 调整元素时，只更新视觉证据支持的字段：box_px、geometry、points_px、polygon_px、kind、role、text、z_index、build.mode、build.processing_type、build.asset_id、style、measurement、source_refs 和 metadata。
- 新增元素时，包含 id、kind、role、box_px、z_index、source_refs、build.mode、build.processing_type、metadata.refine_action="added" 和 metadata.refine_reason。text 元素要包含 text。当 operation 会产生独立 asset 时包含 build.asset_id。
- 删除元素时，从 elements 中移除它，并在 metadata.refine_changes.deleted 中记录删除。
- 拆分元素时，每个 split child 都必须有自己的 box_px、kind、role 和 build.processing_type。每个 split child 应保留指向 source element 或 source evidence 的 source_refs。
- 合并元素时，保留一个稳定 id，扩展 box_px 覆盖完整对象，去重合并 source_refs，删除冗余元素，并记录 metadata.refine_action="merged_result"。

JSON 示例：

Adjusted element:
```json
{
  "id": "E001",
  "kind": "image",
  "role": "logo",
  "box_px": [120, 40, 88, 32],
  "z_index": 20,
  "source_refs": [{"kind": "page_spec_element", "id": "E001"}],
  "build": {"mode": "asset_ref", "processing_type": "crop_nobg", "asset_id": "A001"},
  "metadata": {
    "refine_action": "adjusted",
    "refine_reason": "original bbox missed the right edge of the logo",
    "refine_source_ids": ["E001"]
  }
}
```

Added text element:
```json
{
  "id": "E203",
  "kind": "text",
  "role": "axis_label",
  "box_px": [88, 512, 140, 24],
  "z_index": 15,
  "text": "Accuracy",
  "source_refs": [],
  "build": {"mode": "editable_text", "processing_type": "no_process"},
  "measurement": {"text": "Accuracy", "confidence": "medium"},
  "metadata": {
    "refine_action": "added",
    "refine_reason": "visible axis label was missing from the input PageSpec"
  }
}
```

Top-level audit shape:
```json
{
  "metadata": {
    "refine_changes": {
      "adjusted": [{"id": "E001", "fields": ["box_px", "build.processing_type"], "reason": "..."}],
      "added": [{"id": "E203", "reason": "..."}],
      "split": [{"source_id": "E010", "new_ids": ["E010", "E201"], "reason": "..."}],
      "merged": [{"source_ids": ["E011", "E012"], "kept_id": "E011", "reason": "..."}],
      "deleted": [{"id": "E013", "reason": "..."}]
    }
  }
}
```

"""

PAGE_SPEC_REFINE_TASK_SUFFIX_ZH = """输出要求：

- 只写一个 schema 为 drawai.page_spec.v1 的 JSON object。
- 输出 PageSpec 必须通过 drawai.page_spec.v1 校验。
- 结束前，对声明的输出路径运行 DrawAI format 工具：format validate --format-id drawai.page_spec.v1 --path <declared PageSpec output path>。只有 validation reports ok 后才能结束。
- 不要为此节点写 sidecar planning 或 analysis 文件。把最终决策直接写进 PageSpec elements 和 metadata。
- 不要在 metadata 中嵌入其他完整 schema、上游 payload 或兼容性 artifact；metadata 应保持紧凑并只用于审计。"""


def render_page_spec_refine_task_zh(
    processing_types: Sequence[str] | None = None,
    operation_catalog: Mapping[str, Any] | None = None,
) -> str:
    processing_operations = render_page_spec_processing_operations(
        processing_types,
        operation_catalog=operation_catalog,
    )
    return "\n\n".join(
        (
            PAGE_SPEC_REFINE_TASK_PREFIX_ZH.strip(),
            processing_operations,
            PAGE_SPEC_REFINE_TASK_SUFFIX_ZH.strip(),
        )
    )


PAGE_SPEC_REFINE_TASK_ZH = render_page_spec_refine_task_zh()

PAGE_SPEC_REFINE_CONSTRAINTS = (
    "Use only connected input files listed in this prompt and explicitly declared built-in script files.",
    "Do not inspect repository source code, import internal DrawAI modules, or call internal DrawAI APIs; use declared DrawAI CLI tools for schema/tool contracts.",
    "Do not render final SVG/PPT. This node only refines one PageSpec page.",
    "Do not use MCP tools, apps, web search, memories, skills, hooks, or multi-agent delegation.",
    "Deleted elements must be absent from the output elements array; record deletion only in metadata.refine_changes.",
    "Write the declared PageSpec output exactly as UTF-8 JSON.",
)

SVG_GENERATION_TASK = """IMAGE VECTORIZATION TASK
Goal: convert one bitmap figure into an editable, PPT-stable SVG.

OVERALL DRAWAI PIPELINE
The full DrawAI task is split into three conceptual stages:
1. Asset parsing: SAM/OCR produce PageSpec element evidence for one page.
2. PageSpec refinement and asset preparation: refine the PageSpec elements, adjust bboxes, split/merge elements, add missing elements, decide build.processing_type for each element, and materialize crop/crop_nobg outputs into element.materialization inside the PageSpec bundle.
3. Image editabilization: reconstruct the whole figure as an editable SVG/PPT representation by combining editable SVG primitives/text with allowed raster crop assets.

The current Agent node executes stage 3 only. Do not redo parsing, refinement, or asset preparation. Use the connected original image as visual truth. If the connected input list includes no PageSpec, treat this as the direct-image path from the start. When a materialized PageSpec input is connected, use it as the structured plan and use only its element.materialization outputs as raster asset sources. Your job is to create one complete first-pass SVG, run validation, make the bounded refinement rounds described below, and always finish with the declared final SVG and logs before the agent timeout.

EXECUTION MODEL
- The DrawAI runner prepares the node work directory and connected input files. You must read those files yourself.
- You may use ordinary shell utilities or short local scripts to inspect connected files and write node-local outputs. For DrawAI-specific behavior, do not inspect repository source code, import internal DrawAI modules, or call internal Python APIs; use only the declared DrawAI CLI tools and their `help` / `format describe` contracts.
- The declared SVG output is the semantic output consumed by downstream nodes. This task also intentionally writes auxiliary SVG/render/report/log files inside the same node output directory; those auxiliary files are allowed task artifacts, not additional downstream outputs.
- You must create intermediate SVGs, inspect them, revise them, and finish with the declared final SVG and logs. In PageSpec-connected runs, also create the requested renders/reports with svg-validate.
- Run1 and every refine round may use allowed local raster image hrefs produced from PageSpec element.materialization when the element source is crop or crop_nobg.
- If this node is used in an image-only DAG with no PageSpec input, reconstruct directly from the image, use editable SVG for all structure, do not call page-spec-assets, and validate the final SVG with the format tool instead of PageSpec-backed svg-validate.
- Finalization has higher priority than another refinement round. If the latest SVG validates and is broadly faithful, finalize it immediately.

AVAILABLE FILES AND READING LOGIC
Primary files for this stage:
- Original/current reference image. Use it as the visual truth for layout, color, text placement, arrows, icons, images, tables, axes, and spacing.
- Materialized PageSpec JSON, when connected. Use it as the main structured plan: element ids, kind, role, bbox, z_index, text, style, measurement, grouping, build.processing_type, and materialization outputs.
- PageSpec materialized assets, when connected. Use the declared DrawAI page-spec-assets tool to compute allowed local raster hrefs from the materialized PageSpec for crop/crop_nobg elements.
- SVG validation. In PageSpec-connected runs, use the declared DrawAI svg-validate tool for each SVG/render/report pair. In image-only runs, use format validate for the final SVG and record the validation command in iteration_log.md.

Reading sequence:
1. Start from the original image and the connected materialized PageSpec when present. These sources define what the stage is trying to reproduce.
2. When a PageSpec input is connected, before inserting any raster image href, compute it with the page-spec-assets tool from the connected PageSpec. Use --svg-dir svg so hrefs resolve after the final SVG is mirrored to svg/semantic.svg for preview and PPT export. In image-only runs, skip this step entirely.
3. Do not look for unconnected OCR, template, layout, request, or parser files. OCR/SAM evidence has already been fused into PageSpec when PageSpec is connected.
4. Keep request JSON compact in reasoning. Do not print full JSON files to terminal or logs.

PATH MODEL
- The Agent process cwd is the workflow run root.
- The declared output path shown below is the node-local final SVG, for example nodes/svg_compose/runs/001/output/semantic.svg.
- For PageSpec-connected runs, write every auxiliary file next to that declared output in the same node output directory: semantic_0.svg, rendered_0.png, validation_report_0.json, semantic_1.svg, rendered_1.png, validation_report_1.json, optional semantic_2.svg, optional rendered_2.png, optional validation_report_2.json, rendered.png, validation_report_final.json, iteration_log.md, and iteration_log.jsonl.
- For image-only runs, write semantic_0.svg, semantic_1.svg when a refinement round is used, optional semantic_2.svg only when validation failed, semantic.svg, validation_report_final.json, iteration_log.md, and iteration_log.jsonl. rendered*.png files are optional in image-only runs.
- After this node succeeds, DrawAI mirrors the declared final SVG to svg/semantic.svg for preview and PPT export. You do not write the mirror yourself.
- When a PageSpec input is connected, the mirrored SVG lives under svg/semantic.svg; compute PageSpec asset hrefs with page-spec-assets --svg-dir svg and use those hrefs in every SVG you write. Validate PageSpec-connected SVGs with svg-validate --href-base-dir svg so validation uses the same canonical href base.

SOURCE POLICY
- svg_self_draw: use editable SVG primitives/text for text, formulas, arrows, frames, tables, axes, borders, simple charts, simple icons, and simple diagram components.
- crop: use an exact local crop image for screenshots, photos, dense raster texture, heatmaps, complex small icons, or details that are not worth or not possible to faithfully redraw as SVG.
- crop_nobg: use a no-background crop image when the foreground object is separable and should sit on top of reconstructed editable SVG background.
- Use PageSpec build.processing_type labels as the default. Override only in the SVG source choice when the original image and current render clearly show that another source strategy is more faithful. Record the reason in the iteration log.
- Insert only hrefs returned by the page-spec-assets tool for PageSpec materialization outputs. Do not invent image paths, external URLs, file:// URLs, absolute paths, or base64 images.
- Do not use raster images to cover text, arrows, panels, tables, formulas, axes, or other structure that should remain editable.

RUN1 / COMPLETE FIRST PASS
- Write semantic_0.svg.
- It must be a complete whole-figure SVG, not a placeholder map, skeleton, gray-box map, or list of asset boxes.
- Cover the whole canvas.
- Use SVG/text for svg_self_draw elements.
- Use PageSpec materialization image hrefs for crop/crop_nobg elements when available.
- When a PageSpec input is connected, compute those hrefs with page-spec-assets --svg-dir svg. Even though the declared SVG output is written under this node attempt directory, the hrefs must be valid for the final mirrored SVG under svg/semantic.svg. In image-only runs, do not use image hrefs unless they are already connected as declared inputs.
- Preserve PageSpec bboxes unless visible evidence shows they need adjustment.
- Keep major objects separated and editable where appropriate.
- Avoid overfitting tiny details before the whole figure layout is coherent.
- In PageSpec-connected runs, render/validate semantic_0.svg to rendered_0.png and validation_report_0.json using the svg-validate tool with --href-base-dir svg.
- In image-only runs, skip PageSpec-backed rendering only if no PageSpec input is connected; record that in iteration_log.md and still run format validate --format-id drawai.semantic_svg.v1 --path <declared SVG output path> before finishing.
- Record Run1 in iteration_log.md and iteration_log.jsonl, including what was created, obvious issues, and any crop/crop_nobg regions that still need source decisions.

REFINE LOOP / DEFAULT 1 ROUND, MAX 2 ROUNDS
At the start of each round:
1. Use the latest SVG as input.
2. In PageSpec-connected runs, render it with svg-validate. In image-only runs, render only if a renderer is available through declared tools; otherwise inspect the SVG structure and compare against the original image directly.
3. Compare the render or SVG structure against the original image.
4. First inspect the whole figure, then inspect local regions.
5. Decide the highest-impact fixes yourself.

Refinement budget:
- Default: run exactly one refinement round after Run1, then finalize.
- Skip the refinement round only when Run1 already validates and the whole-figure match is clearly acceptable.
- Run a second refinement round only if the latest validator failed, the render is blank/broken, required raster hrefs are invalid, or one clearly fixable high-impact structure issue would block a useful PPT.
- Do not run a third refinement round in this workflow. Preserve time for finalization.
- For image-only DAGs, never run more than one refinement round unless validation failed. Image-only runs lack PageSpec assets, so prioritize a coherent editable SVG over exhaustive pixel matching.

In each round, consider:
- Whole-figure layout mismatch: canvas scale, panel positions, major blocks, relative spacing, z-order.
- Text mismatch: missing text, wrong content, wrong grouping, wrong size, wrong baseline, wrong color.
- Connector/arrow mismatch: missing arrows, wrong direction, wrong endpoint, wrong arrowhead, wrong layering.
- Shape/table/axis mismatch: wrong borders, grids, ticks, legends, blocks, fills, strokes.
- Asset source mismatch: crop/crop_nobg region redrawn badly, missing PageSpec materialization href, wrong crop/no-background choice, image placed at the wrong bbox.
- Editability regression: text/arrow/table/panel became raster when it should be editable.
- PPT stability issue: unsupported SVG feature, unsafe href, invalid image reference, bad structure for SVG-to-PPT conversion.
- Validator issue: parse error, blank render, asset_href_not_in_manifest, blocked feature, viewBox mismatch, or failed report.

Allowed refine actions:
- Edit SVG shapes, text, groups, arrow geometry, fills, strokes, transforms, z-order, and object IDs.
- Add or remove SVG elements when the original image supports it.
- Insert allowed PageSpec materialization hrefs for crop/crop_nobg regions.
- Replace an unfaithful SVG approximation with an allowed crop/crop_nobg image.
- Replace a crop with editable SVG only when the region is visually simple and the SVG version is faithful.
- Adjust materialized image placement/size to match refined bboxes or visible evidence.
- Correct text from the connected image and PageSpec text fields.

Round outputs:
- In PageSpec-connected runs, Round 1 writes semantic_1.svg, rendered_1.png, and validation_report_1.json.
- In PageSpec-connected runs, optional Round 2 writes semantic_2.svg, rendered_2.png, and validation_report_2.json.
- In image-only runs, Round 1 writes semantic_1.svg when used, and optional Round 2 writes semantic_2.svg only when validation failed. Rendered PNGs and per-round validation reports are optional in image-only runs; validation_report_final.json remains required.

After each round, write to iteration_log.md and iteration_log.jsonl: round number, input SVG, output SVG/render/report, issues found, changes made, asset source changes if any, validation status, and stop or continue decision.

Stop after Run1 or Round 1 when all of these are true:
- The latest validator report is status=\"ok\" for the validation mode available to this DAG.
- The whole-figure render is coherent and broadly close to the original under the current constraints.
- Text, arrows, panels, tables, axes, images, and icons are not obviously missing or broken.
- crop/crop_nobg regions use allowed PageSpec materialization sources, or any exception is explicitly logged.
- Editable structures remain editable.
- Another round would likely improve only small details.

FINALIZATION
- Choose the latest acceptable SVG as the final result.
- Write the accepted final SVG to output/semantic.svg, the declared node-output path.
- In PageSpec-connected runs, render/validate semantic.svg to rendered.png and validation_report_final.json with --href-base-dir svg. Finish only after validation_report_final.json reports status=\"ok\".
- In image-only runs, run format validate --format-id drawai.semantic_svg.v1 --path <declared SVG output path>, write validation_report_final.json with the command result and status, and explain in iteration_log.md that no PageSpec-backed raster validation was available.
- If validation is already ok and time is being spent on minor visual tweaks, stop tweaking and finalize. A complete valid final SVG is better than an unfinished extra refinement.

OVERALL SVG/PPT PROFILE
Target the DrawAI Scientific SVG Profile v1 for editable PPT conversion. Treat the input as an editable scientific structure diagram, not as a bitmap tracing task. Infer the visual language: background, major modules, arrows/connectors, annotations, legends, stroke weights, rounded corners, palette, gradients, typography, and flow direction.
- Use rect for panels/modules/boxes, circle/ellipse for simple nodes/badges/dots, line/polyline for straight or orthogonal connectors, path only when curves/brackets/custom geometry are really needed, polygon for arrowheads or simple closed geometry, text/tspan for all visible text and formulas, and g for stable grouping.
- Use defs only for simple reusable markers or supported gradients. Prefer solid fills for core semantic objects.
- Use image elements only for explicit local raster assets from PageSpec materialization.
- Do not output CSS style blocks, filters, masks, clipPath, foreignObject, textPath, pattern fills, base64 images, external image URLs, absolute paths, symbol, or use.
- Prefer direct SVG presentation attributes over CSS classes for fill, stroke, font-size, opacity, and dash styling.
- Use stable semantic groups with ids prefixed module-, flow-, annotation-, legend-, panel-, connector-, label-, node-, image-, decorative-, or background-.
- For numbered/lettered badges, use a simple circle/ellipse plus centered editable text.
- Prefer orthogonal connector geometry when the source uses horizontal/vertical flows. Route connectors to module edges and avoid crossing text or panel centers.
- Filled or thick block arrows should be one closed shape. Thin connectors should keep shaft and arrowhead together after SVG-to-PPT conversion.
- Render connector arrows after background panels/modules and before raster image assets.
- Preserve editable text with text/tspan. For formulas, render a visible SVG fallback with Unicode math characters and tspan superscript/subscript, and also keep the original LaTeX source on the formula group for PPT export.
- A formula includes standalone mathematical variables or symbols with subscripts, superscripts, accents, Greek letters, operators, or relation signs. Mark these as formula groups even when they are short labels, legends, or isolated variables.
- Do not flatten formula structure into plain text such as alphai, xi2, yhat, or theta0. Use LaTeX for the source and use tspan baseline-shift in the visible fallback for subscripts and superscripts.
- Formula groups must use data-pb-role="formula", data-pb-editable="true", a stable id, data-pb-formula-bbox="x y width height" in SVG viewBox coordinates, and data-pb-formula-latex-b64 with UTF-8 base64 LaTeX. Use data-pb-formula-latex only when the LaTeX is fully XML-escaped.
- Do not display raw LaTeX in the visible SVG text layer. The visible layer is only the SVG fallback; svg_to_ppt reads the hidden LaTeX metadata and exports it as editable Office Math when possible.
- Formula SVG example:
  <g id="label-formula-example" data-pb-role="formula" data-pb-editable="true" data-pb-formula-bbox="100 112 220 40" data-pb-formula-latex-b64="XGFscGhhX2leMitcYmV0YV9pPWNfaQ==">
    <text id="label-formula-example-fallback" x="100" y="140" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="700" fill="#111" text-anchor="start" data-pb-role="formula" data-pb-editable="true" data-pb-text-source="visual_inferred" data-pb-orientation="horizontal">&#945;<tspan baseline-shift="sub" font-size="18">i</tspan><tspan baseline-shift="super" font-size="18">2</tspan> + &#946;<tspan baseline-shift="sub" font-size="18">i</tspan> = c<tspan baseline-shift="sub" font-size="18">i</tspan></text>
    <desc>LaTeX: \\alpha_i^2+\\beta_i=c_i</desc>
  </g>
- Mark non-editable raster assets with data-pb-editable=\"false\" and editable vectors/text with data-pb-editable=\"true\".

FINAL CHECK BEFORE ENDING THIS RUN
- semantic_0.svg exists. In PageSpec-connected runs it also has render/validation output.
- 0-2 refine rounds were run. If 0 rounds were run, explain why Run1 already met the stop condition. If 2 rounds were run, explain the validator failure or high-impact issue that justified it.
- semantic.svg is the accepted final SVG output. In PageSpec-connected runs, rendered.png is the accepted final render output; in image-only runs, rendered.png is optional but validation_report_final.json is required.
- validation_report_final.json is status=\"ok\" for the validation mode available to this DAG.
- iteration_log.md and iteration_log.jsonl explain every round and stop/continue decision.
- Keep the final chat response short; files are the source of truth."""

SVG_GENERATION_TASK_ZH = """图像向量化任务
目标：把一张位图图形转换成可编辑、适合稳定导出到 PPT 的 SVG。

DRAWAI 总体流程
完整 DrawAI 任务分为三个概念阶段：
1. 资产解析：SAM/OCR 为单页生成 PageSpec element evidence。
2. PageSpec 精修和资产准备：精修 PageSpec elements，调整 bboxes，拆分/合并元素，补充缺失元素，决定每个元素的 build.processing_type，并把 crop/crop_nobg 输出 materialize 到 PageSpec bundle 的 element.materialization 中。
3. 图像可编辑化：把可编辑 SVG primitives/text 与允许的 raster crop assets 组合起来，重建整张图，使其成为可编辑的 SVG/PPT 表达。

当前 Agent node 只执行第 3 阶段。不要重做 parsing、refinement 或 asset preparation。使用连接进来的原始图像作为视觉真值。如果连接输入列表中没有 PageSpec，就从一开始按 direct-image path 处理。连接了 materialized PageSpec input 时，把它作为结构化计划，并且只使用其中 element.materialization 输出作为 raster asset sources。你的工作是创建一个完整的一版 SVG，运行 validation，按下面的 bounded refinement rounds 做修正，并始终在 agent timeout 前完成声明的最终 SVG 和日志。

执行模型
- DrawAI runner 会准备 node work directory 和 connected input files。你必须自己读取这些文件。
- 你可以使用普通 shell utilities 或简短 local scripts 来检查 connected files 并写入 node-local outputs。涉及 DrawAI-specific behavior 时，不要检查仓库源码、不要导入内部 DrawAI 模块、不要调用内部 Python API；只使用声明的 DrawAI CLI tools 以及它们的 `help` / `format describe` contracts。
- 声明的 SVG output 是下游节点消费的 semantic output。这个 task 也会有意在同一个 node output directory 内写辅助 SVG/render/report/log 文件；这些辅助文件是允许的 task artifacts，不是额外的 downstream outputs。
- 你必须创建 intermediate SVGs，检查它们，修订它们，并以声明的最终 SVG 和 logs 收尾。在 PageSpec-connected runs 中，还要用 svg-validate 创建请求的 renders/reports。
- Run1 和每个 refine round 都可以使用 PageSpec element.materialization 产生的允许 local raster image hrefs，前提是元素 source 是 crop 或 crop_nobg。
- 如果此节点用于没有 PageSpec input 的 image-only DAG，则直接从图像重建，全部结构使用 editable SVG，不要调用 page-spec-assets，并用 format tool 校验最终 SVG，而不是用 PageSpec-backed svg-validate。
- Finalization 优先级高于再多做一轮 refinement。如果最新 SVG 已通过 validation 且整体足够 faithful，立刻 finalize。

可用文件和读取逻辑
本阶段的主要文件：
- Original/current reference image。把它作为 layout、color、text placement、arrows、icons、images、tables、axes 和 spacing 的视觉真值。
- Materialized PageSpec JSON（如已连接）。把它作为主要结构化计划：element ids、kind、role、bbox、z_index、text、style、measurement、grouping、build.processing_type 和 materialization outputs。
- PageSpec materialized assets（如已连接）。使用声明的 DrawAI page-spec-assets tool，从 materialized PageSpec 计算 crop/crop_nobg elements 的允许 local raster hrefs。
- SVG validation。在 PageSpec-connected runs 中，对每一组 SVG/render/report 使用声明的 DrawAI svg-validate tool。在 image-only runs 中，对最终 SVG 使用 format validate，并把 validation command 记录到 iteration_log.md。

读取顺序：
1. 从 original image 和连接的 materialized PageSpec（如果存在）开始。它们定义本阶段要复现什么。
2. 连接 PageSpec input 时，在插入任何 raster image href 前，先用 connected PageSpec 调用 page-spec-assets tool 计算 href。使用 --svg-dir svg，这样最终 SVG 被 mirror 到 svg/semantic.svg 用于 preview 和 PPT export 后 href 仍能解析。Image-only runs 完全跳过此步骤。
3. 不要寻找未连接的 OCR、template、layout、request 或 parser files。连接 PageSpec 时，OCR/SAM evidence 已经融合进 PageSpec。
4. reasoning 中保持 request JSON 紧凑。不要把完整 JSON 文件打印到 terminal 或 logs。

路径模型
- Agent process cwd 是 workflow run root。
- 下面显示的 declared output path 是 node-local final SVG，例如 nodes/svg_compose/runs/001/output/semantic.svg。
- PageSpec-connected runs 中，把每个辅助文件写在同一个 node output directory 中并靠近 declared output：semantic_0.svg、rendered_0.png、validation_report_0.json、semantic_1.svg、rendered_1.png、validation_report_1.json、optional semantic_2.svg、optional rendered_2.png、optional validation_report_2.json、rendered.png、validation_report_final.json、iteration_log.md 和 iteration_log.jsonl。
- Image-only runs 中，写 semantic_0.svg；使用 refinement round 时写 semantic_1.svg；只有 validation failed 时才可选写 semantic_2.svg；还要写 semantic.svg、validation_report_final.json、iteration_log.md 和 iteration_log.jsonl。Image-only runs 中 rendered*.png 是可选的。
- 此节点成功后，DrawAI 会把声明的 final SVG mirror 到 svg/semantic.svg 用于 preview 和 PPT export。你不要自己写这个 mirror。
- 连接 PageSpec input 时，mirrored SVG 位于 svg/semantic.svg 下；用 page-spec-assets --svg-dir svg 计算 PageSpec asset hrefs，并在你写的每个 SVG 中使用这些 hrefs。用 svg-validate --href-base-dir svg 校验 PageSpec-connected SVGs，这样 validation 使用同一个 canonical href base。

源策略
- svg_self_draw：对 text、formulas、arrows、frames、tables、axes、borders、simple charts、simple icons 和 simple diagram components 使用 editable SVG primitives/text。
- crop：对 screenshots、photos、dense raster texture、heatmaps、complex small icons，或者不值得/无法用 SVG 忠实重画的细节，使用精确 local crop image。
- crop_nobg：当 foreground object 可分离并应放在重建的 editable SVG background 上时，使用 no-background crop image。
- 默认遵循 PageSpec build.processing_type labels。只有当原图和当前 render 明确显示其他 source strategy 更 faithful 时，才在 SVG source choice 中 override。把原因记录到 iteration log。
- 对 PageSpec materialization outputs，只插入 page-spec-assets tool 返回的 hrefs。不要发明 image paths、external URLs、file:// URLs、absolute paths 或 base64 images。
- 不要用 raster images 覆盖 text、arrows、panels、tables、formulas、axes 或其他应保持 editable 的结构。

RUN1 / 完整第一版
- 写 semantic_0.svg。
- 它必须是完整 whole-figure SVG，不是 placeholder map、skeleton、gray-box map 或 asset boxes 列表。
- 覆盖整个 canvas。
- 对 svg_self_draw elements 使用 SVG/text。
- 可用时，对 crop/crop_nobg elements 使用 PageSpec materialization image hrefs。
- 连接 PageSpec input 时，用 page-spec-assets --svg-dir svg 计算这些 hrefs。尽管 declared SVG output 写在本 node attempt directory 下，hrefs 必须对最终 mirror 到 svg/semantic.svg 的 SVG 有效。Image-only runs 中，除非 image hrefs 已作为 declared inputs 连接进来，否则不要使用 image hrefs。
- 除非视觉证据显示需要调整，否则保留 PageSpec bboxes。
- 适当保持主要对象分离和可编辑。
- 在整张图 layout coherent 之前，避免过度拟合小细节。
- PageSpec-connected runs 中，用 svg-validate tool 和 --href-base-dir svg 将 semantic_0.svg render/validate 到 rendered_0.png 和 validation_report_0.json。
- Image-only runs 中，只有未连接 PageSpec input 时才跳过 PageSpec-backed rendering；在 iteration_log.md 中记录这一点，并且结束前仍需运行 format validate --format-id drawai.semantic_svg.v1 --path <declared SVG output path>。
- 在 iteration_log.md 和 iteration_log.jsonl 中记录 Run1，包括创建了什么、明显问题，以及仍需 source decisions 的 crop/crop_nobg regions。

REFINE LOOP / 默认 1 轮，最多 2 轮
每一轮开始时：
1. 使用最新 SVG 作为输入。
2. PageSpec-connected runs 中，用 svg-validate render 它。Image-only runs 中，只有当声明工具中有 renderer 可用时才 render；否则直接检查 SVG structure 并对照原图。
3. 对比 render 或 SVG structure 与原始图像。
4. 先检查整张图，再检查局部区域。
5. 自行决定最高影响的修复。

Refinement budget：
- 默认：Run1 后正好运行一轮 refinement，然后 finalize。
- 只有当 Run1 已经 validates 且 whole-figure match 明确可接受时，才跳过 refinement round。
- 只有当最新 validator failed、render blank/broken、required raster hrefs invalid，或存在一个明显可修复且会阻碍 useful PPT 的 high-impact structure issue 时，才运行第二轮 refinement。
- 不要在此 workflow 中运行第三轮 refinement。保留时间用于 finalization。
- 对 image-only DAGs，除非 validation failed，否则不要超过一轮 refinement。Image-only runs 没有 PageSpec assets，所以优先保证 coherent editable SVG，而不是穷尽 pixel matching。

每轮考虑：
- Whole-figure layout mismatch：canvas scale、panel positions、major blocks、relative spacing、z-order。
- Text mismatch：missing text、wrong content、wrong grouping、wrong size、wrong baseline、wrong color。
- Connector/arrow mismatch：missing arrows、wrong direction、wrong endpoint、wrong arrowhead、wrong layering。
- Shape/table/axis mismatch：wrong borders、grids、ticks、legends、blocks、fills、strokes。
- Asset source mismatch：crop/crop_nobg region redrawn badly、missing PageSpec materialization href、wrong crop/no-background choice、image placed at the wrong bbox。
- Editability regression：text/arrow/table/panel 变成 raster，但本应 editable。
- PPT stability issue：unsupported SVG feature、unsafe href、invalid image reference、对 SVG-to-PPT conversion 不友好的结构。
- Validator issue：parse error、blank render、asset_href_not_in_manifest、blocked feature、viewBox mismatch 或 failed report。

允许的 refine actions：
- 编辑 SVG shapes、text、groups、arrow geometry、fills、strokes、transforms、z-order 和 object IDs。
- 当原始图像支持时，添加或删除 SVG elements。
- 对 crop/crop_nobg regions 插入允许的 PageSpec materialization hrefs。
- 用允许的 crop/crop_nobg image 替换不 faithful 的 SVG approximation。
- 只有当区域视觉简单且 SVG version faithful 时，才用 editable SVG 替换 crop。
- 调整 materialized image placement/size 以匹配 refined bboxes 或视觉证据。
- 根据连接图像和 PageSpec text fields 更正文本。

每轮输出：
- PageSpec-connected runs 中，Round 1 写 semantic_1.svg、rendered_1.png 和 validation_report_1.json。
- PageSpec-connected runs 中，可选 Round 2 写 semantic_2.svg、rendered_2.png 和 validation_report_2.json。
- Image-only runs 中，使用 Round 1 时写 semantic_1.svg；只有 validation failed 时，可选 Round 2 写 semantic_2.svg。Rendered PNGs 和 per-round validation reports 对 image-only runs 是可选的；validation_report_final.json 仍然必填。

每轮结束后，写入 iteration_log.md 和 iteration_log.jsonl：round number、input SVG、output SVG/render/report、发现的问题、做出的改动、asset source changes（如有）、validation status，以及 stop 或 continue decision。

当以下条件全部满足时，在 Run1 或 Round 1 后停止：
- 最新 validator report 对此 DAG 可用的 validation mode 返回 status=\"ok\"。
- Whole-figure render coherent，且在当前约束下与原图 broadly close。
- Text、arrows、panels、tables、axes、images 和 icons 没有明显 missing 或 broken。
- crop/crop_nobg regions 使用允许的 PageSpec materialization sources，或任何例外都已明确记录。
- Editable structures 仍保持 editable。
- 再来一轮很可能只会改善小细节。

FINALIZATION
- 选择最新可接受 SVG 作为最终结果。
- 将 accepted final SVG 写到 output/semantic.svg，也就是声明的 node-output path。
- PageSpec-connected runs 中，用 --href-base-dir svg 将 semantic.svg render/validate 到 rendered.png 和 validation_report_final.json。只有 validation_report_final.json 报告 status=\"ok\" 后才能结束。
- Image-only runs 中，运行 format validate --format-id drawai.semantic_svg.v1 --path <declared SVG output path>，用 command result 和 status 写 validation_report_final.json，并在 iteration_log.md 中说明没有可用的 PageSpec-backed raster validation。
- 如果 validation 已经 ok，而时间正花在 minor visual tweaks 上，停止 tweaking 并 finalize。完整有效的 final SVG 比没完成的 extra refinement 更重要。

整体 SVG/PPT PROFILE
目标是 DrawAI Scientific SVG Profile v1，以便转换成可编辑 PPT。把输入看作可编辑 scientific structure diagram，而不是 bitmap tracing task。推断视觉语言：background、major modules、arrows/connectors、annotations、legends、stroke weights、rounded corners、palette、gradients、typography 和 flow direction。
- 对 panels/modules/boxes 使用 rect，对 simple nodes/badges/dots 使用 circle/ellipse，对 straight 或 orthogonal connectors 使用 line/polyline，只有 curves/brackets/custom geometry 确实需要时才用 path，对 arrowheads 或 simple closed geometry 使用 polygon，对所有 visible text 和 formulas 使用 text/tspan，并用 g 做 stable grouping。
- defs 只用于简单 reusable markers 或 supported gradients。核心 semantic objects 优先使用 solid fills。
- image elements 只能用于 PageSpec materialization 中明确的 local raster assets。
- 不要输出 CSS style blocks、filters、masks、clipPath、foreignObject、textPath、pattern fills、base64 images、external image URLs、absolute paths、symbol 或 use。
- 对 fill、stroke、font-size、opacity 和 dash styling，优先使用 direct SVG presentation attributes，而不是 CSS classes。
- 使用 stable semantic groups，id 前缀为 module-、flow-、annotation-、legend-、panel-、connector-、label-、node-、image-、decorative- 或 background-。
- 对 numbered/lettered badges，使用简单 circle/ellipse 加居中 editable text。
- 源图使用 horizontal/vertical flows 时，优先使用 orthogonal connector geometry。把 connectors route 到 module edges，避免穿过 text 或 panel centers。
- Filled 或 thick block arrows 应是一个 closed shape。Thin connectors 在 SVG-to-PPT conversion 后仍应保持 shaft 和 arrowhead 组合在一起。
- 在 background panels/modules 之后、raster image assets 之前 render connector arrows。
- 用 text/tspan 保留 editable text。对 formulas，渲染一个包含 Unicode math characters 和 tspan superscript/subscript 的可见 SVG fallback，同时在 formula group 上保留 original LaTeX source 供 PPT export 使用。
- Formula 包括带 subscripts、superscripts、accents、Greek letters、operators 或 relation signs 的独立 mathematical variables 或 symbols。即使它们是短 labels、legends 或 isolated variables，也标记为 formula groups。
- 不要把公式结构 flatten 成 alphai、xi2、yhat 或 theta0 这类 plain text。source 使用 LaTeX，可见 fallback 中用 tspan baseline-shift 表示 subscripts 和 superscripts。
- Formula groups 必须使用 data-pb-role=\"formula\"、data-pb-editable=\"true\"、stable id、SVG viewBox 坐标中的 data-pb-formula-bbox=\"x y width height\"，以及包含 UTF-8 base64 LaTeX 的 data-pb-formula-latex-b64。只有 LaTeX 完全 XML-escaped 时才使用 data-pb-formula-latex。
- 不要在 visible SVG text layer 中显示 raw LaTeX。Visible layer 只放 SVG fallback；svg_to_ppt 会读取 hidden LaTeX metadata，并在可能时导出为 editable Office Math。
- Formula SVG example:
  <g id="label-formula-example" data-pb-role="formula" data-pb-editable="true" data-pb-formula-bbox="100 112 220 40" data-pb-formula-latex-b64="XGFscGhhX2leMitcYmV0YV9pPWNfaQ==">
    <text id="label-formula-example-fallback" x="100" y="140" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="700" fill="#111" text-anchor="start" data-pb-role="formula" data-pb-editable="true" data-pb-text-source="visual_inferred" data-pb-orientation="horizontal">&#945;<tspan baseline-shift="sub" font-size="18">i</tspan><tspan baseline-shift="super" font-size="18">2</tspan> + &#946;<tspan baseline-shift="sub" font-size="18">i</tspan> = c<tspan baseline-shift="sub" font-size="18">i</tspan></text>
    <desc>LaTeX: \\alpha_i^2+\\beta_i=c_i</desc>
  </g>
- 用 data-pb-editable=\"false\" 标记 non-editable raster assets，用 data-pb-editable=\"true\" 标记 editable vectors/text。

结束本轮之前的最终检查
- semantic_0.svg 存在。在 PageSpec-connected runs 中，它也有 render/validation output。
- 已运行 0-2 轮 refine。如果是 0 轮，说明为什么 Run1 已满足停止条件。如果是 2 轮，说明 validator failure 或 high-impact issue 为什么需要第二轮。
- semantic.svg 是 accepted final SVG output。PageSpec-connected runs 中，rendered.png 是 accepted final render output；image-only runs 中 rendered.png 可选，但 validation_report_final.json 必填。
- validation_report_final.json 对此 DAG 可用的 validation mode 返回 status=\"ok\"。
- iteration_log.md 和 iteration_log.jsonl 解释每一轮以及 stop/continue decision。
- 最终 chat response 保持简短；文件才是事实来源。"""

SVG_GENERATION_CONSTRAINTS = (
    "Use only connected input files listed in this prompt and explicitly declared built-in script files.",
    "Do not inspect repository source code, import internal DrawAI modules, or call internal DrawAI APIs; use declared DrawAI CLI tools for DrawAI-specific behavior.",
    "Do not redo parsing or PageSpec refinement; consume the connected materialized PageSpec when present and the original image as evidence.",
    "Do not use MCP tools, apps, web search, memories, skills, hooks, or multi-agent delegation.",
    "Do not invent image hrefs, external URLs, file:// URLs, absolute paths, or base64 images.",
    "Do not rasterize panels, arrows, text, formulas, grids, tables, axes, or whole diagram structure.",
    "Write the declared final SVG plus task-requested auxiliary render/report/log files inside this node output directory and keep the final chat response short.",
)

CUSTOM_AGENT_TASK = """Use the connected input files as context and produce exactly the output files declared by this node configuration.

This is a configurable DrawAI Agent node. The node editor controls the task, input inclusion, input descriptions, output declarations, provider, model/profile/reasoning settings, timeout, and runtime constraints. Read the connected files listed in the prompt, follow the declared output formats, and write only the declared outputs."""

CUSTOM_AGENT_CONSTRAINTS = (
    "Treat every connected input file as explicit node context.",
    "Honor the configured output declarations over node defaults.",
    "Write only the declared output paths inside this node work directory.",
)
