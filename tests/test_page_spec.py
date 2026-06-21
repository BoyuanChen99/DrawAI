from __future__ import annotations

from drawai.page_spec import element_plans_from_page_spec


def test_element_plans_from_page_spec_normalizes_asset_ref_elements() -> None:
    plans = element_plans_from_page_spec(
        {
            "schema": "drawai.page_spec.v1",
            "page_id": "page-1",
            "elements": [
                {
                    "id": "E001",
                    "kind": "image",
                    "role": "picture",
                    "box_px": [2, 3, 10, 12],
                    "z_index": 5,
                    "confidence": 0.92,
                    "build": {
                        "mode": "asset_ref",
                        "processing_type": "crop",
                        "parameters": {"padding_px": 2},
                    },
                    "source_refs": [{"kind": "candidate", "id": "sam:B001"}],
                }
            ],
        }
    )

    assert len(plans) == 1
    assert plans[0].element_type == "picture"
    assert plans[0].confidence == "high"
    assert plans[0].processing_intent.processing_type == "crop"
    assert plans[0].processing_intent.parameters == {"padding_px": 2}
    assert plans[0].source_candidate_ids == ("sam:B001",)
