from __future__ import annotations

from pathlib import Path

from drawai.workflow.templates import (
    copy_builtin_template,
    default_drawai_workflow_template,
    user_workflow_template_path,
    workflow_templates_dir,
)
from drawai.workflow.validation import validate_workflow_template


def test_default_drawai_workflow_template_validates() -> None:
    template = default_drawai_workflow_template()

    result = validate_workflow_template(template)

    assert result.ok
    assert result.errors == ()


def test_default_template_contains_current_v2_nodes() -> None:
    template = default_drawai_workflow_template()
    node_ids = {node.node_id for node in template.nodes}

    assert {
        "input",
        "sam_parser",
        "ocr_parser",
        "fusion",
        "run0_agent",
        "asset_planner",
        "asset_processors",
        "svg_agent",
        "svg_to_ppt",
        "output",
    }.issubset(node_ids)


def test_run0_and_svg_are_agent_node_presets() -> None:
    template = default_drawai_workflow_template()
    nodes = {node.node_id: node for node in template.nodes}

    assert nodes["run0_agent"].node_type == "agent"
    assert nodes["svg_agent"].node_type == "agent"
    assert nodes["run0_agent"].config["provider_id"] == "codex_sdk"
    assert nodes["svg_agent"].config["provider_id"] == "codex_sdk"
    assert nodes["run0_agent"].config["preset_id"] == "run0_element_refine"
    assert nodes["svg_agent"].config["preset_id"] == "svg_generation"


def test_default_template_routes_svg_and_pptx_into_output() -> None:
    template = default_drawai_workflow_template()
    output_edges = {
        (edge.source_node_id, edge.source_port_id, edge.target_node_id, edge.target_port_id)
        for edge in template.edges
        if edge.target_node_id == "output"
    }

    assert ("svg_agent", "semantic_svg", "output", "deliverables") in output_edges
    assert ("svg_to_ppt", "pptx", "output", "deliverables") in output_edges


def test_workflow_template_paths_are_under_ignored_workbench_dir(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    assert workflow_templates_dir(workspace) == workspace / "workflows"
    assert user_workflow_template_path(workspace, "custom") == workspace / "workflows" / "custom.json"


def test_copy_builtin_template_returns_editable_custom_template() -> None:
    copied = copy_builtin_template("default_drawai_dag", name="My DAG")

    assert copied.template_id.startswith("custom_")
    assert copied.name == "My DAG"
    assert copied.defaults["source_template_id"] == "default_drawai_dag"
    assert validate_workflow_template(copied).ok
