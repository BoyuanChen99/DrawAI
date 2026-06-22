from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from drawai.workflow.agents import agent_preset_by_id
from drawai.workflow.llm_execution import (
    LLMExecutionRequest,
    LLMExecutionResult,
    execute_llm_prompt,
    render_llm_prompt,
)


def test_llm_prompt_embeds_json_inputs_and_attaches_image_content(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    image_path = run_root / "nodes" / "input" / "runs" / "001" / "output" / "image.png"
    page_spec_path = run_root / "nodes" / "fuse" / "runs" / "001" / "output" / "page_spec.json"
    image_path.parent.mkdir(parents=True)
    page_spec_path.parent.mkdir(parents=True)
    Image.new("RGB", (8, 8), "white").save(image_path)
    page_spec_path.write_text(
        json.dumps(
            {
                "schema": "drawai.page_spec.v1",
                "page_id": "p1",
                "source": {"width_px": 8, "height_px": 8},
                "canvas": {"width_px": 8, "height_px": 8},
                "elements": [],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    prompt = render_llm_prompt(
        agent_preset_by_id("page_spec_refine"),
        inputs=(
            {
                "path": "nodes/input/runs/001/output/image.png",
                "format_id": "drawai.image.v1",
                "type": "image",
                "source_node_id": "input",
                "source_port_id": "image",
                "description": "Original page image.",
            },
            {
                "path": "nodes/fuse/runs/001/output/page_spec.json",
                "format_id": "drawai.page_spec.v1",
                "type": "page_spec",
                "source_node_id": "fuse",
                "source_port_id": "page_spec",
                "description": "Fused PageSpec evidence.",
            },
        ),
        node_config={"node_id": "page_spec_refine"},
        runtime_context={
            "workflow_run_root": run_root,
            "node_workdir": run_root / "nodes" / "page_spec_refine" / "runs" / "001",
            "attempt_id": "001",
        },
    )

    assert prompt.image_paths == (image_path,)
    assert "## Connected Input Contents" in prompt.text
    assert "Image content is attached to this LLM request" in prompt.text
    assert '"schema": "drawai.page_spec.v1"' in prompt.text
    assert "Fused PageSpec evidence." in prompt.text
    assert "Do not read workflow files from disk" in prompt.text
    assert "Return the page_spec output as JSON content" in prompt.text
    assert "Write path from Agent cwd" not in prompt.text


def test_execute_llm_prompt_extracts_fenced_json_and_writes_declared_output(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    workdir = run_root / "nodes" / "page_spec_refine" / "runs" / "001"
    page_spec = {
        "schema": "drawai.page_spec.v1",
        "page_id": "p1",
        "source": {"width_px": 10, "height_px": 10},
        "canvas": {"width_px": 10, "height_px": 10},
        "elements": [],
    }
    prompt = render_llm_prompt(
        agent_preset_by_id("page_spec_refine"),
        inputs=(),
        node_config={"node_id": "page_spec_refine"},
        runtime_context={"workflow_run_root": run_root, "node_workdir": workdir, "attempt_id": "001"},
    )

    def invoker(**_kwargs: Any) -> str:
        return "```json\n" + json.dumps(page_spec) + "\n```"

    result = execute_llm_prompt(
        LLMExecutionRequest(
            prompt=prompt,
            workdir=workdir,
            run_root=run_root,
            node_id="page_spec_refine",
            node_type="llm",
            runtime_config={"provider": "fake", "model_name": "fake-model"},
        ),
        invoke_model=invoker,
    )

    saved = json.loads((workdir / "output" / "page_spec.json").read_text(encoding="utf-8"))
    assert saved == page_spec
    assert result.provider_id == "openai_responses"
    assert result.prompt_path == workdir / "llm_prompt.md"
    assert result.stdout_path == workdir / "llm_response.txt"
    assert result.execution_manifest_path == workdir / "llm_execution.json"


def test_execute_llm_prompt_extracts_json_wrapped_svg_and_writes_declared_output(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    workdir = run_root / "nodes" / "svg_compose" / "runs" / "001"
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
    prompt = render_llm_prompt(
        agent_preset_by_id("svg_generation"),
        inputs=(),
        node_config={"node_id": "svg_compose"},
        runtime_context={"workflow_run_root": run_root, "node_workdir": workdir, "attempt_id": "001"},
    )

    def invoker(**kwargs: Any) -> str:
        assert kwargs["image_paths"] == ()
        assert "Return the semantic_svg output as SVG content" in kwargs["prompt"]
        return json.dumps({"svg": svg})

    execute_llm_prompt(
        LLMExecutionRequest(
            prompt=prompt,
            workdir=workdir,
            run_root=run_root,
            node_id="svg_compose",
            node_type="llm",
            runtime_config={"provider": "fake", "model_name": "fake-model"},
        ),
        invoke_model=invoker,
    )

    assert (workdir / "output" / "semantic.svg").read_text(encoding="utf-8") == svg + "\n"
