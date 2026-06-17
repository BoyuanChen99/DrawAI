from __future__ import annotations

import json
from pathlib import Path

import pytest

from drawai.core import (
    ArtifactStore,
    DagRunner,
    ProviderRef,
    RunContext,
    StageFailure,
    StageResult,
    StageSpec,
)


def test_artifact_store_writes_json_with_hash_and_manifest(tmp_path: Path):
    store = ArtifactStore(tmp_path)

    ref = store.write_json(
        "box_ir",
        "box_ir/box_ir.json",
        {"schema": "drawai.box_ir.v1", "boxes": []},
        schema="drawai.box_ir.v1",
    )

    assert ref.artifact_id == "box_ir"
    assert ref.path == tmp_path / "box_ir" / "box_ir.json"
    assert ref.size_bytes > 0
    assert len(ref.sha256) == 64
    assert json.loads(ref.path.read_text(encoding="utf-8"))["schema"] == "drawai.box_ir.v1"
    assert store.manifest()["artifacts"]["box_ir"]["schema"] == "drawai.box_ir.v1"


def test_artifact_store_rejects_paths_outside_root(tmp_path: Path):
    store = ArtifactStore(tmp_path)

    with pytest.raises(ValueError, match="outside artifact root"):
        store.write_json("escape", "../escape.json", {})


def test_dag_runner_executes_stages_in_dependency_order(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    context = RunContext(config={"mode": "test"}, artifacts=store)
    calls: list[str] = []

    def run_prepare(ctx: RunContext) -> StageResult:
        calls.append("prepare")
        ref = ctx.artifacts.write_json("figure", "inputs/figure.json", {"ok": True})
        return StageResult.ok("prepare", artifacts={"figure": ref})

    def run_svg(ctx: RunContext) -> StageResult:
        calls.append("svg")
        ref = ctx.artifacts.write_json("semantic_svg", "svg/semantic.svg", {"ok": True})
        return StageResult.ok("svg", artifacts={"semantic_svg": ref})

    runner = DagRunner(
        [
            StageSpec(stage_id="svg", depends_on=("prepare",), outputs=("semantic_svg",), run=run_svg),
            StageSpec(stage_id="prepare", outputs=("figure",), run=run_prepare),
        ]
    )

    results = runner.run(context)

    assert calls == ["prepare", "svg"]
    assert [result.stage_id for result in results] == ["prepare", "svg"]


def test_dag_runner_invokes_hooks_around_validated_stages(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    context = RunContext(config={}, artifacts=store)
    events: list[tuple[str, str]] = []

    def run_prepare(ctx: RunContext) -> StageResult:
        ref = ctx.artifacts.write_json("figure", "inputs/figure.json", {"ok": True})
        return StageResult.ok("prepare", artifacts={"figure": ref})

    runner = DagRunner([StageSpec(stage_id="prepare", outputs=("figure",), run=run_prepare)])

    results = runner.run(
        context,
        before_stage=lambda stage: events.append(("before", stage.stage_id)),
        after_stage=lambda stage, result: events.append(("after", result.stage_id)),
    )

    assert [result.stage_id for result in results] == ["prepare"]
    assert events == [("before", "prepare"), ("after", "prepare")]


def test_dag_runner_raises_stage_failure_for_missing_output(tmp_path: Path):
    context = RunContext(config={}, artifacts=ArtifactStore(tmp_path))

    def run_stage(_ctx: RunContext) -> StageResult:
        return StageResult.ok("prepare")

    runner = DagRunner([StageSpec(stage_id="prepare", outputs=("figure",), run=run_stage)])

    with pytest.raises(StageFailure) as exc_info:
        runner.run(context)

    assert exc_info.value.stage_id == "prepare"
    assert exc_info.value.contract == "outputs"
    assert "figure" in str(exc_info.value)


def test_dag_runner_raises_stage_failure_for_missing_provider(tmp_path: Path):
    context = RunContext(config={}, artifacts=ArtifactStore(tmp_path))

    def run_stage(_ctx: RunContext) -> StageResult:
        return StageResult.ok("detect_text")

    runner = DagRunner(
        [
            StageSpec(
                stage_id="detect_text",
                providers=(ProviderRef(name="ocr", protocol="OcrDetector"),),
                run=run_stage,
            )
        ]
    )

    with pytest.raises(StageFailure) as exc_info:
        runner.run(context)

    assert exc_info.value.stage_id == "detect_text"
    assert exc_info.value.contract == "providers"
    assert "ocr" in str(exc_info.value)


def test_dag_runner_rejects_duplicate_stage_ids():
    def run_stage(_ctx: RunContext) -> StageResult:
        return StageResult.ok("prepare")

    with pytest.raises(ValueError, match="duplicate stage id"):
        DagRunner(
            [
                StageSpec(stage_id="prepare", run=run_stage),
                StageSpec(stage_id="prepare", run=run_stage),
            ]
        )
