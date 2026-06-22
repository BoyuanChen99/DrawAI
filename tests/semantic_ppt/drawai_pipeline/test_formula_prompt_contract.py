from drawai import pipeline


def test_staged_pipeline_formula_prompt_requires_formula_group_example() -> None:
    prompt = pipeline._model_text_contract(use_ocr_hints=True) + pipeline._drawai_svg_profile_prompt()

    assert "A formula includes standalone mathematical variables or symbols with subscripts, superscripts, accents, Greek letters, operators, or relation signs." in prompt
    assert "Do not flatten formula structure into plain text such as alphai, xi2, yhat, or theta0." in prompt
    assert "Formula SVG example" in prompt
    assert "label-formula-example" in prompt
    assert "\\alpha_i^2+\\beta_i=c_i" in prompt
    assert 'baseline-shift="sub"' in prompt
    assert "label-formula-delta-ae" not in prompt
    assert "\\Delta^\\phi_{AE}" not in prompt
