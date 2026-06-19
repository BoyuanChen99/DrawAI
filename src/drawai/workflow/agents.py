from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from .agent_prompt_defaults import (
    CUSTOM_AGENT_CONSTRAINTS,
    CUSTOM_AGENT_TASK,
    RUN0_ELEMENT_REFINE_CONSTRAINTS,
    RUN0_ELEMENT_REFINE_TASK,
    SVG_GENERATION_CONSTRAINTS,
    SVG_GENERATION_TASK,
)

AgentProviderKind = Literal["sdk", "cli"]

SUPPORTED_REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")
DANGEROUS_AGENT_CONFIG_KEYS = (
    "argv",
    "cmd",
    "command",
    "env",
    "executable",
    "shell_command",
)


@dataclass(frozen=True)
class AgentProviderSpec:
    provider_id: str
    label: str
    kind: AgentProviderKind
    resource_key: str
    default_max_concurrent: int
    executable: str = ""
    supports_images: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "label": self.label,
            "kind": self.kind,
            "resource_key": self.resource_key,
            "default_max_concurrent": self.default_max_concurrent,
            "executable": self.executable,
            "supports_images": self.supports_images,
            "description": self.description,
        }


@dataclass(frozen=True)
class AgentOutputDeclaration:
    port_id: str
    path: str
    format_id: str
    type: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "port_id": self.port_id,
            "path": self.path,
            "format_id": self.format_id,
            "type": self.type,
            "description": self.description,
        }


@dataclass(frozen=True)
class AgentPreset:
    preset_id: str
    title: str
    provider_id: str
    task: str
    outputs: tuple[AgentOutputDeclaration, ...]
    constraints: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "title": self.title,
            "provider_id": self.provider_id,
            "task": self.task,
            "outputs": [output.to_dict() for output in self.outputs],
            "constraints": list(self.constraints),
        }


@dataclass(frozen=True)
class AgentPrompt:
    preset_id: str
    provider_id: str
    text: str
    inputs: tuple[Mapping[str, Any], ...]
    outputs: tuple[Mapping[str, Any], ...]
    options: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "provider_id": self.provider_id,
            "text": self.text,
            "inputs": [dict(item) for item in self.inputs],
            "outputs": [dict(item) for item in self.outputs],
            "options": dict(self.options),
        }


def default_agent_provider_registry() -> dict[str, AgentProviderSpec]:
    return {
        "codex_sdk": AgentProviderSpec(
            provider_id="codex_sdk",
            label="Codex SDK",
            kind="sdk",
            resource_key="agent_provider:codex_sdk",
            default_max_concurrent=5,
            description="OpenAI Codex Python SDK provider.",
        ),
        "codex_cli": AgentProviderSpec(
            provider_id="codex_cli",
            label="Codex CLI",
            kind="cli",
            resource_key="agent_provider:codex_cli",
            default_max_concurrent=1,
            executable="codex",
            description="Codex CLI provider for file-backed Agent nodes.",
        ),
        "kimi_cli": AgentProviderSpec(
            provider_id="kimi_cli",
            label="Kimi CLI",
            kind="cli",
            resource_key="agent_provider:kimi_cli",
            default_max_concurrent=2,
            executable="kimi",
            description="Kimi CLI provider for file-backed Agent nodes.",
        ),
    }


def run0_agent_preset() -> AgentPreset:
    return AgentPreset(
        preset_id="run0_element_refine",
        title="Run0 Element Refinement",
        provider_id="codex_sdk",
        task=RUN0_ELEMENT_REFINE_TASK,
        outputs=(
            AgentOutputDeclaration(
                port_id="elements",
                path="output/elements.json",
                format_id="drawai.element_plans.v1",
                type="element_plans",
                description="Refined element plans in the standard DrawAI v1 element plan JSON format.",
            ),
        ),
        constraints=(
            *RUN0_ELEMENT_REFINE_CONSTRAINTS,
        ),
    )


def svg_agent_preset() -> AgentPreset:
    return AgentPreset(
        preset_id="svg_generation",
        title="SVG Generation",
        provider_id="codex_sdk",
        task=SVG_GENERATION_TASK,
        outputs=(
            AgentOutputDeclaration(
                port_id="semantic_svg",
                path="output/semantic.svg",
                format_id="drawai.semantic_svg.v1",
                type="semantic_svg",
                description="Editable semantic SVG rooted at an svg element.",
            ),
        ),
        constraints=(
            *SVG_GENERATION_CONSTRAINTS,
        ),
    )


def custom_agent_preset() -> AgentPreset:
    return AgentPreset(
        preset_id="custom_agent",
        title="Custom Agent",
        provider_id="codex_sdk",
        task=CUSTOM_AGENT_TASK,
        outputs=(
            AgentOutputDeclaration(
                port_id="image",
                path="output/image.png",
                format_id="drawai.image.v1",
                type="image",
                description="Generated or edited image file.",
            ),
        ),
        constraints=(
            *CUSTOM_AGENT_CONSTRAINTS,
        ),
    )


def agent_preset_by_id(preset_id: str) -> AgentPreset:
    if preset_id == "run0_element_refine":
        return run0_agent_preset()
    if preset_id == "svg_generation":
        return svg_agent_preset()
    if preset_id == "custom_agent":
        return custom_agent_preset()
    raise ValueError(f"unknown Agent preset: {preset_id}")


def render_agent_prompt(
    preset: AgentPreset,
    *,
    inputs: Sequence[Mapping[str, Any]],
    node_config: Mapping[str, Any] | None = None,
) -> AgentPrompt:
    config = dict(node_config or {})
    _validate_agent_config(config)
    provider_id = str(config.get("provider_id") or preset.provider_id)
    selected_inputs = _selected_inputs(inputs, config)
    outputs = _configured_outputs(preset, config)
    options = _agent_options(config)
    text = _render_prompt_text(
        node_id=str(config.get("node_id") or "<agent_node_id>"),
        provider_id=provider_id,
        inputs=selected_inputs,
        outputs=outputs,
        options=options,
        task=_agent_task(preset, config),
        constraints=_agent_constraints(preset, config),
    )
    return AgentPrompt(
        preset_id=preset.preset_id,
        provider_id=provider_id,
        text=text,
        inputs=selected_inputs,
        outputs=outputs,
        options=options,
    )


def _render_prompt_text(
    *,
    node_id: str,
    provider_id: str,
    inputs: tuple[Mapping[str, Any], ...],
    outputs: tuple[Mapping[str, Any], ...],
    options: Mapping[str, Any],
    task: str,
    constraints: tuple[str, ...],
) -> str:
    lines = [
        "## Agent Runtime Settings",
        f"- Provider: {provider_id}",
        f"- Node workdir: nodes/{node_id}/runs/<attempt_id>",
    ]
    for key, value in options.items():
        lines.append(f"- {key}: {value}")

    lines.extend(
        [
            "",
            "## Task",
            task,
            "",
            "## Connected Input Files",
            (
                "The DrawAI harness records these paths relative to the workflow run "
                "root and writes the same list to input_manifest.json in this node "
                "workdir. If the Agent process runs from the node workdir, open an "
                "input path with ../../../<path> to resolve it from the run root."
            ),
        ]
    )
    if inputs:
        for item in inputs:
            source = _source_label(item)
            lines.extend(
                [
                    f"- Path: {item['path']}",
                    f"  Format: {item.get('format_id') or 'unspecified'}",
                    f"  Type: {item.get('type') or 'unspecified'}",
                    f"  Source: {source}",
                    f"  Description: {item.get('description') or 'No description supplied.'}",
                ]
            )
    else:
        lines.append("- No connected input files were provided.")

    lines.extend(
        [
            "",
            "## Declared Output Files",
            (
                "Write exactly these files relative to this Agent node workdir. "
                f"For example, output/... is saved as nodes/{node_id}/runs/"
                "<attempt_id>/output/... from the workflow run root, and the harness "
                "records the collected artifact path in node_run.json."
            ),
        ]
    )
    for output in outputs:
        lines.extend(
            [
                f"- Path: {output['path']}",
                f"  Format: {output['format_id']}",
                f"  Type: {output['type']}",
                f"  Port: {output['port_id']}",
                f"  Description: {output['description']}",
            ]
        )

    if constraints:
        lines.extend(["", "## Constraints"])
        for constraint in constraints:
            lines.append(f"- {constraint}")

    return "\n".join(lines).strip() + "\n"


def _selected_inputs(
    inputs: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    overrides = _input_overrides(config)
    selected: list[Mapping[str, Any]] = []
    for item in inputs:
        normalized = dict(item)
        path = _required_string(normalized.get("path"), "input.path")
        normalized["path"] = path
        override = _override_for_input(overrides, normalized)
        if override and override.get("include") is False:
            continue
        if override and isinstance(override.get("description"), str):
            normalized["description"] = override["description"]
        selected.append(normalized)
    return tuple(selected)


def _configured_outputs(
    preset: AgentPreset,
    config: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    raw_outputs = config.get("outputs", config.get("output_declarations"))
    if raw_outputs is None:
        return tuple(output.to_dict() for output in preset.outputs)
    if not isinstance(raw_outputs, list | tuple):
        raise ValueError("Agent outputs must be an array")
    outputs: list[Mapping[str, Any]] = []
    for index, raw_output in enumerate(raw_outputs):
        if not isinstance(raw_output, Mapping):
            raise ValueError(f"Agent outputs[{index}] must be an object")
        outputs.append(
            {
                "port_id": _required_string(raw_output.get("port_id"), f"outputs[{index}].port_id"),
                "path": _required_string(raw_output.get("path"), f"outputs[{index}].path"),
                "format_id": _required_string(raw_output.get("format_id"), f"outputs[{index}].format_id"),
                "type": _required_string(raw_output.get("type"), f"outputs[{index}].type"),
                "description": _required_string(
                    raw_output.get("description"),
                    f"outputs[{index}].description",
                ),
            }
        )
    return tuple(outputs)


def _validate_agent_config(config: Mapping[str, Any]) -> None:
    for key in DANGEROUS_AGENT_CONFIG_KEYS:
        if key in config:
            raise ValueError(f"Agent node config cannot override {key}")
    if config.get("reasoning_effort") not in (None, ""):
        effort = str(config["reasoning_effort"]).strip().lower()
        if effort not in SUPPORTED_REASONING_EFFORTS:
            raise ValueError(f"unsupported reasoning_effort: {effort}")
    if config.get("timeout_seconds") not in (None, ""):
        timeout = config["timeout_seconds"]
        if not isinstance(timeout, int | float) or isinstance(timeout, bool) or timeout <= 0:
            raise ValueError("timeout_seconds must be positive")
    for field_name in ("model", "profile", "provider_id"):
        if field_name in config and not isinstance(config[field_name], str):
            raise ValueError(f"{field_name} must be a string")


def _agent_options(config: Mapping[str, Any]) -> Mapping[str, Any]:
    options: dict[str, Any] = {}
    for key in ("model", "profile", "timeout_seconds", "reasoning_effort"):
        if key in config and config[key] not in (None, ""):
            options[key] = config[key]
    return options


def _agent_task(preset: AgentPreset, config: Mapping[str, Any]) -> str:
    raw = (
        config.get("task")
        or config.get("prompt_role")
        or config.get("prompt_fragments")
        or config.get("user_prompt")
        or preset.task
    )
    if not isinstance(raw, str):
        raise ValueError("Agent task must be a string")
    task = raw.strip()
    if not task:
        raise ValueError("Agent task must be non-empty")
    return task


def _agent_constraints(preset: AgentPreset, config: Mapping[str, Any]) -> tuple[str, ...]:
    raw = config.get("constraints")
    if raw in (None, ""):
        return ()
    if isinstance(raw, str):
        return tuple(line.strip() for line in raw.splitlines() if line.strip())
    if not isinstance(raw, list | tuple):
        raise ValueError("Agent constraints must be a string or array of strings")
    constraints: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str):
            raise ValueError(f"Agent constraints[{index}] must be a string")
        constraint = item.strip()
        if constraint:
            constraints.append(constraint)
    return tuple(constraints)


def _input_overrides(config: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    raw = config.get("input_overrides", {})
    if not isinstance(raw, Mapping):
        raise ValueError("Agent input_overrides must be an object")
    overrides: dict[str, Mapping[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise ValueError("Agent input_overrides keys must be strings")
        if not isinstance(value, Mapping):
            raise ValueError(f"Agent input_overrides.{key} must be an object")
        overrides[key] = value
    return overrides


def _override_for_input(
    overrides: Mapping[str, Mapping[str, Any]],
    item: Mapping[str, Any],
) -> Mapping[str, Any]:
    path = str(item.get("path") or "")
    source_node = str(item.get("source_node_id") or "")
    source_port = str(item.get("source_port_id") or "")
    return (
        overrides.get(path)
        or overrides.get(f"{source_node}.{source_port}")
        or overrides.get(source_node)
        or {}
    )


def _source_label(item: Mapping[str, Any]) -> str:
    source_node = str(item.get("source_node_id") or "")
    source_port = str(item.get("source_port_id") or "")
    if source_node and source_port:
        return f"{source_node}.{source_port}"
    if source_node:
        return source_node
    return "connected input"


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value
