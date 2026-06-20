# DrawAI Workflow DAG Canvas Design

Date: 2026-06-19

Status: approved design for implementation planning

Branch: `caopu/drawai-v2-robust-pipeline-design`

## Goal

Replace the current fixed v2 linear pipeline with a first-class editable workflow DAG and a Dify-like Workbench canvas. The default workflow should reproduce the current DrawAI behavior, but parser, processor, Agent, export, and output steps become nodes with typed inputs and outputs.

The workflow canvas is not only a visual explanation. It is the execution authority. Each run stores a workflow snapshot, each node run owns a canonical work directory, and compatibility paths such as `svg/semantic.svg` or `exports/*.pptx` are mirrors or references to node outputs.

## Confirmed Product Decisions

- Add a third top-level Workbench tab: `Workflow`, alongside `生成` and `处理`.
- `Workflow` is a template editor, not a batch/task management surface.
- Use a complete React Flow canvas implementation with `@xyflow/react`.
- The first implementation fully DAG-ifies execution rather than adding a parallel optional workflow runner.
- The built-in `Default DrawAI DAG` is read-only.
- Users can copy the built-in template, edit it, save it locally, and set a custom template as their default run template.
- User workflow templates are machine JSON edited through Workbench, stored under ignored local state such as `.local/workbench/workflows/*.json`.
- Upload creates batch/cases without immediately running them. The processing page binds a workflow template to an unstarted batch and then starts the task.
- Once a case starts, it stores a `workflow_snapshot.json`; later template edits do not affect that run.
- Every node run owns `case_root/nodes/<node_id>/runs/<attempt_id>/` as its canonical work directory.
- Existing public output paths remain as compatibility mirrors or references.
- `package_run` is no longer a product-facing canvas node. The canvas exposes an `Output` node that collects final deliverables and updates package metadata internally.
- `Output` automatically collects deliverable files from connected upstream nodes and lets users hide individual deliverables.
- Run0 refinement and SVG generation are both instances of the same `AgentNode` abstraction.
- Agent providers are global provider registry entries such as `codex_sdk`, `codex_cli`, and `kimi_cli`; nodes select a provider and can override safe fields only.
- Workflow execution runs independent nodes in parallel subject to global resource/provider limits.
- Agent provider limits are per provider id, not a single shared `agent` queue.
- `node_run.json` is written by the DrawAI runner, not by the node implementation or Agent.
- Partial rerun supports both "rerun from this node to Output" and advanced "rerun this node only"; single-node rerun marks downstream nodes stale.

## Current Repo Context

The current v2 surface is:

```text
prepare
parse_elements
fuse_elements
refine_elements
plan_assets
process_assets
compose_svg
export
package_run
```

Useful existing foundations:

- `drawai.core.DagRunner`, `StageSpec`, `RunContext`, and `ArtifactStore` already provide a simple DAG execution substrate.
- `drawai.v2.schema` defines element candidates, element plans, asset packages, and run packages.
- `drawai.v2.parsers`, `drawai.v2.fusion`, `drawai.v2.processors`, and `drawai.v2.stages` already separate parser, fusion, processor, refine, compose, export, and package responsibilities.
- Workbench already has generated/process tabs, batch/case management, v2 assets table/canvas, package inspection, and runtime activity status.
- Current v2 builder still emits a fixed stage list and hard-coded dependencies. This design replaces that authority with workflow JSON plus typed node contracts.

## Workflow Template Model

Workflow templates are JSON documents, edited visually in Workbench.

Each template contains:

- `schema`: workflow template schema id.
- `template_id`, `name`, `description`, `version`.
- `nodes`: node instances with type, position, config, input/output type declarations, and UI metadata.
- `edges`: connections between node ports.
- `defaults`: run-time defaults such as selected Agent provider overrides.
- `created_at`, `updated_at`, and template provenance.

The built-in default template is provided by code and is read-only. Custom templates live under ignored local Workbench state. A Workbench setting records the user's default template id.

## Node Model

Every node has declared `input_types` and `output_types`.

Connection compatibility is determined by type intersection:

- If an upstream output type has no intersection with the downstream input type, the edge is invalid.
- Compatibility is not hard-coded as product rules like "Parser cannot connect to PPT Export"; it follows type contracts.
- Before saving, the whole workflow is validated so every required node input is satisfied.
- Ports declare cardinality. A `single` input can consume one artifact of a type. A `many` input can consume multiple artifacts.
- If two upstream nodes produce the same type and connect to a downstream `single` input, the workflow is invalid unless the user inserts a Merge/Fusion node or disables/removes one of those edge outputs.

Format contracts do not encode source provenance. For example, an original image is an `image` format with a role or description of "source image"; it is not a separate `source_image` format. Provenance and meaning live in file descriptions and node metadata.

## Fixed Nodes

Fixed nodes have deterministic code-owned input/output contracts and storage rules. They may expose config, but their file protocols are not prompt-defined.

Initial fixed node families:

- `Input`
  - Outputs image files and source metadata roles.
- `Parser`
  - Examples: SAM, OCR, future parser adapters.
  - Outputs typed candidate JSON such as `drawai.element_candidates.v1`.
- `Merge / Fusion`
  - Combines multiple compatible inputs, such as parser candidates.
  - Outputs unified or fused formats for downstream nodes.
- `Processor`
  - Examples: crop, background removal, image generation/edit processor wrappers, chart rebuild when implemented.
  - Produces asset packages, images, editable payloads, or declared processor output formats.
- `Export`
  - Examples: SVG to PPTX.
  - Consumes specific output formats such as semantic SVG and produces deliverable formats.
- `Output`
  - Collects deliverable outputs.
  - Writes final output metadata into `drawai_package.json`.
  - Lets the user hide deliverables from the default output list while preserving all artifacts in the run package.

## Agent Nodes

`AgentNode` is a single generic node class. Run0 element refinement and SVG generation are both AgentNode presets.

An AgentNode instance defines:

- `provider_id`, such as `codex_sdk`, `codex_cli`, or `kimi_cli`.
- Safe provider overrides, such as model/profile/timeout/reasoning effort.
- Input sources derived from connected upstream nodes.
- Input file filters and user-editable file descriptions.
- Prompt fragments, including task instructions and output constraints.
- Output declarations: filename, type, format id, deliverable flag, and basic validation requirements.
- A rendered final prompt preview in the Workbench property panel.

AgentNode itself does not have fixed standard input/output formats in the registry. Each Agent node instance dynamically declares the types it accepts and produces. Its prompt instructs the provider to produce the declared outputs, and the runner validates the files afterward.

Agent node presets can be provided by the system and saved by users. Future presets may include image generation, image editing, chart interpretation, OCR-like extraction, or other Agent tasks. An Agent node that replaces OCR can declare output type `element_candidates` and format `drawai.element_candidates.v1`, making it consumable by Fusion.

## Type And Format Registry

Types describe graph compatibility. Formats describe file validation.

Example:

```text
type: element_candidates
format_id: drawai.element_candidates.v1
media_type: application/json
cardinality: many
description: Unified element candidate JSON accepted by Fusion.
```

Initial built-in formats:

- `drawai.image.v1`
- `drawai.element_candidates.v1`
- `drawai.element_plans.v1`
- `drawai.asset_package.v1`
- `drawai.asset_packages.v1`
- `drawai.semantic_svg.v1`
- `drawai.pptx.v1`
- `drawai.final_outputs.v1`

Built-in formats receive strong validation. For example, `drawai.element_candidates.v1` validates required candidate fields, bounding boxes, type fields, and JSON shape. `drawai.semantic_svg.v1` validates that the SVG parses and has an SVG root. Custom formats receive basic validation such as file existence, JSON parseability, XML parseability, image openability, or PPTX package readability.

## Run Layout

Recommended run layout:

```text
case_root/
  workflow_snapshot.json
  drawai_package.json
  inputs/
    figure.png
    original.png
  nodes/
    sam_parser/runs/001/
      input_manifest.json
      output/
        candidates.json
      stdout.log
      stderr.log
      node_run.json
    run0_agent/runs/001/
      input_manifest.json
      prompt.md
      output/
        elements.json
      stdout.log
      stderr.log
      node_run.json
    svg_agent/runs/001/
      input_manifest.json
      prompt.md
      output/
        semantic.svg
      stdout.log
      stderr.log
      node_run.json
    svg_to_ppt/runs/001/
      input_manifest.json
      output/
        deck.pptx
      node_run.json
  svg/
    semantic.svg
  exports/
    deck.pptx
```

The `nodes/.../output` files are canonical. Compatibility mirrors are generated or refreshed from canonical outputs for existing Workbench, CLI, and external integrations.

## Node Run Manifest

The runner writes `node_run.json` for every attempt.

Required fields:

- `node_id`
- `node_type`
- `attempt_id`
- `status`
- `workdir`
- `provider_id` or resource id when applicable
- `inputs`
- `outputs`
- `prompt_path` when applicable
- `stdout_path`
- `stderr_path`
- `started_at`
- `ended_at`
- `duration_ms`
- `exit_code`
- `error`
- `stale_reason` when applicable

The runner writes `status: running` before execution and then updates the manifest to `ok`, `failed`, `blocked`, or `stale`. Node implementations and external Agents must not write this manifest.

## Execution And Scheduling

The workflow runner:

- Validates the workflow snapshot before running.
- Resolves all connected input files into per-node `input_manifest.json`.
- Runs nodes in topological order with automatic parallelism when dependencies allow.
- Uses global resource/provider pools shared across all runs and workflows.
- Marks downstream nodes blocked when an upstream required output fails.
- Writes package metadata and compatibility mirrors only after outputs validate.

Resource pools include fixed processors and parser resources such as:

```text
sam3
ocr
rmbg
svg_to_ppt
```

Agent resources are keyed by provider:

```text
codex_sdk
codex_cli
kimi_cli
```

This preserves concurrency limits across different batches and different DAG templates.

## Rerun Semantics

Workbench exposes two rerun modes:

- Default: rerun from selected node to `Output`.
- Advanced: rerun selected node only.

The default rerun invalidates the selected node and downstream nodes, then runs until Output. Advanced single-node rerun writes a new attempt for that node and marks downstream outputs stale until a downstream rerun occurs.

## Workbench UI

Top-level tabs:

```text
生成 | 处理 | Workflow
```

The `Workflow` tab layout:

- Left: template library and node library.
- Center: React Flow canvas with drag/drop, free positioning, edge creation, zoom, pan, and minimap.
- Right: property panel for selected template, node, edge, or output.
- Top actions: save, save as, copy built-in template, set as default, validate, restore from built-in.

The property panel:

- Fixed nodes show config, input types, output types, format contracts, and storage rules.
- Agent nodes show provider selection, safe overrides, connected input file list, file descriptions, prompt fragments, final rendered prompt, output declarations, and validation settings.
- Edges show which output types are passed through and allow disabling/removing specific formats when needed.
- Output node shows automatically collected deliverables with show/hide toggles.

The processing page:

- Lets the user bind a workflow template to an unstarted batch.
- Starts the task with the selected template.
- Does not edit templates.

The case detail view:

- Can open a Workflow Run View for the stored snapshot.
- Shows node status, attempts, input manifests, output files, actual prompt, logs, and `node_run.json`.
- Supports rerun controls.

## CLI And API Surface

CLI must support:

- Listing workflow templates.
- Validating a workflow JSON file.
- Running a case or image with a selected workflow template.
- Running with the built-in default template.
- Rerunning from a selected node to Output.
- Inspecting node runs and node outputs.

Workbench API must support:

- Template list, read, save, copy built-in, delete custom, set default.
- Workflow validation.
- Batch workflow binding before run.
- Case workflow snapshot retrieval.
- Node run inspection.
- Rerun actions.

## Migration Strategy

Existing v2 concepts become default workflow nodes:

- `parse_elements` becomes SAM/OCR parser nodes plus compatible parser presets.
- `fuse_elements` becomes a Fusion node.
- `refine_elements` becomes a Run0 Agent node preset.
- `plan_assets` and `process_assets` become fixed planner/processor nodes.
- `compose_svg` becomes an SVG Agent node preset.
- `export` becomes SVG-to-PPT Export node.
- `package_run` becomes internal Output/package finalization logic.

Legacy read-only behavior remains unchanged. Historical non-DAG runs stay viewable and downloadable but are not retroactively migrated into editable DAG snapshots.

## Testing And Acceptance

This feature must not be accepted with static UI checks alone. It requires CLI execution, Workbench browser execution, provider coverage, workflow variation tests, and comparison against the v1 pipeline. In this document, v1 means the legacy pre-v2 DrawAI public path that runs structure/text detection, BoxIR assembly, asset materialization, SVG generation, and export without the new workflow DAG snapshot.

### Unit And Contract Tests

Required coverage:

- Workflow JSON schema validation.
- Cycle detection.
- Required input satisfaction.
- Input/output type compatibility.
- Single and many input cardinality.
- Edge-level output filtering.
- Invalid multiple same-type outputs into single input.
- Merge/Fusion resolving multiple compatible inputs.
- Built-in format strong validation.
- Custom format basic validation.
- Runner-owned `node_run.json`.
- Canonical node output path resolution and path traversal rejection.
- Compatibility mirror generation from canonical node outputs.

### CLI End-To-End Tests

Required CLI scenarios:

- Run the built-in default workflow on a real fixture image.
- Run Agent nodes with `codex_sdk`.
- Run Agent nodes with `kimi_cli`.
- Produce SVG and PPTX deliverables.
- Verify `workflow_snapshot.json`, node workdirs, `node_run.json`, logs, actual prompts, final outputs, and compatibility mirrors.
- Compare output to the v1 pipeline on the same input.

The v1 comparison should not require pixel-perfect identity, but results should be materially close:

- Element count and major bounding box distribution are close.
- Key OCR text is preserved or has an explainable substitute.
- SVG renders successfully.
- PPTX exports and passes package checks.
- The final output is not a full-slide raster fallback.

Required workflow variants:

- Default workflow.
- Workflow without OCR node.
- Workflow where an Agent node acts as OCR-like extractor and outputs `drawai.element_candidates.v1`.
- Workflow where an Agent node is inserted between SAM and Fusion and preserves `drawai.element_candidates.v1`.
- Workflow where SVG Agent output feeds SVG-to-PPT and both feed Output.

### Workbench Browser Tests

Required Workbench scenarios, using browser automation against a real local Workbench:

- Open `Workflow` tab.
- Copy built-in template.
- Edit template on the React Flow canvas.
- Save custom template to local ignored workflow storage.
- Set custom template as default.
- Bind a workflow template to an unstarted batch from the processing page.
- Start the batch and observe node execution.
- Inspect Workflow Run View.
- Verify node status, input manifest, actual rendered prompt, output files, logs, and `node_run.json`.
- Verify Output node lists SVG and PPTX deliverables and respects hidden deliverables.
- Rerun from a failed or selected node to Output.
- Rerun a single node and verify downstream nodes are marked stale.

Browser verification should use the available browser plugin or Playwright control for the actual local page, not a static HTML mock.

### Provider And Resource Tests

Required scenarios:

- `codex_sdk` Agent provider executes at least one Agent node.
- `kimi_cli` Agent provider executes at least one Agent node.
- Provider queues are tracked separately.
- Multiple concurrent runs using different workflows share global resource/provider limits.
- Workbench runtime activity shows queued/running counts by resource/provider.

### Manual Review Criteria

Before implementation is called complete:

- Run one real CLI workflow with Codex SDK.
- Run one real CLI workflow with Kimi CLI.
- Run one real Workbench workflow through the browser.
- Run at least one modified workflow, such as no OCR or Agent-as-OCR.
- Compare results to v1 on the same input and document the observed differences.

## Non-Goals For First Implementation

- Cloud template marketplace.
- Collaborative multi-user workflow editing.
- Full migration of legacy read-only runs into editable DAG snapshots.
- Pixel-perfect equivalence with v1.
- Arbitrary shell commands inside Agent node definitions.
- Treating all Agent providers as one shared queue.

## Implementation Notes

- Prefer existing DrawAI schemas, validators, artifact store, and provider patterns where possible.
- Keep node contracts small and explicit; avoid adding a generic untyped file graph.
- Use Workbench visual editing for custom templates; JSON is the durable machine format.
- Keep user workflow files in ignored local state.
- Make actual prompt rendering inspectable for every Agent node.
- Preserve compatibility downloads while making node outputs canonical.
