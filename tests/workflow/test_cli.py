from __future__ import annotations

import json
from pathlib import Path

from drawai.cli import main
from drawai.workflow.cli import workflow_cli
from drawai.workflow.node_runs import begin_node_run, finish_node_run_ok
from drawai.workflow.templates import user_workflow_template_path


def _read_stdout_json(capsys) -> dict[str, object]:  # type: ignore[no-untyped-def]
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, dict)
    return payload


def test_workflow_templates_cli_lists_builtin_templates(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    status = workflow_cli(["templates", "--workspace", str(tmp_path)])

    payload = _read_stdout_json(capsys)
    assert status == 0
    assert payload["templates"][0]["template_id"] == "default_drawai_dag"


def test_workflow_copy_and_validate_template_cli(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    status = workflow_cli(
        [
            "copy-template",
            "default_drawai_dag",
            "--name",
            "CLI Copy",
            "--workspace",
            str(tmp_path),
        ]
    )
    copied = _read_stdout_json(capsys)["template"]
    assert status == 0
    assert copied["template_id"] == "custom_cli_copy"
    assert user_workflow_template_path(tmp_path, "custom_cli_copy").is_file()

    status = workflow_cli(
        [
            "validate",
            "--template",
            "custom_cli_copy",
            "--workspace",
            str(tmp_path),
        ]
    )
    payload = _read_stdout_json(capsys)
    assert status == 0
    assert payload["ok"] is True


def test_workflow_prompt_cli_renders_agent_prompt(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    input_manifest = tmp_path / "input_manifest.json"
    input_manifest.write_text(
        json.dumps(
            {
                "schema": "drawai.workflow_input_manifest.v1",
                "inputs": [
                    {
                        "path": "nodes/fusion/runs/001/output/elements.json",
                        "format_id": "drawai.element_plans.v1",
                        "type": "element_plans",
                        "description": "Fused candidates.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    status = workflow_cli(
        [
            "prompt",
            "run0_element_refine",
            "--input-manifest",
            str(input_manifest),
            "--provider",
            "kimi_cli",
        ]
    )

    payload = _read_stdout_json(capsys)
    assert status == 0
    assert payload["provider_id"] == "kimi_cli"
    assert "Fused candidates." in payload["text"]
    assert "output/elements.json" in payload["text"]


def test_workflow_inspect_node_run_cli_reads_latest_manifest(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    record = begin_node_run(tmp_path, "agent", node_type="agent", provider_id="codex_sdk")
    finish_node_run_ok(record, outputs=())

    status = workflow_cli(["inspect-node-run", str(tmp_path), "agent"])

    payload = _read_stdout_json(capsys)
    assert status == 0
    assert payload["node_id"] == "agent"
    assert payload["attempt_id"] == "001"
    assert payload["status"] == "ok"


def test_top_level_cli_routes_workflow_command(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    status = main(["workflow", "templates", "--workspace", str(tmp_path)])

    payload = _read_stdout_json(capsys)
    assert status == 0
    assert payload["templates"][0]["template_id"] == "default_drawai_dag"
