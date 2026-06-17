from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from drawai.explainer_app import load_case_data, render_report_fragment, write_static_report


def test_load_case_data_indexes_stage_outputs(tmp_path: Path) -> None:
    case_dir = _sample_case_dir(tmp_path)

    data = load_case_data(case_dir)

    assert data["case_name"] == "case_001_sample"
    assert data["sam3"]["prompt_count"] == 1
    assert data["sam3"]["total_regions"] == 1
    assert data["ocr"]["text_box_count"] == 1
    assert data["boxir"]["final_box_count"] == 1
    assert data["assets"]["asset_count"] == 1
    assert data["assets"]["display_asset_count"] == 1
    assert data["assets"]["asset_items"][0]["asset_id"] == "AF01"
    assert data["assets"]["asset_items"][0]["active_artifact"]["rel"] == "svg_to_ppt/assets/crops/AF01_nobg.png"
    assert data["pptx"]["status"] == "ok"
    assert data["ppt_optimization"]["status"] == "ok"
    assert data["ppt_optimization"]["change_count"] == 1
    assert "ppt_optimized" in data["stage_io"]["stages"]
    assert len(data["codex_rounds"]) == 1
    assert [attempt["label"] for attempt in data["svg_attempts"]] == [
        "template #1",
        "visual_review_text_style #1",
        "visual_review_text_style #2",
        "ir_refine #1",
    ]
    assert data["svg_attempts"][1]["status"] == "failed"
    assert data["svg_attempts"][1]["semantic_svg"]["rel"] == "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/semantic.svg"
    assert data["svg_attempts"][3]["rendered_png"]["rel"] == "svg/attempts/ir_refine/001/rendered.png"


def test_load_case_data_groups_svg_codex_runs_with_inputs_and_outputs(tmp_path: Path) -> None:
    case_dir = _sample_case_dir(tmp_path)

    data = load_case_data(case_dir)

    assert [run["label"] for run in data["svg_runs"]] == [
        "Run 1: template",
        "Run 2: visual_review_text_style",
        "Run 3: ir_refine",
    ]
    assert [run["attempt_count"] for run in data["svg_runs"]] == [1, 2, 1]

    template_attempt = data["svg_runs"][0]["attempts"][0]
    template_inputs = {item["role"]: item["artifact"]["rel"] for item in template_attempt["input_artifacts"]}
    assert template_attempt["instruction"]["rel"] == "svg/template_iterations/01_template/001/prompt.txt"
    assert template_attempt["instruction_preview"].startswith("Instruction:")
    assert template_inputs == {
        "figure_path": "svg/svg_generation_reference.png",
        "reference_image_path": "svg/template_reference.png",
    }
    assert template_attempt["output_artifacts"][0]["rel"] == "svg/template_iterations/01_template/001/semantic.svg"
    assert template_attempt["output_artifacts"][1]["rel"] == "svg/template_iterations/01_template/001/rendered.png"
    assert (
        template_attempt["session_log_artifact"]["rel"]
        == "svg/template_iterations/01_template/001/codex_session_log"
    )
    assert (
        template_attempt["session_log_manifest"]["rel"]
        == "svg/template_iterations/01_template/001/codex_session_log/manifest.json"
    )

    review_attempt = data["svg_runs"][1]["attempts"][1]
    review_inputs = {item["role"]: item["artifact"]["rel"] for item in review_attempt["input_artifacts"]}
    assert review_attempt["instruction"]["rel"] == "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/prompt.txt"
    assert review_inputs == {
        "figure_path": "svg/svg_generation_reference.png",
        "reference_image_path": "svg/template_rendered.png",
        "input_template_svg": "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/input_template.svg",
    }
    assert review_attempt["status"] == "ok"

    refine_attempt = data["svg_runs"][2]["attempts"][0]
    refine_inputs = {item["role"]: item["artifact"]["rel"] for item in refine_attempt["input_artifacts"]}
    assert refine_attempt["instruction"]["rel"] == "svg/attempts/ir_refine/001/prompt.txt"
    assert refine_inputs == {
        "figure_path": "svg/svg_generation_reference.png",
        "reference_image_path": "svg/template_rendered.png",
        "input_template_svg": "svg/attempts/ir_refine/001/input_template.svg",
    }


def test_render_and_write_static_report(tmp_path: Path) -> None:
    case_dir = _sample_case_dir(tmp_path)

    report_path = write_static_report(case_dir)
    html = report_path.read_text(encoding="utf-8")

    assert "DrawAI 图片转可编辑 SVG/PPTX 全流程解释" in html
    assert "../inputs/figure.png" in html
    assert "SAM3 语义 prompt 分割" in html

    fragment = render_report_fragment(load_case_data(case_dir), mode="static")
    assert "Run 1" in fragment
    assert "semantic.svg_to_ppt.pptx" in fragment
    assert "PPT 元素优化" in fragment
    assert "boxir-direct-ppt-optimized.pptx" in fragment
    assert "全部 assets" in fragment
    assert "AF01_nobg.png" in fragment
    assert "SVG/Codex 三个 run" in fragment
    assert "Run 1: template" in fragment
    assert "Run 2: visual_review_text_style" in fragment
    assert "Run 3: ir_refine" in fragment
    assert "Instruction" in fragment
    assert "svg-run-large-gallery" in fragment
    assert "template #1" in fragment
    assert "visual_review_text_style #1" in fragment
    assert "visual_review_text_style #2" in fragment
    assert "ir_refine #1" in fragment
    assert "../svg/svg_generation_reference.png" in fragment
    assert "../svg/template_reference.png" in fragment
    assert "../svg/template_rendered.png" in fragment
    assert "../svg/template_iterations/02_visual_review_loop/round_01_text_style/002/input_template.svg" in fragment
    assert "../svg/template_iterations/01_template/001/semantic.svg" in fragment
    assert "../svg/template_iterations/02_visual_review_loop/round_01_text_style/001/rendered.png" in fragment
    assert "../svg/attempts/ir_refine/001/semantic.svg" in fragment
    assert "../svg/template_iterations/01_template/001/codex_session_log" in fragment
    assert "manifest.json" in fragment


def _sample_case_dir(tmp_path: Path) -> Path:
    case_dir = tmp_path / "case_001_sample"
    for rel in (
        "inputs",
        "sam3/prompt_runs",
        "sam3/prompt_overlays",
        "box_ir",
        "ocr",
        "svg_to_ppt/assets/crops",
        "ppt_optimization/preview",
        "svg",
        "svg/template_iterations/01_template/001",
        "svg/template_iterations/01_template/001/codex_session_log/sessions/2026/06/08",
        "svg/template_iterations/02_visual_review_loop/round_01_text_style/001",
        "svg/template_iterations/02_visual_review_loop/round_01_text_style/002",
        "svg/attempts/ir_refine/001",
        "reports",
        "trace",
    ):
        (case_dir / rel).mkdir(parents=True, exist_ok=True)

    _write_png(case_dir / "inputs/original.png")
    _write_png(case_dir / "inputs/figure.png")
    _write_png(case_dir / "sam3/prompt_overlays/icon.png")
    _write_png(case_dir / "box_ir/semantic_overlay.png")
    _write_png(case_dir / "box_ir/semantic_overlay_legend.png")
    _write_png(case_dir / "box_ir/final_semantic_overlay.png")
    _write_png(case_dir / "box_ir/final_semantic_overlay_legend.png")
    _write_png(case_dir / "svg/asset_recovery_reference.png")
    _write_png(case_dir / "svg/asset_recovery_reference_legend.png")
    _write_png(case_dir / "svg/svg_generation_reference.png")
    _write_png(case_dir / "svg/svg_generation_reference_legend.png")
    _write_png(case_dir / "svg/template_reference.png")
    _write_png(case_dir / "svg/template_reference_legend.png")
    _write_png(case_dir / "svg/template_rendered.png")
    _write_png(case_dir / "svg/rendered.png")
    _write_png(case_dir / "svg/template_iterations/01_template/001/rendered.png")
    _write_png(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/rendered.png")
    _write_png(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/rendered.png")
    _write_png(case_dir / "svg/attempts/ir_refine/001/rendered.png")
    _write_png(case_dir / "svg_to_ppt/assets/crops/AF01.png")
    _write_png(case_dir / "svg_to_ppt/assets/crops/AF01_nobg.png")
    _write_png(case_dir / "ppt_optimization/preview/optimized-slide-01.png")
    _write_png(case_dir / "ppt_optimization/preview/before-after-slide-01.png")
    _write_png(case_dir / "ppt_optimization/preview/before-after-slide-02.png")

    _write_json(case_dir / "inputs/source_metadata.json", {"width": 20, "height": 12})
    prompt_payload = {
        "prompt_id": "icon",
        "request": {"prompts": [{"id": "icon", "text": "icon", "confidence_threshold": 0.3}]},
        "regions": [{"id": "region_001", "bbox": [1, 2, 3, 4]}],
        "raw_regions": [{"id": "icon_001", "bbox": [1, 2, 3, 4]}],
        "elapsed_ms": 1234.0,
    }
    _write_json(case_dir / "sam3/prompt_runs/icon.json", prompt_payload)
    _write_json(case_dir / "sam3/raw_regions.json", {"regions": prompt_payload["regions"]})
    _write_json(case_dir / "sam3/sam_boxes_by_prompt.json", {"icon": prompt_payload["regions"]})
    box_ir = {
        "schema": "drawai.box_ir.v1",
        "canvas": {"width": 20, "height": 12},
        "boxes": [{"id": "B001", "bbox": [1, 2, 3, 4]}],
        "ocr_text_boxes": [{"text": "hello", "bbox": [1, 2, 3, 4]}],
    }
    _write_json(case_dir / "box_ir/box_ir.raw.json", box_ir)
    _write_json(case_dir / "box_ir/box_ir.merged.json", box_ir)
    _write_json(case_dir / "box_ir/box_ir.json", box_ir)
    _write_json(case_dir / "box_ir/merge_trace.json", {"merged": []})
    _write_json(case_dir / "box_ir/box_merge_diagnostics.json", {"issues": []})
    _write_json(case_dir / "ocr/ocr_boxes.json", {"provider": "fixture_ocr", "ocr_text_boxes": box_ir["ocr_text_boxes"], "elapsed_ms": 25})
    _write_json(case_dir / "svg_to_ppt/assets/asset_decisions.json", {"decisions": [{"box_id": "B001"}]})
    _write_json(case_dir / "svg_to_ppt/assets/initial_asset_decisions.json", {"decisions": []})
    _write_json(case_dir / "svg_to_ppt/assets/svg_recoverable_assets.json", {"assets": []})
    _write_json(case_dir / "svg_to_ppt/assets/asset_policy_report.json", {"policies": []})
    _write_json(
        case_dir / "svg_to_ppt/assets/asset_manifest.json",
        {
            "assets": [
                {
                    "asset_id": "AF01",
                    "box_id": "B001",
                    "render_policy": "raster_png",
                    "source_svg_href": "../svg_to_ppt/assets/crops/AF01.png",
                    "svg_href": "../svg_to_ppt/assets/crops/AF01_nobg.png",
                    "active_variant": "without_background",
                    "width": 20,
                    "height": 12,
                    "policy_reason_codes": ["fixture_asset"],
                    "rmbg_elapsed_ms": 10,
                }
            ]
        },
    )
    (case_dir / "svg/semantic.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>\n", encoding="utf-8")
    (case_dir / "svg/template.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>\n", encoding="utf-8")
    for rel in (
        "svg/template_iterations/01_template/001/semantic.svg",
        "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/semantic.svg",
        "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/semantic.svg",
        "svg/attempts/ir_refine/001/semantic.svg",
    ):
        (case_dir / rel).write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>\n", encoding="utf-8")
    _write_svg_attempt_files(case_dir)
    _write_json(case_dir / "svg/svg_template_ir.json", {"groups": []})
    _write_json(case_dir / "reports/svg_validation_report.json", {"status": "ok", "issues": []})
    _write_json(case_dir / "reports/svg_to_ppt_export_report.json", {"status": "ok", "issues": []})
    _write_json(case_dir / "reports/stage_status.json", {"latest_stage": "completed"})
    _write_json(
        case_dir / "reports/stage_io_manifest.json",
        {
            "schema": "drawai.stage_io_manifest.v1",
            "stages": {
                "svg_generated": {
                    "inputs": {"box_ir": str(case_dir / "box_ir/box_ir.json")},
                    "outputs": {"semantic_svg": str(case_dir / "svg/semantic.svg")},
                    "inference_slots": ["svg_invoker"],
                }
            },
        },
    )
    _write_json(case_dir / "reports/pipeline_summary.json", {"status": "ok", "artifacts": {}})
    (case_dir / "svg_to_ppt/semantic.svg_to_ppt.pptx").write_bytes(b"pptx")
    (case_dir / "ppt_optimization/boxir-direct-ppt-optimized.pptx").write_bytes(b"optimized pptx")
    (case_dir / "ppt_optimization/boxir-direct-ppt-before-after.pptx").write_bytes(b"before after pptx")
    _write_json(
        case_dir / "ppt_optimization/direct-ppt-optimization-manifest.json",
        {"changes": ["directly adjust editable PPT elements"]},
    )
    trace_records = [
        {
            "connection_id": "local-codex-gateway",
            "model_name": "gpt-5-codex",
            "images": [{"image_path": str(case_dir / "svg/svg_generation_reference.png")}],
            "messages": [{"role": "user", "content": "make svg"}],
        },
        {"output_chars": 42, "output_excerpt": "<svg></svg>"},
    ]
    (case_dir / "trace/svg_generation_model.jsonl").write_text(
        "\n".join(json.dumps(record) for record in trace_records) + "\n",
        encoding="utf-8",
    )
    return case_dir


def _write_svg_attempt_files(case_dir: Path) -> None:
    template_attempt = {
        "phase": "template",
        "attempt": 1,
        "status": "ok",
        "issues": [],
        "validation_report": str(case_dir / "svg/template_iterations/01_template/001/validation_report.json"),
        "semantic_svg": str(case_dir / "svg/template_iterations/01_template/001/semantic.svg"),
        "rendered_png": str(case_dir / "svg/template_iterations/01_template/001/rendered.png"),
        "model_response": str(case_dir / "svg/template_iterations/01_template/001/model_response.txt"),
    }
    review_failed_attempt = {
        "phase": "visual_review_text_style",
        "attempt": 1,
        "status": "failed",
        "issues": [{"code": "blank_render"}],
        "validation_report": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/validation_report.json"),
        "semantic_svg": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/semantic.svg"),
        "rendered_png": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/rendered.png"),
        "model_response": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/model_response.txt"),
    }
    review_ok_attempt = {
        "phase": "visual_review_text_style",
        "attempt": 2,
        "status": "ok",
        "issues": [],
        "validation_report": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/validation_report.json"),
        "semantic_svg": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/semantic.svg"),
        "rendered_png": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/rendered.png"),
        "model_response": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/model_response.txt"),
    }
    _write_json(
        case_dir / "svg/template_iterations/iteration_manifest.json",
        {
            "schema": "drawai.svg_template_iterations.v1",
            "status": "ok",
            "phases": [
                {"phase": "template", "attempt_reports": [template_attempt]},
                {"phase": "visual_review_text_style", "attempt_reports": [review_failed_attempt, review_ok_attempt]},
            ],
        },
    )
    attempt_contexts = {
        "svg/template_iterations/01_template/001": {
            "phase": "template",
            "attempt": 1,
            "figure_path": str(case_dir / "svg/svg_generation_reference.png"),
            "reference_image_path": str(case_dir / "svg/template_reference.png"),
            "prompt_path": str(case_dir / "svg/template_iterations/01_template/001/prompt.txt"),
        },
        "svg/template_iterations/02_visual_review_loop/round_01_text_style/001": {
            "phase": "visual_review_text_style",
            "attempt": 1,
            "figure_path": str(case_dir / "svg/svg_generation_reference.png"),
            "reference_image_path": str(case_dir / "svg/template_rendered.png"),
            "input_template_svg": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/input_template.svg"),
            "prompt_path": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/prompt.txt"),
        },
        "svg/template_iterations/02_visual_review_loop/round_01_text_style/002": {
            "phase": "visual_review_text_style",
            "attempt": 2,
            "figure_path": str(case_dir / "svg/svg_generation_reference.png"),
            "reference_image_path": str(case_dir / "svg/template_rendered.png"),
            "input_template_svg": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/input_template.svg"),
            "prompt_path": str(case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/prompt.txt"),
        },
        "svg/attempts/ir_refine/001": {
            "phase": "ir_refine",
            "attempt": 1,
            "figure_path": str(case_dir / "svg/svg_generation_reference.png"),
            "reference_image_path": str(case_dir / "svg/template_rendered.png"),
            "input_template_svg": str(case_dir / "svg/attempts/ir_refine/001/input_template.svg"),
            "prompt_path": str(case_dir / "svg/attempts/ir_refine/001/prompt.txt"),
        },
    }
    for rel, context in attempt_contexts.items():
        attempt_dir = case_dir / rel
        _write_json(attempt_dir / "request_context.json", context)
        (attempt_dir / "prompt.txt").write_text(
            f"Instruction:\nGenerate the {context['phase']} SVG attempt {context['attempt']} from the supplied DrawAI inputs.\n",
            encoding="utf-8",
        )
        if "input_template_svg" in context:
            Path(context["input_template_svg"]).write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>\n", encoding="utf-8")

    ir_refine_dir = case_dir / "svg/attempts/ir_refine/001"
    _write_json(ir_refine_dir / "validation_report.json", {"status": "ok", "issues": []})
    for path in (
        case_dir / "svg/template_iterations/01_template/001/validation_report.json",
        case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/validation_report.json",
        case_dir / "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/validation_report.json",
    ):
        status = "failed" if "/001/" in str(path) and "round_01_text_style" in str(path) else "ok"
        issues = [{"code": "blank_render"}] if status == "failed" else []
        _write_json(path, {"status": status, "issues": issues})
    for rel in (
        "svg/template_iterations/01_template/001/model_response.txt",
        "svg/template_iterations/02_visual_review_loop/round_01_text_style/001/model_response.txt",
        "svg/template_iterations/02_visual_review_loop/round_01_text_style/002/model_response.txt",
        "svg/attempts/ir_refine/001/model_response.txt",
    ):
        (case_dir / rel).write_text("<svg></svg>\n", encoding="utf-8")
    session_log = (
        case_dir
        / "svg/template_iterations/01_template/001/codex_session_log/sessions/2026/06/08/rollout-test.jsonl"
    )
    session_log.write_text(
        '{"event":"tool"}\n',
        encoding="utf-8",
    )
    _write_json(
        case_dir / "svg/template_iterations/01_template/001/codex_session_log/manifest.json",
        {
            "schema": "drawai.codex_session_log_archive.v1",
            "copied": ["sessions"],
            "missing": ["log"],
        },
    )


def _write_png(path: Path) -> None:
    Image.new("RGB", (20, 12), "white").save(path)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
