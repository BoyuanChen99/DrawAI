import json

from drawai.domain.box_ir import build_svg_template_ir


def test_build_svg_template_ir_keeps_only_content_boxes_and_arrows():
    box_ir = {
        "canvas": {"width": 100.2, "height": 80.8},
        "boxes": [
            {"id": "B001", "type": "content_box", "bbox": [1.1, 2.2, 30.6, 40.7], "score": 0.9},
            {"id": "B002", "type": "arrow", "bbox": [45, 10, 80, 15], "source_box_ids": ["R001"]},
            {"id": "B003", "type": "icon", "bbox": [5, 50, 20, 65]},
            {"id": "B004", "type": "picture", "bbox": [25, 50, 40, 65]},
        ],
        "ocr_text_boxes": [{"id": "T001", "bbox": [10, 10, 20, 20], "text": "Do not leak"}],
    }

    template_ir = build_svg_template_ir(box_ir)
    serialized = json.dumps(template_ir, ensure_ascii=False)

    assert template_ir["schema"] == "drawai.box_ir.svg_template_ir.v1"
    assert template_ir["canvas"] == {"width": 100, "height": 81}
    assert template_ir["box_count"] == 2
    assert template_ir["boxes"] == [
        {"id": "B001", "type": "content_box", "bbox": [1, 2, 31, 41]},
        {"id": "B002", "type": "arrow", "bbox": [45, 10, 80, 15]},
    ]
    assert "B003" not in serialized
    assert "B004" not in serialized
    assert "T001" not in serialized
    assert "Do not leak" not in serialized
    assert "score" not in serialized
    assert "source_box_ids" not in serialized
