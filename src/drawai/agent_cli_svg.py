from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import model_runtime


AGENT_CLI_RUNNER = "agent_cli"
SUPPORTED_AGENT_CLI_AGENTS = frozenset({"kimi", "claude", "codex", "custom"})


class AgentCliSvgError(RuntimeError):
    """Raised when a direct agent CLI cannot complete a DrawAI task."""


class AgentCliSvgSession:
    """Thin adapter around file-editing agent CLIs such as Kimi, Claude, or Codex."""

    def __init__(
        self,
        *,
        runtime_config: Mapping[str, Any] | None = None,
        trace_path: str | Path | None = None,
        isolated_cwd: str | Path | None = None,
    ) -> None:
        self.runtime_config = dict(runtime_config or {})
        self.trace_path = Path(trace_path) if trace_path is not None else None
        self.isolated_cwd = Path(isolated_cwd or Path.cwd()).expanduser().resolve(strict=False)
        self.timeout_seconds = model_runtime._runtime_timeout_seconds(self.runtime_config)
        self.agent = _agent_cli_agent(self.runtime_config)

    def invoke(
        self,
        *,
        image_paths: str | Path | Sequence[str | Path],
        prompt: str,
        task_name: str,
        output_svg_path: str | Path | None = None,
        output_response_path: str | Path | None = None,
    ) -> str:
        normalized_images = _normalize_image_paths(image_paths)
        svg_path = (
            _normalize_workspace_output_path(output_svg_path, self.isolated_cwd)
            if output_svg_path is not None
            else None
        )
        response_path = (
            _normalize_workspace_output_path(output_response_path, self.isolated_cwd)
            if output_response_path is not None
            else None
        )
        if svg_path is not None:
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            if svg_path.exists():
                svg_path.unlink()
        if response_path is not None:
            response_path.parent.mkdir(parents=True, exist_ok=True)
            if response_path.exists():
                response_path.unlink()

        controlled_prompt = _controlled_prompt(
            prompt,
            agent=self.agent,
            workspace_dir=self.isolated_cwd,
            image_paths=normalized_images,
            output_svg_path=svg_path,
            output_response_path=response_path,
        )
        result = self._run(
            image_paths=normalized_images,
            prompt=controlled_prompt,
            task_name=task_name,
        )
        if response_path is not None and not response_path.exists():
            response_path.write_text(result.stdout.strip() + "\n", encoding="utf-8")
        if svg_path is not None:
            if svg_path.exists():
                svg_text = _read_output_svg_file(svg_path)
                source = "output_svg_path"
            else:
                svg_text = _svg_from_text(result.stdout)
                svg_path.write_text(svg_text, encoding="utf-8")
                source = "stdout"
        else:
            svg_text = _svg_from_text(result.stdout)
            source = "stdout"
        model_runtime._append_trace(
            self.trace_path,
            {
                "type": "agent_cli_response",
                "runner": AGENT_CLI_RUNNER,
                "agent": self.agent,
                "task_name": task_name,
                "returncode": result.returncode,
                "duration_ms": result.duration_ms,
                "stdout_chars": len(result.stdout),
                "stderr_chars": len(result.stderr),
                "source": source,
                "output_svg_path": str(svg_path) if svg_path is not None else None,
                "output_response_path": str(response_path) if response_path is not None else None,
            },
        )
        return svg_text

    def invoke_text(
        self,
        *,
        image_paths: str | Path | Sequence[str | Path],
        prompt: str,
        task_name: str,
    ) -> str:
        normalized_images = _normalize_image_paths(image_paths)
        controlled_prompt = _controlled_prompt(
            prompt,
            agent=self.agent,
            workspace_dir=self.isolated_cwd,
            image_paths=normalized_images,
        )
        result = self._run(
            image_paths=normalized_images,
            prompt=controlled_prompt,
            task_name=task_name,
        )
        model_runtime._append_trace(
            self.trace_path,
            {
                "type": "agent_cli_text_response",
                "runner": AGENT_CLI_RUNNER,
                "agent": self.agent,
                "task_name": task_name,
                "returncode": result.returncode,
                "duration_ms": result.duration_ms,
                "stdout_chars": len(result.stdout),
                "stderr_chars": len(result.stderr),
            },
        )
        return result.stdout

    def _run(
        self,
        *,
        image_paths: Sequence[Path],
        prompt: str,
        task_name: str,
    ) -> "_AgentCliResult":
        command = _agent_cli_command(
            self.runtime_config,
            work_dir=self.isolated_cwd,
            image_paths=image_paths,
        )
        model_runtime._append_trace(
            self.trace_path,
            {
                "type": "agent_cli_request",
                "runner": AGENT_CLI_RUNNER,
                "agent": self.agent,
                "task_name": task_name,
                "command": command,
                "cwd": str(self.isolated_cwd),
                "timeout_seconds": self.timeout_seconds,
                "prompt_chars": len(prompt),
                "image_paths": [str(path) for path in image_paths],
            },
        )
        started_at = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                cwd=self.isolated_cwd,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started_at) * 1000)
            model_runtime._append_trace(
                self.trace_path,
                {
                    "type": "agent_cli_error",
                    "runner": AGENT_CLI_RUNNER,
                    "agent": self.agent,
                    "task_name": task_name,
                    "duration_ms": duration_ms,
                    "error_type": "TimeoutExpired",
                    "error": f"Agent CLI exceeded timeout_seconds={self.timeout_seconds:g}",
                    "stdout_tail": _tail(exc.stdout),
                    "stderr_tail": _tail(exc.stderr),
                },
            )
            raise AgentCliSvgError(f"Agent CLI exceeded timeout_seconds={self.timeout_seconds:g}") from exc

        duration_ms = int((time.monotonic() - started_at) * 1000)
        result = _AgentCliResult(
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            returncode=completed.returncode,
            duration_ms=duration_ms,
        )
        if completed.returncode != 0:
            model_runtime._append_trace(
                self.trace_path,
                {
                    "type": "agent_cli_error",
                    "runner": AGENT_CLI_RUNNER,
                    "agent": self.agent,
                    "task_name": task_name,
                    "duration_ms": duration_ms,
                    "returncode": completed.returncode,
                    "stdout_tail": _tail(result.stdout),
                    "stderr_tail": _tail(result.stderr),
                },
            )
            raise AgentCliSvgError(
                f"Agent CLI failed with returncode={completed.returncode}. "
                f"stderr tail: {_tail(result.stderr)}"
            )
        return result


class _AgentCliResult:
    def __init__(self, *, stdout: str, stderr: str, returncode: int, duration_ms: int) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.duration_ms = duration_ms


def invoke_agent_cli_svg_text(
    *,
    image_paths: str | Path | Sequence[str | Path],
    prompt: str,
    task_name: str,
    runtime_config: Mapping[str, Any] | None = None,
    trace_path: str | Path | None = None,
    isolated_cwd: str | Path | None = None,
    output_svg_path: str | Path | None = None,
    output_response_path: str | Path | None = None,
) -> str:
    session = AgentCliSvgSession(
        runtime_config=runtime_config,
        trace_path=trace_path,
        isolated_cwd=isolated_cwd,
    )
    return session.invoke(
        image_paths=image_paths,
        prompt=prompt,
        task_name=task_name,
        output_svg_path=output_svg_path,
        output_response_path=output_response_path,
    )


def invoke_agent_cli_text(
    *,
    image_paths: str | Path | Sequence[str | Path],
    prompt: str,
    task_name: str,
    runtime_config: Mapping[str, Any] | None = None,
    trace_path: str | Path | None = None,
    isolated_cwd: str | Path | None = None,
) -> str:
    session = AgentCliSvgSession(
        runtime_config=runtime_config,
        trace_path=trace_path,
        isolated_cwd=isolated_cwd,
    )
    return session.invoke_text(
        image_paths=image_paths,
        prompt=prompt,
        task_name=task_name,
    )


def _agent_cli_command(
    runtime_config: Mapping[str, Any],
    *,
    work_dir: Path,
    image_paths: Sequence[Path] = (),
) -> list[str]:
    agent = _agent_cli_agent(runtime_config)
    raw = _agent_cli_command_raw(runtime_config, agent)
    command = _parse_command(raw)
    model_name = str(runtime_config.get("model_name") or "").strip()
    if agent == "kimi":
        return _kimi_preset_command(command, model_name=model_name, work_dir=work_dir)
    if agent == "claude":
        return _claude_command(command, model_name=model_name)
    if agent == "codex":
        return _codex_command(command, model_name=model_name, work_dir=work_dir, image_paths=image_paths)
    return command


def _agent_cli_agent(runtime_config: Mapping[str, Any]) -> str:
    cli = runtime_config.get("cli")
    agent = ""
    if isinstance(cli, Mapping):
        agent = str(cli.get("agent") or "").strip().lower()
    if not agent:
        provider = str(runtime_config.get("provider") or "").strip().lower()
        connection_id = str(runtime_config.get("connection_id") or "").strip().lower()
        if provider in {"kimi-cli"} or connection_id in {"kimi", "kimi-cli"}:
            agent = "kimi"
        elif provider in {"claude-cli"} or connection_id in {"claude", "claude-cli"}:
            agent = "claude"
        elif provider in {"codex-cli"} or connection_id in {"codex", "codex-cli"}:
            agent = "codex"
        else:
            agent = "kimi"
    if agent not in SUPPORTED_AGENT_CLI_AGENTS:
        supported = ", ".join(sorted(SUPPORTED_AGENT_CLI_AGENTS))
        raise AgentCliSvgError(f"Unsupported agent CLI preset: {agent!r}. Expected one of: {supported}")
    return agent


def _agent_cli_command_raw(runtime_config: Mapping[str, Any], agent: str) -> Any:
    cli = runtime_config.get("cli")
    if isinstance(cli, Mapping) and cli.get("command"):
        return cli.get("command")
    env_command = os.environ.get("DRAWAI_AGENT_CLI_COMMAND")
    if env_command:
        return env_command
    if agent == "kimi":
        return ("kimi",)
    if agent == "claude":
        return ("claude",)
    if agent == "codex":
        return ("codex", "exec")
    raise AgentCliSvgError("model_runtime.cli.command is required for custom agent CLI")


def _parse_command(raw: Any) -> list[str]:
    if isinstance(raw, str):
        command = shlex.split(raw)
    elif isinstance(raw, Sequence):
        command = [str(item) for item in raw]
    else:
        raise AgentCliSvgError("runtime_config.cli.command must be a string or list of strings")
    if not command:
        raise AgentCliSvgError("runtime_config.cli.command must not be empty")
    return command


def _kimi_preset_command(command: list[str], *, model_name: str, work_dir: Path) -> list[str]:
    if model_name and "--model" not in command and "-m" not in command:
        command.extend(["--model", model_name])
    if "--work-dir" not in command and "-w" not in command:
        command.extend(["--work-dir", str(work_dir)])
    for flag in ("--print", "--yolo", "--final-message-only"):
        if flag not in command:
            command.append(flag)
    if "--input-format" not in command:
        command.extend(["--input-format", "text"])
    return command


def _claude_command(command: list[str], *, model_name: str) -> list[str]:
    if model_name and "--model" not in command:
        command.extend(["--model", model_name])
    if "--print" not in command and "-p" not in command:
        command.append("--print")
    if "--permission-mode" not in command and "--dangerously-skip-permissions" not in command:
        command.extend(["--permission-mode", "bypassPermissions"])
    if "--output-format" not in command:
        command.extend(["--output-format", "text"])
    if "--input-format" not in command:
        command.extend(["--input-format", "text"])
    return command


def _codex_command(command: list[str], *, model_name: str, work_dir: Path, image_paths: Sequence[Path]) -> list[str]:
    if model_name and "--model" not in command and "-m" not in command:
        command.extend(["--model", model_name])
    if "--cd" not in command and "-C" not in command:
        command.extend(["--cd", str(work_dir)])
    if "--skip-git-repo-check" not in command:
        command.append("--skip-git-repo-check")
    if "--dangerously-bypass-approvals-and-sandbox" not in command and "--sandbox" not in command:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    if "--color" not in command:
        command.extend(["--color", "never"])
    for image_path in image_paths:
        command.extend(["-i", str(image_path)])
    if "-" not in command:
        command.append("-")
    return command


def _controlled_prompt(
    prompt: str,
    *,
    agent: str,
    workspace_dir: Path,
    image_paths: Sequence[Path],
    output_svg_path: Path | None = None,
    output_response_path: Path | None = None,
) -> str:
    label = _agent_label(agent)
    image_block = "\n".join(f"- {path}" for path in image_paths) or "- none"
    if output_svg_path is None:
        return (
            f"Internal DrawAI {label} task.\n"
            f"Workspace root: {workspace_dir}\n"
            f"Use {label}'s own file, shell, and media-reading tools directly inside this workspace. "
            "Do not use MCP tools, apps, web search, memories, hooks, or multi-agent delegation. "
            "Write DrawAI outputs only inside the workspace root unless this prompt explicitly names another output path.\n\n"
            "Local image paths available for visual inspection:\n"
            f"{image_block}\n\n"
            f"{prompt}"
        )
    response_line = (
        f"- If useful, write brief notes to: {output_response_path}\n"
        if output_response_path is not None
        else ""
    )
    return (
        f"Internal DrawAI {label} SVG generation task.\n"
        f"Workspace root: {workspace_dir}\n"
        f"Use {label}'s own file, shell, and media-reading tools directly inside this workspace. "
        "Do not use MCP tools, apps, web search, memories, hooks, or multi-agent delegation. "
        "Write DrawAI outputs only inside the workspace root unless this prompt explicitly names another output path.\n\n"
        "Local image paths available for visual inspection:\n"
        f"{image_block}\n\n"
        "Write the SVG file yourself. Output contract:\n"
        f"- Required SVG output path: {output_svg_path}\n"
        f"{response_line}"
        "- The SVG output file must contain exactly one complete SVG document, starting with <svg and ending with </svg>.\n"
        "- Keep the final chat response short; the SVG file is the source of truth.\n\n"
        f"{prompt}"
    )


def _agent_label(agent: str) -> str:
    if agent == "kimi":
        return "Kimi CLI"
    if agent == "claude":
        return "Claude CLI"
    if agent == "codex":
        return "Codex CLI"
    return "Agent CLI"


def _normalize_workspace_output_path(path_value: str | Path, workspace_dir: Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = workspace_dir / path
    resolved = path.resolve(strict=False)
    if not _is_relative_to(resolved, workspace_dir):
        raise AgentCliSvgError(f"output path must be inside agent CLI workspace root: {resolved}")
    return resolved


def _read_output_svg_file(path: Path) -> str:
    if not path.exists():
        raise AgentCliSvgError(f"Agent CLI did not write required SVG output file: {path}")
    if not path.is_file():
        raise AgentCliSvgError(f"Agent CLI SVG output path is not a file: {path}")
    svg_text = path.read_text(encoding="utf-8").strip()
    if not svg_text.startswith("<svg") or not svg_text.endswith("</svg>"):
        raise AgentCliSvgError(f"Agent CLI SVG output file is not a complete SVG document: {path}")
    return svg_text


def _svg_from_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("<svg") and stripped.endswith("</svg>"):
        return stripped
    match = re.search(r"(<svg\b.*?</svg>)", stripped, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    raise AgentCliSvgError("Agent CLI final response did not contain a complete SVG document")


def _normalize_image_paths(image_paths: str | Path | Sequence[str | Path]) -> list[Path]:
    if isinstance(image_paths, (str, Path)):
        return [Path(image_paths)]
    return [Path(path) for path in image_paths]


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _tail(value: Any, *, max_chars: int = 2000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    return text[-max_chars:]
