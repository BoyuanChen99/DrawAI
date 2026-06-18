from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from .schema import WorkflowEdge, WorkflowNode, WorkflowPort, WorkflowTemplate

DEFAULT_WORKFLOW_TEMPLATE_ID = "default_drawai_dag"


def default_drawai_workflow_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        template_id=DEFAULT_WORKFLOW_TEMPLATE_ID,
        name="Default DrawAI DAG",
        description="Built-in workflow that mirrors the current DrawAI v2 path.",
        nodes=(
            WorkflowNode(
                node_id="input",
                node_type="input",
                title="Input",
                outputs=(
                    _output("image", "Image", ("image",), formats=("drawai.image.v1",)),
                ),
                position={"x": 0, "y": 160},
            ),
            WorkflowNode(
                node_id="sam_parser",
                node_type="parser",
                title="SAM Parser",
                inputs=(_input("image", "Image", ("image",)),),
                outputs=(
                    _output(
                        "candidates",
                        "Candidates",
                        ("element_candidates",),
                        formats=("drawai.element_candidates.v1",),
                    ),
                ),
                config={"parser_id": "sam3_structure_parser", "resource": "sam3"},
                position={"x": 240, "y": 80},
            ),
            WorkflowNode(
                node_id="ocr_parser",
                node_type="parser",
                title="OCR Parser",
                inputs=(_input("image", "Image", ("image",)),),
                outputs=(
                    _output(
                        "candidates",
                        "Candidates",
                        ("element_candidates",),
                        formats=("drawai.element_candidates.v1",),
                    ),
                ),
                config={"parser_id": "ocr_text_parser", "resource": "ocr"},
                position={"x": 240, "y": 240},
            ),
            WorkflowNode(
                node_id="fusion",
                node_type="fusion",
                title="Fusion",
                inputs=(
                    _input(
                        "candidates",
                        "Candidates",
                        ("element_candidates",),
                        cardinality="many",
                    ),
                ),
                outputs=(
                    _output(
                        "elements",
                        "Element Plans",
                        ("element_plans",),
                        formats=("drawai.element_plans.v1",),
                    ),
                ),
                config={"fusion_id": "priority_nms"},
                position={"x": 500, "y": 160},
            ),
            WorkflowNode(
                node_id="run0_agent",
                node_type="agent",
                title="Run0 Agent",
                inputs=(_input("elements", "Element Plans", ("element_plans",)),),
                outputs=(
                    _output(
                        "elements",
                        "Element Plans",
                        ("element_plans",),
                        formats=("drawai.element_plans.v1",),
                    ),
                ),
                config={
                    "preset_id": "run0_element_refine",
                    "provider_id": "codex_sdk",
                    "prompt_role": "Refine element positions, types, and processing intent.",
                },
                position={"x": 760, "y": 160},
            ),
            WorkflowNode(
                node_id="asset_planner",
                node_type="processor",
                title="Asset Planner",
                inputs=(_input("elements", "Element Plans", ("element_plans",)),),
                outputs=(
                    _output(
                        "elements",
                        "Planned Elements",
                        ("element_plans",),
                        formats=("drawai.element_plans.v1",),
                    ),
                ),
                config={"processor_id": "asset_planner"},
                position={"x": 1020, "y": 160},
            ),
            WorkflowNode(
                node_id="asset_processors",
                node_type="processor",
                title="Asset Processors",
                inputs=(_input("elements", "Planned Elements", ("element_plans",)),),
                outputs=(
                    _output(
                        "asset_packages",
                        "Asset Packages",
                        ("asset_packages",),
                        formats=("drawai.asset_packages.v1",),
                    ),
                ),
                config={"processor_id": "asset_processors"},
                position={"x": 1280, "y": 160},
            ),
            WorkflowNode(
                node_id="svg_agent",
                node_type="agent",
                title="SVG Agent",
                inputs=(
                    _input("elements", "Element Plans", ("element_plans",)),
                    _input("asset_packages", "Asset Packages", ("asset_packages",)),
                ),
                outputs=(
                    _output(
                        "semantic_svg",
                        "Semantic SVG",
                        ("semantic_svg",),
                        formats=("drawai.semantic_svg.v1",),
                        deliverable=True,
                    ),
                ),
                config={
                    "preset_id": "svg_generation",
                    "provider_id": "codex_sdk",
                    "prompt_role": "Generate editable semantic SVG from element plans and asset packages.",
                },
                position={"x": 1540, "y": 160},
            ),
            WorkflowNode(
                node_id="svg_to_ppt",
                node_type="export",
                title="SVG to PPT",
                inputs=(_input("semantic_svg", "Semantic SVG", ("semantic_svg",)),),
                outputs=(
                    _output(
                        "pptx",
                        "PPTX",
                        ("pptx",),
                        formats=("drawai.pptx.v1",),
                        deliverable=True,
                    ),
                ),
                config={"exporter_id": "svg_to_ppt"},
                position={"x": 1800, "y": 240},
            ),
            WorkflowNode(
                node_id="output",
                node_type="output",
                title="Output",
                inputs=(
                    _input(
                        "deliverables",
                        "Deliverables",
                        ("semantic_svg", "pptx"),
                        cardinality="many",
                    ),
                ),
                outputs=(
                    _output(
                        "final_outputs",
                        "Final Outputs",
                        ("final_outputs",),
                        formats=("drawai.final_outputs.v1",),
                    ),
                ),
                config={"auto_collect_deliverables": True},
                position={"x": 2060, "y": 160},
            ),
        ),
        edges=(
            _edge("input", "image", "sam_parser", "image"),
            _edge("input", "image", "ocr_parser", "image"),
            _edge("sam_parser", "candidates", "fusion", "candidates"),
            _edge("ocr_parser", "candidates", "fusion", "candidates"),
            _edge("fusion", "elements", "run0_agent", "elements"),
            _edge("run0_agent", "elements", "asset_planner", "elements"),
            _edge("asset_planner", "elements", "asset_processors", "elements"),
            _edge("asset_planner", "elements", "svg_agent", "elements"),
            _edge("asset_processors", "asset_packages", "svg_agent", "asset_packages"),
            _edge("svg_agent", "semantic_svg", "svg_to_ppt", "semantic_svg"),
            _edge("svg_agent", "semantic_svg", "output", "deliverables"),
            _edge("svg_to_ppt", "pptx", "output", "deliverables"),
        ),
        defaults={
            "builtin": True,
            "read_only": True,
            "agent_provider_id": "codex_sdk",
        },
    )


def workflow_templates_dir(workspace: str | Path) -> Path:
    return Path(workspace).expanduser().resolve(strict=False) / "workflows"


def user_workflow_template_path(workspace: str | Path, template_id: str) -> Path:
    return workflow_templates_dir(workspace) / f"{_safe_template_id(template_id)}.json"


def copy_builtin_template(template_id: str, *, name: str) -> WorkflowTemplate:
    if template_id != DEFAULT_WORKFLOW_TEMPLATE_ID:
        raise ValueError(f"unknown built-in workflow template: {template_id}")
    copied_id = f"custom_{_safe_template_id(name).replace('-', '_')}"
    defaults = dict(default_drawai_workflow_template().defaults)
    defaults["builtin"] = False
    defaults["read_only"] = False
    defaults["source_template_id"] = template_id
    return replace(
        default_drawai_workflow_template(),
        template_id=copied_id,
        name=name,
        defaults=defaults,
    )


def _input(
    port_id: str,
    label: str,
    types: tuple[str, ...],
    *,
    cardinality: str = "single",
    formats: tuple[str, ...] = (),
) -> WorkflowPort:
    return WorkflowPort(
        port_id=port_id,
        label=label,
        types=types,
        required=True,
        cardinality=cardinality,  # type: ignore[arg-type]
        formats=formats,
    )


def _output(
    port_id: str,
    label: str,
    types: tuple[str, ...],
    *,
    formats: tuple[str, ...] = (),
    deliverable: bool = False,
) -> WorkflowPort:
    description = "deliverable" if deliverable else ""
    return WorkflowPort(
        port_id=port_id,
        label=label,
        types=types,
        required=False,
        formats=formats,
        description=description,
    )


def _edge(
    source_node_id: str,
    source_port_id: str,
    target_node_id: str,
    target_port_id: str,
) -> WorkflowEdge:
    return WorkflowEdge(
        edge_id=f"{source_node_id}:{source_port_id}->{target_node_id}:{target_port_id}",
        source_node_id=source_node_id,
        source_port_id=source_port_id,
        target_node_id=target_node_id,
        target_port_id=target_port_id,
    )


def _safe_template_id(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_").lower()
    if not slug:
        raise ValueError("template id must contain at least one safe character")
    return slug
