from __future__ import annotations

from drawai.domain.box_ir import build_raw_box_ir, build_svg_template_ir, merge_box_ir, validate_box_ir


def test_box_ir_domain_exports_core_document_operations():
    raw_box_ir = build_raw_box_ir(
        canvas=(100, 50),
        source_image="figure.png",
        normalized_long_edge=100,
        prompt_runs=[],
        raw_regions=[],
    )

    merged_box_ir, merge_trace = merge_box_ir(raw_box_ir)

    assert validate_box_ir(merged_box_ir) == []
    assert merge_trace["schema"] == "drawai.box_ir.merge_trace.v1"
    assert build_svg_template_ir(merged_box_ir)["schema"] == "drawai.box_ir.svg_template_ir.v1"
