# DrawAI v2 Robust Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace DrawAI's current main path with a package-authoritative v2 pipeline for parser fusion, Agent refinement, asset processing, and Workbench-controlled reuse.

**Architecture:** Introduce focused v2 domain modules first, then connect them to file-backed stages, CLI, Workbench API, and Workbench UI. Keep current SVG/PPTX code reachable through compatibility exports while making `drawai_package.json` and per-asset packages the v2 source of truth.

**Tech Stack:** Python 3.12, dataclasses, Pillow, FastAPI, pytest, existing DrawAI `DagRunner`/`ArtifactStore`, React 19, TypeScript, Vite.

---

## Scope And Sequencing

This plan implements the approved spec in one feature branch, with frequent commits. The work is intentionally ordered so each task leaves the repo in a testable state:

1. v2 schemas, registries, and package IO
2. parser adapters and deterministic fusion
3. Agent refine contract and Codex adapter
4. asset processors and per-asset package mutation
5. v2 file-backed stages and public stage routing
6. SVG/PPTX compatibility composition
7. CLI commands
8. Workbench backend/API and legacy read-only enforcement
9. Workbench frontend asset package UI
10. end-to-end smoke, docs, and cleanup

The first implementation must not migrate legacy run intermediates into v2 packages. It can fork a legacy run into a fresh v2 run using the original source image.

## File Structure

Create these focused v2 modules:

- `src/drawai/v2/__init__.py`: public exports for v2 contracts.
- `src/drawai/v2/schema.py`: dataclasses, constants, validation helpers for candidates, plans, run packages, and asset packages.
- `src/drawai/v2/registry.py`: core enum registry and extension registration.
- `src/drawai/v2/packages.py`: filesystem layout, package read/write helpers, legacy detection.
- `src/drawai/v2/parsers.py`: SAM3/OCR/current-output adapter providers.
- `src/drawai/v2/fusion.py`: priority/NMS fusion engine and trace writer.
- `src/drawai/v2/refine.py`: Agent refinement contract, validation, Codex invocation wrapper.
- `src/drawai/v2/processors.py`: crop, crop_nobg, svg_self_draw, image_generate, image_edit, chart reserved processor contracts.
- `src/drawai/v2/stages.py`: v2 `StageSpec` builders and stage implementations.
- `src/drawai/v2/compat.py`: derived `box_ir.json`, `element_analysis.json`, and `asset_manifest.json` exports for existing SVG/PPT code.
- `src/drawai/v2/workbench.py`: Workbench-facing helpers for package payloads, mutation checks, and legacy forking.

Modify these existing files:

- `src/drawai/artifacts.py`: add v2 package paths to `DrawAiArtifactPaths`.
- `src/drawai/config.py`: add v2 parse/fusion/refine/processor config sections.
- `src/drawai/public_stages.py`: expose v2 public stages as the main stage order.
- `src/drawai/pipeline.py`: route full runs through v2 stages while preserving compatibility summary shape.
- `src/drawai/stages/file_backed.py`: add v2 stage specs and preserve compatibility stage aliases.
- `src/drawai/cli.py`: add v2 stage and asset commands.
- `src/drawai/local_cli.py`: ensure `uv run drawai run image.png --local` uses v2 by default.
- `src/drawai/workbench/models.py`: add v2 package metadata fields and case status support when needed.
- `src/drawai/workbench/runner.py`: run v2 stages, register v2 artifacts, and block legacy mutation.
- `src/drawai/workbench/api.py`: add v2 package, element, asset processor, active result, compose/export, and fork endpoints.
- `src/drawai/workbench/store.py`: add case JSON helpers only if existing helpers cannot write package payloads safely.
- `apps/workbench/src/types.ts`: add v2 package, element, processor, and legacy case types.
- `apps/workbench/src/api.ts`: add v2 API wrappers.
- `apps/workbench/src/App.tsx`: show v2 package UI, asset drawer, processor actions, active result selection, legacy read-only actions.
- `apps/workbench/src/styles.css`: add compact styles for v2 package UI.

Add or update tests:

- `tests/v2/test_schema_registry_packages.py`
- `tests/v2/test_parsers_fusion.py`
- `tests/v2/test_refine_contract.py`
- `tests/v2/test_processors.py`
- `tests/v2/test_v2_public_stages.py`
- `tests/semantic_ppt/drawai_pipeline/test_cli_pipeline.py`
- `tests/workbench/test_store_api.py`
- `apps/workbench/src/*.test.tsx` only if this repo already has a frontend test runner configured during the task; otherwise verify frontend through `npm run build`.

---

### Task 1: Add v2 Schema, Registry, And Package IO

**Files:**
- Create: `src/drawai/v2/__init__.py`
- Create: `src/drawai/v2/schema.py`
- Create: `src/drawai/v2/registry.py`
- Create: `src/drawai/v2/packages.py`
- Modify: `src/drawai/artifacts.py`
- Test: `tests/v2/test_schema_registry_packages.py`

- [ ] **Step 1: Write failing schema and package tests**

Create `tests/v2/test_schema_registry_packages.py` with these tests:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from drawai.v2.packages import (
    classify_run_root,
    element_dir,
    read_run_package,
    write_asset_package,
    write_element_plan,
    write_run_package,
)
from drawai.v2.registry import DrawAiRegistry, default_registry
from drawai.v2.schema import (
    AssetPackage,
    ElementCandidate,
    ElementPlan,
    ProcessingIntent,
    RunPackage,
    validate_element_candidate,
    validate_element_plan,
)


def test_element_candidate_and_plan_validate_core_fields(tmp_path: Path) -> None:
    candidate = ElementCandidate(
        candidate_id="sam3:B001",
        source_parser="sam3_structure_parser",
        source_parser_version="v1",
        element_type="icon",
        bbox=(1.0, 2.0, 20.0, 30.0),
        geometry={"kind": "bbox", "bbox": [1, 2, 20, 30]},
        confidence=0.82,
        z_hint=0,
        text="",
        evidence_files=[],
        provenance={"prompt": "icon"},
        raw_ref={"path": "reports/parser_outputs/sam3.json", "index": 0},
    )
    validate_element_candidate(candidate, registry=default_registry())

    plan = ElementPlan(
        element_id="E001",
        source_candidate_ids=("sam3:B001",),
        element_type="icon",
        bbox=(1.0, 2.0, 20.0, 30.0),
        geometry={"kind": "bbox", "bbox": [1, 2, 20, 30]},
        z_order=0,
        confidence="high",
        processing_intent=ProcessingIntent(object_type="icon", processing_type="crop_nobg"),
        review_status="agent_refined",
        created_by_stage="refine_elements",
        change_reason="Kept source candidate.",
    )
    validate_element_plan(plan, registry=default_registry())


def test_registry_rejects_unknown_types_until_registered() -> None:
    registry = DrawAiRegistry.core()
    plan = ElementPlan(
        element_id="E001",
        source_candidate_ids=("sam3:B001",),
        element_type="molecule",
        bbox=(0.0, 0.0, 10.0, 10.0),
        geometry={"kind": "bbox", "bbox": [0, 0, 10, 10]},
        z_order=0,
        confidence="medium",
        processing_intent=ProcessingIntent(object_type="molecule", processing_type="crop"),
        review_status="deterministic",
        created_by_stage="fuse_elements",
        change_reason="Extension type example.",
    )
    with pytest.raises(ValueError, match="unregistered element_type"):
        validate_element_plan(plan, registry=registry)

    registry.register_element_type("molecule", schema_version="drawai.extension.element.molecule.v1", capabilities=("crop",))
    validate_element_plan(plan, registry=registry)


def test_run_and_asset_packages_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = RunPackage.new(run_id="run_001", root=root, source_image="inputs/figure.png", canvas={"width": 100, "height": 80})
    run = write_run_package(root, run)
    loaded = read_run_package(root)
    assert loaded["schema"] == "drawai.run_package.v1"
    assert loaded["run_id"] == "run_001"

    plan = ElementPlan(
        element_id="E001",
        source_candidate_ids=("ocr:T001",),
        element_type="text",
        bbox=(4.0, 5.0, 30.0, 18.0),
        geometry={"kind": "bbox", "bbox": [4, 5, 30, 18]},
        z_order=1,
        confidence="high",
        processing_intent=ProcessingIntent(object_type="text", processing_type="svg_self_draw"),
        review_status="deterministic",
        created_by_stage="fuse_elements",
        change_reason="Text from OCR.",
    )
    write_element_plan(root, plan)
    assert (element_dir(root, "E001") / "element.json").is_file()

    package = AssetPackage.empty(asset_id="A001", element_id="E001", processor_type="svg_self_draw")
    write_asset_package(root, package)
    assert json.loads((element_dir(root, "E001") / "asset_package.json").read_text(encoding="utf-8"))["asset_id"] == "A001"
    assert classify_run_root(root).mode == "v2"


def test_legacy_run_root_is_readonly_when_no_v2_package(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    (root / "svg").mkdir(parents=True)
    (root / "svg" / "semantic.svg").write_text("<svg />\n", encoding="utf-8")
    (root / "inputs").mkdir()
    (root / "inputs" / "figure.png").write_bytes(b"png")

    classification = classify_run_root(root)

    assert classification.mode == "legacy_readonly"
    assert classification.can_fork_from_source is True
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
uv run pytest tests/v2/test_schema_registry_packages.py -q
```

Expected: FAIL during import because `drawai.v2` modules do not exist.

- [ ] **Step 3: Create v2 dataclasses and validation helpers**

Create `src/drawai/v2/schema.py` with these public names and behavior:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

ELEMENT_CANDIDATE_SCHEMA = "drawai.element_candidate.v1"
ELEMENT_PLAN_SCHEMA = "drawai.element_plan.v1"
ASSET_PACKAGE_SCHEMA = "drawai.asset_package.v1"
RUN_PACKAGE_SCHEMA = "drawai.run_package.v1"

AssetStatus = Literal["pending", "running", "ok", "failed", "unsupported"]
ReviewStatus = Literal["deterministic", "agent_refined", "user_edited"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ProcessingIntent:
    object_type: str
    processing_type: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "processing_type": self.processing_type,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True)
class ElementCandidate:
    candidate_id: str
    source_parser: str
    source_parser_version: str
    element_type: str
    bbox: tuple[float, float, float, float]
    geometry: Mapping[str, Any]
    confidence: float
    z_hint: int
    text: str
    evidence_files: tuple[str, ...] | list[str]
    provenance: Mapping[str, Any]
    raw_ref: Mapping[str, Any]
    schema: str = ELEMENT_CANDIDATE_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["bbox"] = list(self.bbox)
        payload["evidence_files"] = list(self.evidence_files)
        return payload


@dataclass(frozen=True)
class ElementPlan:
    element_id: str
    source_candidate_ids: tuple[str, ...]
    element_type: str
    bbox: tuple[float, float, float, float]
    geometry: Mapping[str, Any]
    z_order: int
    confidence: str
    processing_intent: ProcessingIntent
    review_status: str
    created_by_stage: str
    change_reason: str
    schema: str = ELEMENT_PLAN_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["bbox"] = list(self.bbox)
        payload["source_candidate_ids"] = list(self.source_candidate_ids)
        payload["processing_intent"] = self.processing_intent.to_dict()
        return payload


@dataclass(frozen=True)
class AssetPackage:
    asset_id: str
    element_id: str
    status: AssetStatus
    source_refs: Mapping[str, Any]
    processor_plan: Mapping[str, Any]
    processor_runs: tuple[Mapping[str, Any], ...]
    active_result: str
    all_results: tuple[Mapping[str, Any], ...]
    editable_payload: Mapping[str, Any]
    failure: Mapping[str, Any]
    schema: str = ASSET_PACKAGE_SCHEMA

    @classmethod
    def empty(cls, *, asset_id: str, element_id: str, processor_type: str) -> "AssetPackage":
        return cls(
            asset_id=asset_id,
            element_id=element_id,
            status="pending",
            source_refs={},
            processor_plan={"processor_type": processor_type},
            processor_runs=(),
            active_result="",
            all_results=(),
            editable_payload={},
            failure={},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunPackage:
    run_id: str
    package_version: int
    source_image: str
    canvas: Mapping[str, Any]
    stage_status: Mapping[str, Any]
    parser_registry: Mapping[str, Any]
    fusion_config: Mapping[str, Any]
    refine_config: Mapping[str, Any]
    processor_registry: Mapping[str, Any]
    elements: tuple[Mapping[str, Any], ...]
    asset_packages: tuple[Mapping[str, Any], ...]
    compose_outputs: Mapping[str, Any]
    export_outputs: Mapping[str, Any]
    legacy_compatibility: Mapping[str, Any]
    created_at: str
    updated_at: str
    schema: str = RUN_PACKAGE_SCHEMA

    @classmethod
    def new(cls, *, run_id: str, root: str | Path, source_image: str, canvas: Mapping[str, Any]) -> "RunPackage":
        now = utc_now()
        return cls(
            run_id=run_id,
            package_version=1,
            source_image=source_image,
            canvas=dict(canvas),
            stage_status={},
            parser_registry={},
            fusion_config={},
            refine_config={},
            processor_registry={},
            elements=(),
            asset_packages=(),
            compose_outputs={},
            export_outputs={},
            legacy_compatibility={"mode": "v2", "root": str(Path(root).expanduser().resolve(strict=False))},
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_bbox(bbox: tuple[float, float, float, float] | list[Any], *, label: str) -> tuple[float, float, float, float]:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ValueError(f"{label}.bbox must contain four numbers")
    values = tuple(float(item) for item in bbox)
    if values[2] <= values[0] or values[3] <= values[1]:
        raise ValueError(f"{label}.bbox must have positive width and height")
    return values


def validate_element_candidate(candidate: ElementCandidate, *, registry: Any) -> None:
    if candidate.schema != ELEMENT_CANDIDATE_SCHEMA:
        raise ValueError(f"Unexpected candidate schema: {candidate.schema!r}")
    if not registry.has_element_type(candidate.element_type):
        raise ValueError(f"unregistered element_type: {candidate.element_type}")
    validate_bbox(candidate.bbox, label=candidate.candidate_id)
    if candidate.confidence < 0 or candidate.confidence > 1:
        raise ValueError(f"{candidate.candidate_id}.confidence must be between 0 and 1")


def validate_element_plan(plan: ElementPlan, *, registry: Any) -> None:
    if plan.schema != ELEMENT_PLAN_SCHEMA:
        raise ValueError(f"Unexpected element plan schema: {plan.schema!r}")
    if not registry.has_element_type(plan.element_type):
        raise ValueError(f"unregistered element_type: {plan.element_type}")
    if not registry.has_processing_type(plan.processing_intent.processing_type):
        raise ValueError(f"unregistered processing_type: {plan.processing_intent.processing_type}")
    validate_bbox(plan.bbox, label=plan.element_id)
    if not plan.element_id:
        raise ValueError("element_id is required")
```

- [ ] **Step 4: Create registry and package IO modules**

Create `src/drawai/v2/registry.py` with `DrawAiRegistry.core()`, `register_element_type()`, `register_processing_type()`, `has_element_type()`, `has_processing_type()`, and `default_registry()`. Core element and processing types must match the spec.

Create `src/drawai/v2/packages.py` with:

- `RunClassification(mode: str, root: Path, can_fork_from_source: bool)`
- `element_dir(root, element_id)`
- `write_run_package(root, package)`
- `read_run_package(root)`
- `write_element_plan(root, plan)`
- `write_asset_package(root, package)`
- `classify_run_root(root)`

Use `json.dumps(..., ensure_ascii=False, indent=2)` and a trailing newline. Reject writes outside the run root by resolving paths through `ArtifactStore` or a local equivalent.

- [ ] **Step 5: Add v2 artifact paths**

Modify `src/drawai/artifacts.py`:

- Add fields to `DrawAiArtifactPaths`: `run_package_json`, `v2_elements_dir`, `v2_parser_outputs_dir`, `v2_fusion_trace_json`, `v2_refine_trace_json`, `v2_processor_trace_jsonl`, `exports_dir`.
- Create those directories in `prepare_artifact_paths()`.
- Keep existing fields unchanged.

- [ ] **Step 6: Run schema/package tests**

Run:

```bash
uv run pytest tests/v2/test_schema_registry_packages.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/drawai/v2 src/drawai/artifacts.py tests/v2/test_schema_registry_packages.py
git commit -m "feat: add v2 package contracts"
```

---

### Task 2: Add Parser Adapters And Deterministic Fusion

**Files:**
- Create: `src/drawai/v2/parsers.py`
- Create: `src/drawai/v2/fusion.py`
- Modify: `src/drawai/v2/__init__.py`
- Test: `tests/v2/test_parsers_fusion.py`

- [ ] **Step 1: Write failing parser and fusion tests**

Create `tests/v2/test_parsers_fusion.py`:

```python
from __future__ import annotations

from pathlib import Path

from PIL import Image

from drawai.v2.fusion import FusionConfig, fuse_candidates
from drawai.v2.parsers import ocr_payload_to_candidates, sam3_payload_to_candidates


def test_sam3_and_ocr_payloads_convert_to_element_candidates(tmp_path: Path) -> None:
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    sam_payload = {
        "raw_regions": [
            {"bbox": [10, 10, 40, 35], "score": 0.91, "label": "icon", "source_prompt": "icon"}
        ]
    }
    ocr_payload = {
        "ocr_text_boxes": [
            {"id": "T001", "bbox": [12, 42, 60, 55], "text": "Hello", "confidence": 0.88}
        ]
    }

    sam_candidates = sam3_payload_to_candidates(sam_payload, source_image=image)
    ocr_candidates = ocr_payload_to_candidates(ocr_payload, source_image=image)

    assert sam_candidates[0].candidate_id == "sam3:B001"
    assert sam_candidates[0].element_type == "icon"
    assert ocr_candidates[0].candidate_id == "ocr:T001"
    assert ocr_candidates[0].text == "Hello"


def test_fusion_keeps_text_and_visual_candidates_separate() -> None:
    sam_candidates = sam3_payload_to_candidates(
        {"raw_regions": [{"bbox": [0, 0, 50, 50], "score": 0.8, "label": "picture"}]},
        source_image=Path("inputs/figure.png"),
    )
    ocr_candidates = ocr_payload_to_candidates(
        {"ocr_text_boxes": [{"id": "T001", "bbox": [5, 5, 45, 18], "text": "Title", "confidence": 0.9}]},
        source_image=Path("inputs/figure.png"),
    )

    result = fuse_candidates([*sam_candidates, *ocr_candidates], config=FusionConfig.default())

    assert [plan.element_type for plan in result.elements] == ["picture", "text"]
    assert result.trace["decisions"][0]["action"] == "kept"


def test_fusion_suppresses_lower_priority_duplicate_same_type() -> None:
    first = sam3_payload_to_candidates(
        {"raw_regions": [{"bbox": [10, 10, 40, 40], "score": 0.7, "label": "icon"}]},
        source_image=Path("inputs/figure.png"),
    )[0]
    second = sam3_payload_to_candidates(
        {"raw_regions": [{"bbox": [11, 11, 41, 41], "score": 0.95, "label": "icon"}]},
        source_image=Path("inputs/figure.png"),
        parser_id="vision_layout_parser",
        parser_priority=20,
    )[0]

    result = fuse_candidates([first, second], config=FusionConfig.default())

    assert len(result.elements) == 1
    assert result.elements[0].source_candidate_ids == (second.candidate_id,)
    assert any(item["action"] == "suppressed" for item in result.trace["decisions"])
```

- [ ] **Step 2: Run tests and verify failure**

```bash
uv run pytest tests/v2/test_parsers_fusion.py -q
```

Expected: FAIL because parser and fusion modules do not exist.

- [ ] **Step 3: Implement parser adapters**

Create `src/drawai/v2/parsers.py` with:

- `sam3_payload_to_candidates(payload, source_image, parser_id="sam3_structure_parser", parser_priority=10)`
- `ocr_payload_to_candidates(payload, source_image, parser_id="ocr_text_parser", parser_priority=5)`

Implementation requirements:

- Candidate IDs use stable prefixes: `sam3:B001`, `ocr:<source id>`.
- Use `normalize_box_type()` from `drawai.domain.box_ir` for known type aliases.
- Default unknown SAM type to `unknown`; default OCR type to `text`.
- Set `provenance["parser_priority"]`.
- Preserve mask geometry if region has `geometry.kind == "mask"` or `mask_path`.

- [ ] **Step 4: Implement deterministic fusion**

Create `src/drawai/v2/fusion.py` with:

- `FusionConfig`
- `FusionResult`
- `fuse_candidates(candidates, config)`

Rules:

- Sort by `(z_hint, top, left)` for output order.
- Same-type duplicates are suppressed when IoU is at or above `duplicate_iou_threshold`.
- Higher `parser_priority`, then higher confidence, wins duplicate conflicts.
- Text candidates and visual candidates do not suppress each other.
- Locked mask geometry cannot be geometrically merged with bbox candidates.
- Every decision is recorded in `trace["decisions"]`.

- [ ] **Step 5: Run parser/fusion tests**

```bash
uv run pytest tests/v2/test_parsers_fusion.py -q
```

Expected: PASS.

- [ ] **Step 6: Run existing BoxIR merge tests**

```bash
uv run pytest tests/domain/test_box_ir_domain_exports.py tests/semantic_ppt/drawai_pipeline/test_box_ir_merge.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/drawai/v2/parsers.py src/drawai/v2/fusion.py src/drawai/v2/__init__.py tests/v2/test_parsers_fusion.py
git commit -m "feat: add v2 parser fusion"
```

---

### Task 3: Add Agent Refinement Contract And Codex Adapter

**Files:**
- Create: `src/drawai/v2/refine.py`
- Modify: `scripts/run_codex_element_analysis.py`
- Test: `tests/v2/test_refine_contract.py`
- Test: `tests/semantic_ppt/drawai_pipeline/test_element_analysis_mask_geometry.py`

- [ ] **Step 1: Write failing refinement contract tests**

Create `tests/v2/test_refine_contract.py`:

```python
from __future__ import annotations

import pytest

from drawai.v2.refine import (
    RefineConfig,
    RefinementValidationError,
    validate_refined_elements,
)
from drawai.v2.schema import ElementPlan, ProcessingIntent


def _plan(element_id: str, source_ids: tuple[str, ...], processing_type: str = "crop") -> ElementPlan:
    return ElementPlan(
        element_id=element_id,
        source_candidate_ids=source_ids,
        element_type="icon",
        bbox=(1.0, 2.0, 20.0, 30.0),
        geometry={"kind": "bbox", "bbox": [1, 2, 20, 30]},
        z_order=0,
        confidence="high",
        processing_intent=ProcessingIntent(object_type="icon", processing_type=processing_type),
        review_status="agent_refined",
        created_by_stage="refine_elements",
        change_reason="Agent kept this element.",
    )


def test_refine_validation_requires_source_coverage() -> None:
    with pytest.raises(RefinementValidationError, match="missing source candidates"):
        validate_refined_elements(
            [_plan("E001", ("sam3:B001",))],
            expected_candidate_ids={"sam3:B001", "ocr:T001"},
            locked_geometry_by_candidate={},
        )


def test_refine_validation_rejects_locked_mask_bbox_change() -> None:
    changed = _plan("E001", ("sam3:B001",))
    changed = ElementPlan(
        **{**changed.to_dict(), "bbox": (0.0, 0.0, 40.0, 40.0), "processing_intent": changed.processing_intent}
    )
    with pytest.raises(RefinementValidationError, match="locked geometry"):
        validate_refined_elements(
            [changed],
            expected_candidate_ids={"sam3:B001"},
            locked_geometry_by_candidate={"sam3:B001": {"kind": "mask", "bbox": [1, 2, 20, 30]}},
        )


def test_refine_can_be_disabled_by_config() -> None:
    config = RefineConfig(enabled=False, provider="codex_element_refiner")
    assert config.enabled is False
    assert config.provider == "codex_element_refiner"
```

- [ ] **Step 2: Run tests and verify failure**

```bash
uv run pytest tests/v2/test_refine_contract.py -q
```

Expected: FAIL because `drawai.v2.refine` does not exist.

- [ ] **Step 3: Implement refinement validation**

Create `src/drawai/v2/refine.py` with:

- `RefineConfig`
- `RefinementValidationError`
- `validate_refined_elements(elements, expected_candidate_ids, locked_geometry_by_candidate)`
- `CodexElementRefiner`

Validation rules:

- all expected candidates must be represented by at least one element unless an element carries a removal record with reason
- duplicate element IDs fail
- invalid bbox fails
- unregistered processing intent fails through schema validation
- locked mask bbox and geometry must match source geometry when retained

- [ ] **Step 4: Adapt current Codex analysis script output**

Modify `scripts/run_codex_element_analysis.py` only where needed so its validated output can be converted into `ElementPlan` records by `drawai.v2.refine`.

Preserve existing script behavior:

- no git commands from the Codex child process
- mask preview enrichment remains intact
- `element_analysis.json` remains writable for compatibility export

- [ ] **Step 5: Run refinement and existing mask tests**

```bash
uv run pytest tests/v2/test_refine_contract.py tests/semantic_ppt/drawai_pipeline/test_element_analysis_mask_geometry.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/drawai/v2/refine.py scripts/run_codex_element_analysis.py tests/v2/test_refine_contract.py
git commit -m "feat: add v2 refinement contract"
```

---

### Task 4: Add Asset Processors And Asset Package Mutation

**Files:**
- Create: `src/drawai/v2/processors.py`
- Modify: `src/drawai/v2/packages.py`
- Modify: `src/drawai/codex_python_sdk_imagegen.py` only if package metadata cannot be obtained from existing return values
- Test: `tests/v2/test_processors.py`
- Test: `tests/workbench/test_assets.py`

- [ ] **Step 1: Write failing processor tests**

Create `tests/v2/test_processors.py`:

```python
from __future__ import annotations

from pathlib import Path

from PIL import Image

from drawai.rmbg_client import RmbgResult
from drawai.v2.packages import read_asset_package
from drawai.v2.processors import (
    ChartRebuildReservedProcessor,
    CropNoBgProcessor,
    CropProcessor,
    SvgSelfDrawProcessor,
)
from drawai.v2.schema import ElementPlan, ProcessingIntent


class FakeRmbgClient:
    def remove_background(self, image, output_name, *, timeout_s, model_path="", artifact_prefix=None):
        rgba = image.convert("RGBA")
        rgba.putpixel((0, 0), (255, 255, 255, 0))
        return RmbgResult(image=rgba, elapsed_ms=12.0, artifacts={"output_name": output_name})


def _plan(processing_type: str) -> ElementPlan:
    return ElementPlan(
        element_id="E001",
        source_candidate_ids=("sam3:B001",),
        element_type="icon",
        bbox=(2.0, 2.0, 12.0, 12.0),
        geometry={"kind": "bbox", "bbox": [2, 2, 12, 12]},
        z_order=0,
        confidence="high",
        processing_intent=ProcessingIntent(object_type="icon", processing_type=processing_type),
        review_status="agent_refined",
        created_by_stage="refine_elements",
        change_reason="Test element.",
    )


def test_crop_processor_writes_asset_package_result(tmp_path: Path) -> None:
    Image.new("RGBA", (20, 20), (255, 255, 255, 255)).save(tmp_path / "figure.png")

    package = CropProcessor().process(run_root=tmp_path, figure_image=tmp_path / "figure.png", plan=_plan("crop"))

    loaded = read_asset_package(tmp_path, "E001")
    assert package.status == "ok"
    assert loaded["active_result"]
    assert (tmp_path / loaded["all_results"][0]["output_path"]).is_file()


def test_crop_nobg_processor_records_rmbg_metadata(tmp_path: Path) -> None:
    Image.new("RGBA", (20, 20), (255, 255, 255, 255)).save(tmp_path / "figure.png")

    package = CropNoBgProcessor(rmbg_client=FakeRmbgClient()).process(
        run_root=tmp_path,
        figure_image=tmp_path / "figure.png",
        plan=_plan("crop_nobg"),
    )

    assert package.status == "ok"
    assert package.processor_runs[0]["processor_type"] == "crop_nobg"
    assert package.all_results[0]["metadata"]["rmbg_elapsed_ms"] == 12.0


def test_svg_self_draw_processor_creates_editable_payload(tmp_path: Path) -> None:
    package = SvgSelfDrawProcessor().process(run_root=tmp_path, figure_image=tmp_path / "figure.png", plan=_plan("svg_self_draw"))

    assert package.status == "ok"
    assert package.editable_payload["kind"] == "svg_self_draw_constraints"


def test_chart_reserved_processor_is_unsupported(tmp_path: Path) -> None:
    package = ChartRebuildReservedProcessor().process(
        run_root=tmp_path,
        figure_image=tmp_path / "figure.png",
        plan=_plan("chart_rebuild_reserved"),
    )

    assert package.status == "unsupported"
    assert "reserved" in package.failure["message"]
```

- [ ] **Step 2: Run tests and verify failure**

```bash
uv run pytest tests/v2/test_processors.py -q
```

Expected: FAIL because processors do not exist.

- [ ] **Step 3: Implement processors**

Create `src/drawai/v2/processors.py`:

- `AssetProcessor` protocol
- `CropProcessor`
- `CropNoBgProcessor`
- `SvgSelfDrawProcessor`
- `ImageGenerateProcessor`
- `ImageEditProcessor`
- `ChartRebuildReservedProcessor`
- `processor_for_type(processing_type, providers)`

Implementation requirements:

- Use `geometry_crop()` from `drawai.asset_geometry`.
- Write result files under `elements/<element_id>/results/<result_id>/`.
- Record `processor_runs` with `processor_type`, `status`, `started_at`, `ended_at`, `input_refs`, `output_refs`, and `metadata`.
- `ImageGenerateProcessor` and `ImageEditProcessor` call existing Codex image generation helpers and store provider metadata returned by those helpers.
- Any processor failure writes an asset package with `status="failed"` before re-raising at the processor boundary where the caller needs the exception.

- [ ] **Step 4: Add asset package read helper**

Extend `src/drawai/v2/packages.py` with `read_asset_package(root, element_id)`.

- [ ] **Step 5: Run processor tests and existing workbench asset tests**

```bash
uv run pytest tests/v2/test_processors.py tests/workbench/test_assets.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/drawai/v2/processors.py src/drawai/v2/packages.py tests/v2/test_processors.py
git commit -m "feat: add v2 asset processors"
```

---

### Task 5: Add V2 File-Backed Stages And Public Pipeline Routing

**Files:**
- Create: `src/drawai/v2/stages.py`
- Create: `src/drawai/v2/compat.py`
- Modify: `src/drawai/config.py`
- Modify: `src/drawai/public_stages.py`
- Modify: `src/drawai/pipeline.py`
- Modify: `src/drawai/stages/file_backed.py`
- Test: `tests/v2/test_v2_public_stages.py`
- Test: `tests/semantic_ppt/drawai_pipeline/test_public_stages.py`
- Test: `tests/stages/test_file_backed_stage_specs.py`

- [ ] **Step 1: Write failing v2 public stage tests**

Create `tests/v2/test_v2_public_stages.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from drawai.public_stages import PUBLIC_STAGE_ORDER, run_public_stage


def _config(tmp_path: Path) -> Path:
    image = tmp_path / "input.png"
    Image.new("RGB", (80, 40), "white").save(image)
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
input:
  image: {image.name}
  output_dir: out
  normalization:
    enabled: false
sam3:
  prompts:
    - id: icon
      text: icon
      confidence_threshold: 0.3
ocr:
  provider: fixture
  fixture:
    path: ocr_fixture.json
asset_materialization:
  rmbg:
    enabled: false
svg_to_ppt:
  enabled: true
  export_pptx: false
v2:
  refine:
    enabled: false
""",
        encoding="utf-8",
    )
    (tmp_path / "ocr_fixture.json").write_text(
        '{"ocr_text_boxes":[{"id":"T001","bbox":[4,5,20,14],"text":"Hello","confidence":0.9}]}',
        encoding="utf-8",
    )
    return config


def test_public_stage_order_uses_v2_main_path() -> None:
    assert PUBLIC_STAGE_ORDER == (
        "prepare",
        "parse_elements",
        "fuse_elements",
        "refine_elements",
        "plan_assets",
        "process_assets",
        "compose_svg",
        "export",
        "package_run",
    )


def test_v2_pipeline_writes_run_package_after_fusion(tmp_path: Path) -> None:
    summary = run_public_stage(_config(tmp_path), "fuse_elements")

    assert summary["status"] == "ok"
    package_path = Path(summary["artifacts"]["run_package"])
    assert package_path.is_file()
    payload = json.loads(package_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "drawai.run_package.v1"
    assert payload["elements"]
```

- [ ] **Step 2: Run tests and verify failure**

```bash
uv run pytest tests/v2/test_v2_public_stages.py -q
```

Expected: FAIL because public stage order still uses old stage names.

- [ ] **Step 3: Add config sections**

Modify `src/drawai/config.py`:

- Add `V2ParserConfig`, `V2FusionConfig`, `V2RefineConfig`, `V2ProcessorConfig`, `DrawAiV2Config`.
- Add `v2: DrawAiV2Config = DrawAiV2Config()` to `DrawAiPipelineConfig`.
- Parse optional YAML `v2` section.
- Defaults: `v2.enabled=True`, `v2.refine.enabled=True`, `v2.refine.provider="codex_element_refiner"`.

- [ ] **Step 4: Implement v2 stage specs**

Create `src/drawai/v2/stages.py` with:

- `V2_STAGE_ORDER`
- `build_v2_stage_specs(stage_ids, options)`
- stage runners for `prepare`, `parse_elements`, `fuse_elements`, `refine_elements`, `plan_assets`, `process_assets`, `compose_svg`, `export`, `package_run`

Use existing functions where possible:

- `normalize_input_image()` for prepare
- `run_sam3_prompt_plan()` and `_extract_ocr_boxes()` for parser providers
- `fuse_candidates()` for fusion
- `CodexElementRefiner` or deterministic pass-through when refine disabled
- processors from Task 4
- compatibility exports from `drawai.v2.compat`

- [ ] **Step 5: Implement compatibility exports**

Create `src/drawai/v2/compat.py` with:

- `write_box_ir_compat(root, elements, source_metadata)`
- `write_element_analysis_compat(root, elements)`
- `write_asset_manifest_compat(root, asset_packages)`

These functions write derived files for existing SVG/PPT code. They must not read legacy files as inputs.

- [ ] **Step 6: Route public stages through v2**

Modify `src/drawai/public_stages.py`:

- Replace `PUBLIC_STAGE_ORDER` with v2 stage order.
- Keep old names accepted through an alias map:
  - `detect_structure` and `detect_text` -> `parse_elements`
  - `assemble_boxir` -> `fuse_elements`
  - `asset_plan` -> `plan_assets`
  - `asset_analyze` -> `refine_elements`
  - `asset_materialize` -> `process_assets`
  - `svg` -> `compose_svg`
- Include `stage_alias` in summary when an old name is used.

- [ ] **Step 7: Route pipeline full run through v2**

Modify `src/drawai/pipeline.py`:

- `run_drawai_pipeline()` calls v2 stage runner by default.
- `run_drawai_pipeline_from_stage()` accepts v2 stages and old aliases.
- Summary retains `status`, `artifacts`, `failed_stage`, and `exception` shape.

- [ ] **Step 8: Run focused stage tests**

```bash
uv run pytest tests/v2/test_v2_public_stages.py tests/semantic_ppt/drawai_pipeline/test_public_stages.py tests/stages/test_file_backed_stage_specs.py -q
```

Expected: PASS. Existing old-stage tests should pass through alias expectations adjusted in the same task.

- [ ] **Step 9: Commit**

```bash
git add src/drawai/v2/stages.py src/drawai/v2/compat.py src/drawai/config.py src/drawai/public_stages.py src/drawai/pipeline.py src/drawai/stages/file_backed.py tests/v2/test_v2_public_stages.py tests/semantic_ppt/drawai_pipeline/test_public_stages.py tests/stages/test_file_backed_stage_specs.py
git commit -m "feat: route pipeline through v2 stages"
```

---

### Task 6: Connect V2 Packages To SVG Composition And Export

**Files:**
- Modify: `src/drawai/v2/stages.py`
- Modify: `src/drawai/v2/compat.py`
- Modify: `src/drawai/svg_generation_loop.py` only if it needs package-aware metadata
- Modify: `src/drawai/svg_to_ppt_check.py` only if export report needs v2 failed asset checks
- Test: `tests/v2/test_v2_public_stages.py`
- Test: `tests/semantic_ppt/drawai_pipeline/test_svg_generation_loop.py`
- Test: `tests/semantic_ppt/drawai_pipeline/test_svg_to_ppt_export_stage.py`

- [ ] **Step 1: Extend tests for compose/export failure gates**

Add to `tests/v2/test_v2_public_stages.py`:

```python
def test_export_refuses_failed_asset_by_default(tmp_path: Path) -> None:
    config = _config(tmp_path)
    summary = run_public_stage(config, "process_assets")
    root = Path(summary["output_dir"])
    package_path = root / "elements" / "E001" / "asset_package.json"
    payload = json.loads(package_path.read_text(encoding="utf-8"))
    payload["status"] = "failed"
    payload["failure"] = {"message": "forced failure"}
    package_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    export_summary = run_public_stage(config, "export")

    assert export_summary["status"] == "failed"
    assert export_summary["failed_stage"] == "export"
```

- [ ] **Step 2: Run the focused test and verify failure**

```bash
uv run pytest tests/v2/test_v2_public_stages.py::test_export_refuses_failed_asset_by_default -q
```

Expected: FAIL until export checks asset package statuses.

- [ ] **Step 3: Compose SVG from v2 package state**

In `src/drawai/v2/stages.py`, implement `compose_svg`:

- Read `ElementPlan` files and asset packages.
- Write compatibility `box_ir.json`, `element_analysis.json`, and `asset_manifest.json`.
- Call existing `run_svg_generation_loop()` with compatibility payloads.
- Copy validation report into `reports/svg_validation_report.json`.
- Update `drawai_package.json.compose_outputs`.

- [ ] **Step 4: Export with failed asset checks**

Before calling existing SVG-to-PPT export:

- Read all asset packages referenced by the run package.
- Fail if any required package status is `failed` or `unsupported` and `allow_partial_export` is false.
- Write `reports/svg_to_ppt_export_report.json` with omitted or failed asset details when failing.
- Update `drawai_package.json.export_outputs` when export succeeds.

- [ ] **Step 5: Run SVG/export tests**

```bash
uv run pytest tests/v2/test_v2_public_stages.py tests/semantic_ppt/drawai_pipeline/test_svg_generation_loop.py tests/semantic_ppt/drawai_pipeline/test_svg_to_ppt_export_stage.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/drawai/v2/stages.py src/drawai/v2/compat.py src/drawai/svg_generation_loop.py src/drawai/svg_to_ppt_check.py tests/v2/test_v2_public_stages.py
git commit -m "feat: compose and export from v2 packages"
```

---

### Task 7: Add V2 CLI Commands

**Files:**
- Modify: `src/drawai/cli.py`
- Modify: `src/drawai/local_cli.py`
- Test: `tests/semantic_ppt/drawai_pipeline/test_cli_pipeline.py`

- [ ] **Step 1: Write failing CLI tests**

Add tests to `tests/semantic_ppt/drawai_pipeline/test_cli_pipeline.py`:

```python
def test_cli_accepts_v2_public_stage(tmp_path: Path, capsys) -> None:
    config = _write_minimal_cli_config(tmp_path)

    code = drawai_cli.main(["run", "parse_elements", "--config", str(config)])

    captured = capsys.readouterr()
    assert code == 0
    assert "pipeline_summary:" in captured.out or "drawai.run_package.v1" in captured.out


def test_cli_asset_process_requires_v2_run(tmp_path: Path, capsys) -> None:
    legacy = tmp_path / "legacy"
    (legacy / "svg").mkdir(parents=True)
    (legacy / "svg" / "semantic.svg").write_text("<svg />\n", encoding="utf-8")

    code = drawai_cli.main(["asset", "process", str(legacy), "E001", "--processor", "crop"])

    captured = capsys.readouterr()
    assert code == 2
    assert "legacy_readonly" in captured.err
```

Use existing helper patterns in this test file for imports and config generation.

- [ ] **Step 2: Run CLI tests and verify failure**

```bash
uv run pytest tests/semantic_ppt/drawai_pipeline/test_cli_pipeline.py -q
```

Expected: FAIL until CLI supports v2 stages and asset commands.

- [ ] **Step 3: Implement `drawai run` v2 stage routing**

Modify `src/drawai/cli.py`:

- `drawai run <v2-stage> --config ...` calls `run_public_stage()`.
- Old public stage aliases still work and print summary.
- `drawai run image.png --local` remains delegated to `local_cli.run_image_cli()`.

- [ ] **Step 4: Implement `drawai asset` commands**

Add subcommands:

```text
drawai asset process <run-dir> <element-id> --processor <processor>
drawai asset activate <run-dir> <element-id> <result-id>
drawai compose <run-dir>
drawai export <run-dir>
```

Behavior:

- reject legacy roots with stderr containing `legacy_readonly`
- process invokes v2 processor by type
- activate updates asset package and run package
- compose/export run v2 stage helpers for that run root

- [ ] **Step 5: Run CLI tests**

```bash
uv run pytest tests/semantic_ppt/drawai_pipeline/test_cli_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/drawai/cli.py src/drawai/local_cli.py tests/semantic_ppt/drawai_pipeline/test_cli_pipeline.py
git commit -m "feat: add v2 cli commands"
```

---

### Task 8: Add Workbench Backend/API Package Operations And Legacy Read-Only Guard

**Files:**
- Create: `src/drawai/v2/workbench.py`
- Modify: `src/drawai/workbench/models.py`
- Modify: `src/drawai/workbench/runner.py`
- Modify: `src/drawai/workbench/api.py`
- Modify: `src/drawai/workbench/store.py` only if package helpers need store-backed JSON writes
- Test: `tests/workbench/test_store_api.py`

- [ ] **Step 1: Write failing Workbench API tests**

Add tests to `tests/workbench/test_store_api.py`:

```python
def test_api_exposes_v2_package_and_asset_package(tmp_path: Path) -> None:
    store = WorkbenchStore(tmp_path / "workspace")
    base_config = _base_config(tmp_path)
    source = tmp_path / "source.png"
    Image.new("RGB", (24, 24), "white").save(source)
    settings = _settings(tmp_path, base_config)
    runner = WorkbenchRunner(store, settings, stage_executor=_deterministic_stage_executor)
    app = create_app(settings, store=store, runner=runner)
    client = TestClient(app)
    batch = store.create_batch(
        name="v2 batch",
        input_mode="upload",
        max_concurrent_cases=1,
        auto_run_svg_after_analysis=False,
        config_path=base_config,
    )
    case = store.create_case(batch_id=batch.batch_id, name="source.png", source_image_path=source, config_path=base_config)
    _write_minimal_v2_package(Path(case.run_root), case.case_id)

    package_response = client.get(f"/api/cases/{case.case_id}/package")
    elements_response = client.get(f"/api/cases/{case.case_id}/elements")
    asset_response = client.get(f"/api/cases/{case.case_id}/elements/E001/asset-package")

    assert package_response.status_code == 200
    assert package_response.json()["package"]["schema"] == "drawai.run_package.v1"
    assert elements_response.json()["elements"][0]["element_id"] == "E001"
    assert asset_response.json()["asset_package"]["element_id"] == "E001"


def test_legacy_case_mutation_is_rejected_but_can_fork_from_source(tmp_path: Path) -> None:
    store = WorkbenchStore(tmp_path / "workspace")
    base_config = _base_config(tmp_path)
    source = tmp_path / "source.png"
    Image.new("RGB", (24, 24), "white").save(source)
    settings = _settings(tmp_path, base_config)
    app = create_app(settings, store=store, runner=WorkbenchRunner(store, settings, stage_executor=_deterministic_stage_executor))
    client = TestClient(app)
    batch = store.create_batch(
        name="legacy batch",
        input_mode="upload",
        max_concurrent_cases=1,
        auto_run_svg_after_analysis=False,
        config_path=base_config,
    )
    case = store.create_case(batch_id=batch.batch_id, name="source.png", source_image_path=source, config_path=base_config)
    root = Path(case.run_root)
    (root / "inputs").mkdir(parents=True)
    shutil.copy2(source, root / "inputs" / "figure.png")
    (root / "svg").mkdir()
    (root / "svg" / "semantic.svg").write_text("<svg />\n", encoding="utf-8")

    process_response = client.post(
        f"/api/cases/{case.case_id}/elements/E001/process",
        json={"processor": "crop"},
    )
    fork_response = client.post(f"/api/cases/{case.case_id}/fork-v2-from-source")

    assert process_response.status_code == 409
    assert process_response.json()["detail"] == "legacy_readonly_case"
    assert fork_response.status_code == 200
    assert fork_response.json()["case"]["case_id"] != case.case_id
```

Add `_write_minimal_v2_package()` test helper in the same test file using v2 package helpers.

- [ ] **Step 2: Run Workbench API tests and verify failure**

```bash
uv run pytest tests/workbench/test_store_api.py -q
```

Expected: FAIL because v2 endpoints do not exist.

- [ ] **Step 3: Add Workbench v2 helpers**

Create `src/drawai/v2/workbench.py` with:

- `case_package_payload(case)`
- `case_elements_payload(case)`
- `case_asset_package_payload(case, element_id)`
- `ensure_v2_mutation_allowed(case)`
- `fork_v2_case_from_source(store, runner, case)`

`ensure_v2_mutation_allowed()` raises a typed error or returns a value that `api.py` maps to HTTP 409 `legacy_readonly_case`.

- [ ] **Step 4: Update runner**

Modify `src/drawai/workbench/runner.py`:

- Replace `ANALYSIS_STAGES` with v2 stages through `refine_elements`.
- Replace `RerunStage` with v2 names while accepting old aliases from API.
- Register `run_package`, `fusion_trace`, `refine_trace`, and per-asset package artifacts.
- Keep batch status transitions equivalent: analysis ends at review unless auto-run is true.

- [ ] **Step 5: Add API endpoints**

Modify `src/drawai/workbench/api.py`:

- `GET /api/cases/{case_id}/package`
- `GET /api/cases/{case_id}/elements`
- `GET /api/cases/{case_id}/elements/{element_id}/asset-package`
- `POST /api/cases/{case_id}/elements/{element_id}/process`
- `POST /api/cases/{case_id}/elements/{element_id}/active-result`
- `POST /api/cases/{case_id}/compose`
- `POST /api/cases/{case_id}/export`
- `POST /api/cases/{case_id}/fork-v2-from-source`

All mutating endpoints call `ensure_v2_mutation_allowed()` first.

- [ ] **Step 6: Run Workbench tests**

```bash
uv run pytest tests/workbench/test_store_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/drawai/v2/workbench.py src/drawai/workbench/models.py src/drawai/workbench/runner.py src/drawai/workbench/api.py src/drawai/workbench/store.py tests/workbench/test_store_api.py
git commit -m "feat: add v2 workbench api"
```

---

### Task 9: Add Workbench Frontend Package UI

**Files:**
- Modify: `apps/workbench/src/types.ts`
- Modify: `apps/workbench/src/api.ts`
- Modify: `apps/workbench/src/App.tsx`
- Modify: `apps/workbench/src/styles.css`

- [ ] **Step 1: Add TypeScript API types**

Modify `apps/workbench/src/types.ts`:

- Add `RunCompatibilityMode = "v2" | "legacy_readonly" | "none"`.
- Add `V2ProcessingIntent`, `V2ElementPlan`, `V2AssetPackage`, `V2RunPackage`, `V2ProcessorRun`, `V2AssetResult`.
- Add `compatibility_mode?: RunCompatibilityMode` to `CaseRecord`.

- [ ] **Step 2: Add API wrappers**

Modify `apps/workbench/src/api.ts`:

- `getRunPackage(caseId)`
- `getElements(caseId)`
- `getAssetPackage(caseId, elementId)`
- `processV2Asset(caseId, elementId, processor, payload)`
- `setActiveAssetResult(caseId, elementId, resultId)`
- `composeV2Case(caseId)`
- `exportV2Case(caseId)`
- `forkV2FromSource(caseId)`

- [ ] **Step 3: Add v2 package state in App**

Modify `apps/workbench/src/App.tsx`:

- Add state for run package, elements, selected element, selected asset package, and package loading errors.
- When selecting a case, call `getRunPackage()`; if it returns 404 and the case has legacy artifacts, set mode to `legacy_readonly`.
- Keep current asset plan loading for old UI only when a v2 package is absent.

- [ ] **Step 4: Replace pipeline labels with v2 stages**

Update `PIPELINE_GROUPS` and `PIPELINE_STAGE_ORDER`:

```text
prepare
parse_elements
fuse_elements
refine_elements
plan_assets
process_assets
compose_svg
export
package_run
```

Old stage names can still render if returned by historical stage runs, but active pipeline controls should use v2 names.

- [ ] **Step 5: Add asset package drawer**

In `App.tsx`, add a component near existing asset editing components:

- `V2AssetPackagePanel`
- Shows element type, bbox, processing intent, package status, active result, processor run history, failure message.
- Buttons:
  - `Crop`
  - `No BG`
  - `Generate`
  - `Edit`
  - `Set active` for previous results
  - `Compose`
  - `Export`
- Disable chart rebuild with a clear reserved/unsupported state.

- [ ] **Step 6: Add legacy read-only UI**

For `legacy_readonly` cases:

- Keep existing artifact preview/download controls.
- Hide or disable processing, compose, export, and SVG edit controls.
- Show `Create v2 run from source` only when backend reports source availability.
- Call `forkV2FromSource()` when clicked.

- [ ] **Step 7: Add CSS**

Modify `apps/workbench/src/styles.css`:

- `.v2-package-panel`
- `.v2-element-list`
- `.v2-asset-drawer`
- `.v2-processor-history`
- `.legacy-readonly-banner`
- `.asset-status-failed`
- `.asset-status-unsupported`

Use the existing dense workbench visual language. Avoid nested cards.

- [ ] **Step 8: Build frontend**

Run:

```bash
cd apps/workbench && npm run build
```

Expected: PASS.

- [ ] **Step 9: Run backend Workbench tests**

```bash
uv run pytest tests/workbench/test_store_api.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add apps/workbench/src/types.ts apps/workbench/src/api.ts apps/workbench/src/App.tsx apps/workbench/src/styles.css
git commit -m "feat: add v2 workbench package ui"
```

---

### Task 10: End-To-End Verification, Docs, And Cleanup

**Files:**
- Modify: `src/drawai/README.md`
- Modify: `README.md`
- Modify: `README-en.md`
- Modify: `docs/zh-CN/runtime-options.md` if CLI/runtime flags changed
- Test: existing targeted suites

- [ ] **Step 1: Run Python focused suites**

```bash
uv run pytest tests/v2 tests/core tests/stages tests/domain tests/semantic_ppt/drawai_pipeline/test_public_stages.py tests/semantic_ppt/drawai_pipeline/test_cli_pipeline.py tests/workbench/test_assets.py tests/workbench/test_store_api.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

```bash
cd apps/workbench && npm run build
```

Expected: PASS.

- [ ] **Step 3: Run real smoke without external Agent**

Use a config with `v2.refine.enabled: false` and fixture OCR so the smoke can run without Codex:

```bash
uv run drawai run all --config /tmp/drawai-v2-smoke/config.yaml
```

Expected:

- command exits 0
- `drawai_package.json` exists
- `elements/*/asset_package.json` exists
- `svg/semantic.svg` exists when compose is enabled
- `reports/pipeline_summary.json` exists

- [ ] **Step 4: Run Workbench API smoke**

Start the backend in a temporary workspace:

```bash
DRAWAI_WORKBENCH_WORKSPACE=/tmp/drawai-v2-workbench uv run drawai-workbench-api --host 127.0.0.1 --port 8890
```

In another terminal, run a small request sequence:

```bash
curl -fsS http://127.0.0.1:8890/api/health
```

Expected: JSON response with `status` equal to `ok` or `degraded`, and no server traceback.

- [ ] **Step 5: Update docs**

Update docs only for user-visible behavior:

- `src/drawai/README.md`: package-authoritative v2 entrypoints.
- `README.md` and `README-en.md`: keep structural parity if top-level public behavior changed.
- `docs/zh-CN/runtime-options.md`: v2 config fields and legacy read-only behavior if needed.

- [ ] **Step 6: Run doc diff checks**

```bash
git diff --check
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/drawai/README.md README.md README-en.md docs/zh-CN/runtime-options.md
git commit -m "docs: describe v2 package workflow"
```

- [ ] **Step 8: Final verification before PR or handoff**

Run:

```bash
git status --short --branch
uv run pytest tests/v2 tests/core tests/stages tests/domain tests/semantic_ppt/drawai_pipeline/test_public_stages.py tests/semantic_ppt/drawai_pipeline/test_cli_pipeline.py tests/workbench/test_assets.py tests/workbench/test_store_api.py -q
cd apps/workbench && npm run build
```

Expected:

- git status shows only intended uncommitted files, or no uncommitted files after final commit
- Python tests pass
- frontend build passes

---

## Implementation Notes

- Keep top-level exception handling only at CLI/API/background job boundaries where structured status must be written.
- Do not add production mock paths or synthetic fallback data.
- Use provider-boundary test doubles only inside tests.
- Do not call old `box_ir.json`, `element_analysis.json`, or `asset_manifest.json` authoritative in new code.
- If an existing SVG/PPT function still needs those files, generate them from v2 packages through `drawai.v2.compat`.
- If old stage names remain accepted, expose them as aliases and include alias metadata in summaries.
- Legacy Workbench cases are view/download/fork-only.
- Any mutating API must call the legacy guard before reading mutable payloads.
- Chart rebuild is a reserved capability and must not appear as runnable.

## Self-Review Checklist

- Spec requirement: direct v2 main path replacement. Covered by Tasks 5, 6, 7, and 8.
- Spec requirement: legacy read-only display and fork. Covered by Tasks 8 and 9.
- Spec requirement: optional Agent refine default enabled. Covered by Tasks 3 and 5.
- Spec requirement: registry-based core enum and extension. Covered by Task 1.
- Spec requirement: priority/NMS fusion and rule hooks. Covered by Task 2.
- Spec requirement: run-level and asset-level packages. Covered by Tasks 1 and 4.
- Spec requirement: crop, crop_nobg, svg_self_draw, image_generate, image_edit processors. Covered by Task 4.
- Spec requirement: chart Agent reserved slot. Covered by Tasks 1, 4, and 9.
- Spec requirement: stage-sensitive failure handling. Covered by Tasks 4, 5, 6, and 8.
- Spec requirement: Core, CLI, API, and Workbench UI. Covered by Tasks 1 through 9.
