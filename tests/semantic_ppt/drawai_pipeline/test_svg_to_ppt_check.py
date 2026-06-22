from pathlib import Path

from drawai.svg_to_ppt_check import check_svg_to_ppt_compatibility


OK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><rect width="100" height="80" fill="white"/></svg>'


def test_svg_to_ppt_check_classifies_svg_profile_issue(tmp_path: Path):
    svg = tmp_path / "bad.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><image href="https://example.com/a.png"/></svg>', encoding="utf-8")
    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=False)
    assert report["status"] == "failed"
    assert report["failure_class"] == "svg_profile_issue"


def test_svg_to_ppt_check_uses_scientific_profile_before_compile(tmp_path: Path):
    svg = tmp_path / "bad_filter.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80">'
        '<defs><filter id="shadow"><feDropShadow dx="1" dy="1"/></filter></defs>'
        '<rect width="20" height="20" filter="url(#shadow)"/></svg>',
        encoding="utf-8",
    )
    called = False

    def compiler_must_not_run(*args, **kwargs):
        nonlocal called
        called = True

    report = check_svg_to_ppt_compatibility(
        svg,
        output_dir=tmp_path,
        export_pptx=True,
        compiler=compiler_must_not_run,
    )

    assert report["status"] == "failed"
    assert report["failure_class"] == "svg_profile_issue"
    assert called is False
    assert report["scientific_svg_profile"]["compliant"] is False
    assert any(issue["code"] == "blocked_filter" for issue in report["issues"])


def test_svg_to_ppt_check_classifies_compiler_failure(tmp_path: Path):
    svg = tmp_path / "ok.svg"
    svg.write_text(OK_SVG, encoding="utf-8")

    def failing_compiler(*args, **kwargs):
        raise RuntimeError("compiler exploded")

    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=True, compiler=failing_compiler)
    assert report["status"] == "failed"
    assert report["failure_class"] == "compiler_tool_issue"


def test_svg_to_ppt_check_skips_compiler_when_export_pptx_disabled(tmp_path: Path):
    svg = tmp_path / "ok.svg"
    svg.write_text(OK_SVG, encoding="utf-8")
    called = False

    def compiler_must_not_run(*args, **kwargs):
        nonlocal called
        called = True

    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=False, compiler=compiler_must_not_run)
    assert report["status"] == "ok"
    assert report["export_pptx"] is False
    assert called is False


def test_svg_to_ppt_check_returns_ok_when_fake_compiler_writes_pptx(tmp_path: Path):
    svg = tmp_path / "ok.svg"
    svg.write_text(OK_SVG, encoding="utf-8")

    def successful_compiler(svg_path: Path, output_pptx: Path):
        assert svg_path == svg
        output_pptx.write_bytes(b"pptx")

    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=True, compiler=successful_compiler)
    assert report["status"] == "ok"
    assert report["failure_class"] is None
    assert Path(report["pptx_path"]).exists()


def test_svg_to_ppt_check_rejects_single_picture_native_output(tmp_path: Path):
    svg = tmp_path / "ok.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><text x="5" y="20">Planner</text></svg>',
        encoding="utf-8",
    )

    def screenshot_like_compiler(svg_path: Path, output_pptx: Path):
        assert svg_path == svg
        output_pptx.write_bytes(b"pptx")
        return {
            "backend": "drawai_native_shapes",
            "editable_surface": "native_shapes",
            "pptx_structure": {
                "slide_count": 1,
                "media_count": 2,
                "picture_tag_count": 1,
                "shape_tag_count": 0,
                "text_run_count": 0,
                "is_single_screenshot_like": True,
            },
        }

    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=True, compiler=screenshot_like_compiler)

    assert report["status"] == "failed"
    assert any(issue["code"] == "drawai_conversion_report_screenshot_like" for issue in report["issues"])


def test_svg_to_ppt_check_rejects_drawai_conversion_report_blockers_from_compiler(tmp_path: Path):
    svg = tmp_path / "ok.svg"
    svg.write_text(OK_SVG, encoding="utf-8")

    def compiler_with_blockers(svg_path: Path, output_pptx: Path):
        output_pptx.write_bytes(b"pptx")
        return {
            "backend": "drawai_native_shapes",
            "external_report": {
                "status": "ok",
                "svg_analysis": {"blockers": [{"code": "unsupported_filter"}]},
                "issues": [],
                "pptx_structure": {"is_single_screenshot_like": False},
            },
        }

    report = check_svg_to_ppt_compatibility(
        svg,
        output_dir=tmp_path,
        export_pptx=True,
        compiler=compiler_with_blockers,
    )

    assert report["status"] == "failed"
    assert report["failure_class"] == "svg_profile_issue"
    assert any(issue["code"] == "drawai_conversion_report_blockers" for issue in report["issues"])


def test_svg_to_ppt_check_classifies_missing_pptx_as_compiler_tool_issue(tmp_path: Path):
    svg = tmp_path / "ok.svg"
    svg.write_text(OK_SVG, encoding="utf-8")

    def silent_compiler(*args, **kwargs):
        return None

    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=True, compiler=silent_compiler)
    assert report["status"] == "failed"
    assert report["failure_class"] == "compiler_tool_issue"
    assert any(issue["code"] == "pptx_missing" for issue in report["issues"])


def test_svg_to_ppt_check_classifies_missing_dependency_as_environment_issue(tmp_path: Path):
    svg = tmp_path / "ok.svg"
    svg.write_text(OK_SVG, encoding="utf-8")

    def missing_dependency_compiler(*args, **kwargs):
        raise FileNotFoundError("native converter not found")

    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=True, compiler=missing_dependency_compiler)
    assert report["status"] == "failed"
    assert report["failure_class"] == "environment_issue"


def test_svg_to_ppt_check_rejects_local_asset_href_not_in_manifest(tmp_path: Path):
    asset = tmp_path / "asset.png"
    asset.write_bytes(b"fake")
    svg = tmp_path / "bad_asset.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><image href="asset.png" width="10" height="10"/></svg>',
        encoding="utf-8",
    )
    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=False, asset_manifest={"assets": []})
    assert report["status"] == "failed"
    assert report["failure_class"] == "svg_profile_issue"
    assert any(issue["code"] == "asset_href_not_in_manifest" for issue in report["issues"])


def test_svg_to_ppt_check_rejects_local_asset_href_when_manifest_missing(tmp_path: Path):
    asset = tmp_path / "asset.png"
    asset.write_bytes(b"fake")
    svg = tmp_path / "bad_asset.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><image href="asset.png" width="10" height="10"/></svg>',
        encoding="utf-8",
    )
    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=False)
    assert report["status"] == "failed"
    assert report["failure_class"] == "svg_profile_issue"
    assert any(issue["code"] == "asset_href_not_in_manifest" for issue in report["issues"])


def test_svg_to_ppt_check_accepts_manifest_approved_local_asset(tmp_path: Path):
    asset = tmp_path / "asset.png"
    asset.write_bytes(b"fake")
    svg = tmp_path / "ok_asset.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><image href="asset.png" width="10" height="10"/></svg>',
        encoding="utf-8",
    )
    report = check_svg_to_ppt_compatibility(
        svg,
        output_dir=tmp_path,
        export_pptx=False,
        asset_manifest={"assets": [{"path": str(asset)}]},
    )
    assert report["status"] == "ok"
    assert report["failure_class"] is None


def test_svg_to_ppt_check_accepts_svg_href_manifest_asset(tmp_path: Path):
    svg_dir = tmp_path / "out" / "svg"
    asset = tmp_path / "out" / "assets" / "crops" / "AF01.png"
    svg_dir.mkdir(parents=True)
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"fake")
    svg = svg_dir / "ok_asset.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80">'
        '<image href="../assets/crops/AF01.png" width="10" height="10"/></svg>',
        encoding="utf-8",
    )
    report = check_svg_to_ppt_compatibility(
        svg,
        output_dir=tmp_path,
        export_pptx=False,
        asset_manifest={"assets": [{"asset_id": "AF01", "svg_href": "../assets/crops/AF01.png"}]},
    )
    assert report["status"] == "ok"
    assert report["failure_class"] is None


def test_svg_to_ppt_check_accepts_insertable_component_asset(tmp_path: Path):
    svg_dir = tmp_path / "out" / "svg"
    asset = tmp_path / "out" / "svg_to_ppt" / "assets" / "crops" / "AF13_C01_nobg.png"
    svg_dir.mkdir(parents=True)
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"fake")
    svg = svg_dir / "ok_component_asset.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80">'
        '<image href="../svg_to_ppt/assets/crops/AF13_C01_nobg.png" width="10" height="10"/></svg>',
        encoding="utf-8",
    )

    report = check_svg_to_ppt_compatibility(
        svg,
        output_dir=tmp_path / "out",
        export_pptx=False,
        asset_manifest={
            "assets": [
                {
                    "asset_id": "AF13",
                    "insertable": False,
                    "insertable_components": [
                        {
                            "component_id": "AF13_C01",
                            "svg_href": "../svg_to_ppt/assets/crops/AF13_C01_nobg.png",
                            "bbox": [10, 10, 20, 20],
                        }
                    ],
                }
            ]
        },
    )

    assert report["status"] == "ok"
    assert report["failure_class"] is None


def test_svg_to_ppt_check_rejects_conversion_that_drops_manifest_images(tmp_path: Path):
    svg_dir = tmp_path / "out" / "svg"
    asset = tmp_path / "out" / "svg_to_ppt" / "assets" / "crops" / "AF01.png"
    svg_dir.mkdir(parents=True)
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"fake")
    svg = svg_dir / "semantic.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80">'
        '<image href="../svg_to_ppt/assets/crops/AF01.png" width="10" height="10"/></svg>',
        encoding="utf-8",
    )

    def compiler_drops_images(svg_path: Path, output_pptx: Path):
        output_pptx.write_bytes(b"pptx")
        return {
            "backend": "drawai_native_shapes",
            "external_report": {
                "status": "ok",
                "source_profile": {"feature_counts": {"image": 1}},
                "svg_analysis": {"blockers": [], "element_counts": {"image": 1}},
                "issues": [],
                "pptx_structure": {
                    "is_single_screenshot_like": False,
                    "media_count": 0,
                    "picture_tag_count": 0,
                },
            },
        }

    report = check_svg_to_ppt_compatibility(
        svg,
        output_dir=tmp_path / "out",
        export_pptx=True,
        compiler=compiler_drops_images,
        asset_manifest={"assets": [{"asset_id": "AF01", "svg_href": "../svg_to_ppt/assets/crops/AF01.png"}]},
    )

    assert report["status"] == "failed"
    assert report["failure_class"] == "compiler_tool_issue"
    assert any(issue["code"] == "drawai_conversion_report_missing_images" for issue in report["issues"])


def test_svg_to_ppt_check_rejects_top_level_report_that_drops_svg_images(tmp_path: Path):
    svg_dir = tmp_path / "out" / "svg"
    asset = tmp_path / "out" / "svg_to_ppt" / "assets" / "crops" / "AF01.png"
    svg_dir.mkdir(parents=True)
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"fake")
    svg = svg_dir / "semantic.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80">'
        '<image href="../svg_to_ppt/assets/crops/AF01.png" width="10" height="10"/></svg>',
        encoding="utf-8",
    )

    def compiler_drops_images(svg_path: Path, output_pptx: Path):
        output_pptx.write_bytes(b"pptx")
        return {
            "status": "ok",
            "backend": "drawai_native_shapes",
            "source_svg": str(svg_path),
            "pptx_structure": {
                "is_single_screenshot_like": False,
                "media_count": 0,
                "picture_tag_count": 0,
                "text_run_count": 0,
            },
        }

    report = check_svg_to_ppt_compatibility(
        svg,
        output_dir=tmp_path / "out",
        export_pptx=True,
        compiler=compiler_drops_images,
        asset_manifest={"assets": [{"asset_id": "AF01", "svg_href": "../svg_to_ppt/assets/crops/AF01.png"}]},
    )

    assert report["status"] == "failed"
    assert report["failure_class"] == "compiler_tool_issue"
    assert any(issue["code"] == "drawai_conversion_report_missing_images" for issue in report["issues"])


def test_svg_to_ppt_check_rejects_conversion_that_drops_native_text(tmp_path: Path):
    svg = tmp_path / "text_heavy.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80">'
        '<text x="10" y="20">A</text><text x="20" y="30">B</text>'
        '<text x="30" y="40">C</text><text x="40" y="50">D</text>'
        '<text x="50" y="60">E</text></svg>',
        encoding="utf-8",
    )

    def compiler_drops_text(svg_path: Path, output_pptx: Path):
        output_pptx.write_bytes(b"pptx")
        return {
            "backend": "drawai_native_shapes",
            "external_report": {
                "status": "ok",
                "source_profile": {"feature_counts": {"text": 5}},
                "canonicalized_profile": {"feature_counts": {"text": 5}},
                "svg_analysis": {"blockers": [], "element_counts": {"text": 5}},
                "issues": [],
                "pptx_structure": {
                    "is_single_screenshot_like": False,
                    "text_run_count": 1,
                },
            },
        }

    report = check_svg_to_ppt_compatibility(
        svg,
        output_dir=tmp_path,
        export_pptx=True,
        compiler=compiler_drops_text,
    )

    assert report["status"] == "failed"
    assert report["failure_class"] == "compiler_tool_issue"
    assert any(issue["code"] == "drawai_conversion_report_text_loss" for issue in report["issues"])


def test_svg_to_ppt_check_uses_prepared_svg_text_count_after_formula_strip(tmp_path: Path):
    svg = tmp_path / "formula_heavy.svg"
    prepared_svg = tmp_path / "formula_heavy.prepared.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80">'
        '<text x="10" y="20">A</text><text x="20" y="30">B</text>'
        '<text x="30" y="40">C</text><text x="40" y="50">D</text>'
        '<text x="50" y="60">Caption</text><text x="60" y="70">Axis</text></svg>',
        encoding="utf-8",
    )
    prepared_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80">'
        '<text x="50" y="60">Caption</text><text x="60" y="70">Axis</text></svg>',
        encoding="utf-8",
    )

    def compiler_with_formula_stripped_svg(svg_path: Path, output_pptx: Path):
        output_pptx.write_bytes(b"pptx")
        return {
            "backend": "drawai_native_shapes",
            "prepared_svg": str(prepared_svg),
            "source_svg": str(svg_path),
            "formula_export": {"status": "ok", "count": 4, "converted": 4, "fallback": 0},
            "pptx_structure": {
                "is_single_screenshot_like": False,
                "text_run_count": 2,
            },
        }

    report = check_svg_to_ppt_compatibility(
        svg,
        output_dir=tmp_path,
        export_pptx=True,
        compiler=compiler_with_formula_stripped_svg,
    )

    assert report["status"] == "ok"
    assert report["prepared_svg"] == str(prepared_svg)


def test_svg_to_ppt_check_rejects_doctype_script_af_placeholder_and_missing_viewbox(tmp_path: Path):
    cases = {
        "doctype.svg": '<!DOCTYPE svg [<!ENTITY local SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"></svg>',
        "script.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><script>alert(1)</script></svg>',
        "placeholder.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><text>AF01</text></svg>',
        "missing_viewbox.svg": '<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="80"/></svg>',
    }

    for filename, svg_text in cases.items():
        svg = tmp_path / filename
        svg.write_text(svg_text, encoding="utf-8")
        report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=False)
        assert report["status"] == "failed"
        assert report["failure_class"] == "svg_profile_issue"


def test_svg_to_ppt_check_removes_stale_pptx_on_profile_failure(tmp_path: Path):
    svg = tmp_path / "bad.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><image href="https://example.com/a.png"/></svg>', encoding="utf-8")
    stale_pptx = tmp_path / "svg_to_ppt" / "bad.svg_to_ppt.pptx"
    stale_pptx.parent.mkdir(parents=True)
    stale_pptx.write_bytes(b"stale")

    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=True)

    assert report["status"] == "failed"
    assert report["pptx_path"] == str(stale_pptx)
    assert not stale_pptx.exists()


def test_svg_to_ppt_check_removes_stale_pptx_when_export_pptx_disabled(tmp_path: Path):
    svg = tmp_path / "ok.svg"
    svg.write_text(OK_SVG, encoding="utf-8")
    stale_pptx = tmp_path / "svg_to_ppt" / "ok.svg_to_ppt.pptx"
    stale_pptx.parent.mkdir(parents=True)
    stale_pptx.write_bytes(b"stale")

    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=False)

    assert report["status"] == "ok"
    assert report["pptx_path"] == str(stale_pptx)
    assert not stale_pptx.exists()


def test_svg_to_ppt_check_updates_prepared_svg_from_compiler_report(tmp_path: Path):
    svg = tmp_path / "ok.svg"
    prepared_svg = tmp_path / "ok.prepared.svg"
    svg.write_text(OK_SVG, encoding="utf-8")
    prepared_svg.write_text(OK_SVG, encoding="utf-8")

    def compiler_with_report(svg_path: Path, output_pptx: Path):
        output_pptx.write_bytes(b"pptx")
        return {"prepared_svg": str(prepared_svg), "source_svg": str(svg_path)}

    report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=True, compiler=compiler_with_report)

    assert report["status"] == "ok"
    assert report["prepared_svg"] == str(prepared_svg)


def test_svg_to_ppt_check_rejects_missing_svg_namespace_and_root(tmp_path: Path):
    cases = {
        "missing_namespace.svg": '<svg viewBox="0 0 100 80"><rect width="100" height="80"/></svg>',
        "not_svg.svg": '<html xmlns="http://www.w3.org/1999/xhtml"></html>',
    }

    for filename, svg_text in cases.items():
        svg = tmp_path / filename
        svg.write_text(svg_text, encoding="utf-8")
        report = check_svg_to_ppt_compatibility(svg, output_dir=tmp_path, export_pptx=False)
        assert report["status"] == "failed"
        assert report["failure_class"] == "svg_profile_issue"
