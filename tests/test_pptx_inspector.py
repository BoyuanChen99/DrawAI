from pathlib import Path
from zipfile import ZipFile

from drawai.pptx_inspector import inspect_pptx_structure


def test_inspect_pptx_structure_counts_ppt_tags_with_attributes(tmp_path: Path):
    pptx = tmp_path / "attributed_tags.pptx"
    with ZipFile(pptx, "w") as zf:
        zf.writestr(
            "ppt/slides/slide1.xml",
            """<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree>
    <p:sp id="shape-1"><p:txBody><a:p><a:r><a:t xml:space="preserve">Hello</a:t></a:r></a:p></p:txBody></p:sp>
    <p:pic id="image-1"><p:nvPicPr/></p:pic>
    <p:cxnSp id="connector-1"/>
  </p:spTree></p:cSld>
</p:sld>""",
        )
        zf.writestr("ppt/media/image1.png", b"fake")

    report = inspect_pptx_structure(pptx)

    assert report["slide_count"] == 1
    assert report["media_count"] == 1
    assert report["svg_media_count"] == 0
    assert report["shape_tag_count"] == 1
    assert report["picture_tag_count"] == 1
    assert report["connector_tag_count"] == 1
    assert report["text_run_count"] == 1


def test_inspect_pptx_structure_does_not_treat_single_svg_picture_as_screenshot(tmp_path: Path):
    pptx = tmp_path / "svg_picture.pptx"
    with ZipFile(pptx, "w") as zf:
        zf.writestr(
            "ppt/slides/slide1.xml",
            """<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:pic id="image-1"/></p:spTree></p:cSld>
</p:sld>""",
        )
        zf.writestr("ppt/media/image1.svg", b"<svg/>")

    report = inspect_pptx_structure(pptx)

    assert report["picture_tag_count"] == 1
    assert report["svg_media_count"] == 1
    assert report["is_single_screenshot_like"] is False
