from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from drawai.tool_agent_runtime import invoke_drawai_tool_agent
from drawai.workflow.agents import agent_preset_by_id
from drawai.workflow.llm_execution import LLMExecutionRequest, execute_llm_prompt, render_llm_prompt


def test_drawai_tool_agent_loop_writes_file_through_tool(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[dict[str, Any]] = []

    _install_fake_openai(
        monkeypatch,
        calls,
        [
            _tool_message(
                "write_file",
                {
                    "path": "output/result.json",
                    "content": '{"ok": true}\n',
                },
            ),
            _text_message("done"),
        ],
    )

    result = invoke_drawai_tool_agent(
        prompt="Write output/result.json.",
        task_name="unit.tool_agent",
        runtime_config={
            "provider": "drawai_tool_agent",
            "connection_id": "drawai_tool_agent",
            "model_name": "fake-model",
            "api_key": "fake-key",
            "wire_api": "chat_completions",
        },
        workspace_dir=tmp_path,
        repo_root=Path(__file__).resolve().parents[2],
        trace_path=tmp_path / "trace.jsonl",
    )

    assert result.final_text == "done"
    assert result.tool_calls == 1
    assert (tmp_path / "output" / "result.json").read_text(encoding="utf-8") == '{"ok": true}\n'
    assert calls[0]["tools"][0]["type"] == "function"
    assert any(message["role"] == "tool" for message in calls[1]["messages"])
    trace_text = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    assert "tool_agent_tool_result" in trace_text
    assert "fake-key" not in trace_text


def test_llm_execution_uses_tool_agent_outputs_instead_of_final_text(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[dict[str, Any]] = []
    run_root = tmp_path / "run"
    workdir = run_root / "nodes" / "svg_compose" / "runs" / "001"
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>\n'
    output_path = "nodes/svg_compose/runs/001/output/semantic.svg"
    _install_fake_openai(
        monkeypatch,
        calls,
        [
            _tool_message("write_file", {"path": output_path, "content": svg}),
            _text_message("final summary only"),
        ],
    )
    prompt = render_llm_prompt(
        agent_preset_by_id("svg_generation"),
        inputs=(),
        node_config={
            "node_id": "svg_compose",
            "provider_id": "drawai_tool_agent",
            "model": "fake-model",
            "api_key": "fake-key",
        },
        runtime_context={"workflow_run_root": run_root, "node_workdir": workdir, "attempt_id": "001"},
    )

    result = execute_llm_prompt(
        LLMExecutionRequest(
            prompt=prompt,
            workdir=workdir,
            run_root=run_root,
            node_id="svg_compose",
            node_type="llm",
            runtime_config={"provider": "drawai_tool_agent", "model_name": "fake-model", "api_key": "fake-key"},
        ),
    )

    assert result.provider_id == "drawai_tool_agent"
    assert (workdir / "output" / "semantic.svg").read_text(encoding="utf-8") == svg
    assert (workdir / "llm_response.txt").read_text(encoding="utf-8") == "final summary only"
    assert "Direct Output Runtime Override" not in prompt.text
    assert "Tool Runtime Contract" in prompt.text
    assert "fake-key" not in prompt.text
    request_manifest = (workdir / "llm_execution_request.json").read_text(encoding="utf-8")
    assert "fake-key" not in request_manifest


def test_drawai_tool_agent_stops_after_successful_finalize(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[dict[str, Any]] = []
    _install_fake_openai(
        monkeypatch,
        calls,
        [
            _tool_message("write_file", {"path": "output/result.json", "content": '{"ok": true}\n'}),
            _tool_message("finalize", {"summary": "completed from finalize"}),
        ],
    )

    result = invoke_drawai_tool_agent(
        prompt="Write output/result.json and finalize.",
        task_name="unit.tool_agent.finalize",
        runtime_config={
            "provider": "drawai_tool_agent",
            "connection_id": "drawai_tool_agent",
            "model_name": "fake-model",
            "api_key": "fake-key",
            "wire_api": "chat_completions",
        },
        workspace_dir=tmp_path,
        repo_root=Path(__file__).resolve().parents[2],
        trace_path=tmp_path / "trace.jsonl",
        max_iterations=2,
    )

    assert result.final_text == "completed from finalize"
    assert result.iterations == 2
    assert len(calls) == 2


def _install_fake_openai(monkeypatch, calls: list[dict[str, Any]], messages: list[SimpleNamespace]) -> None:  # type: ignore[no-untyped-def]
    class FakeCompletions:
        def __init__(self) -> None:
            self.index = 0

        async def create(self, **payload: Any) -> SimpleNamespace:
            calls.append(payload)
            message = messages[self.index]
            self.index += 1
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeAsyncOpenAI:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=FakeCompletions())

        async def close(self) -> None:
            return None

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))


def _tool_message(name: str, arguments: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        content="",
        tool_calls=[
            SimpleNamespace(
                id=f"call_{name}",
                function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
            )
        ],
    )


def _text_message(content: str) -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=[])
