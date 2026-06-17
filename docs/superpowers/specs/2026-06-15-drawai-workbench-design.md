# DrawAI Workbench Design

Date: 2026-06-15

## Purpose

Build a DrawAI workbench for batch image-to-editable-SVG/PPTX processing. The
service supports both self-hosted local usage and a simple cloud test service.
It exposes the existing DrawAI pipeline as a task-based web application where
users can review and edit asset analysis before running SVG reconstruction.

The frontend should take product inspiration from Open Design's local-first,
artifact-first workspace style, but DrawAI will not integrate Open Design's
runtime, daemon, or skills.

## Confirmed Decisions

- Architecture: repo-integrated FastAPI backend plus React/Vite frontend.
- Scope: batch-first, with a job list and per-case detail workspace.
- Inputs:
  - self-hosted: browser upload, zip upload, and server-local directory path.
  - cloud: browser upload or zip upload only.
- Access control: invite code only for the first service version.
- Asset editing: canvas-first. Users drag, resize, add, select, merge, split,
  and delete boxes on the original image; numeric bbox editing is an advanced
  inspector option.
- Asset source strategies: `svg_self_draw`, `crop`, and `crop_nobg`.
- Asset semantic role/type remains editable metadata, separate from source
  strategy.
- A batch may stop after asset analysis for manual review or auto-run through
  SVG/PPTX after analysis.
- Stage reruns are required: users can rerun run0/asset analysis, asset
  materialization, SVG reconstruction, or export.
- No multi-version asset rollback UI is required. The service keeps a current
  draft and one approved asset plan.

## High-Level Architecture

```text
apps/workbench/       React/Vite frontend
apps/api/             FastAPI backend and job API
src/drawai/           Existing DrawAI pipeline, stages, providers, SVG/PPTX logic
workspace/runs/       Job artifacts and case run roots
workspace/drawai.db   SQLite job registry for the first version
```

The backend must not move pipeline business logic into API handlers. API
handlers validate requests and enqueue work. A service layer maps job requests
to existing DrawAI stage functions and file-backed artifacts.

The pipeline remains artifact-backed. SQLite indexes batches, cases, stage
runs, configs, invite usage, and artifact locations, but artifact files remain
the source of truth.

## Pipeline Shape

The workbench exposes two user-visible phases.

```text
Phase 1: Analysis
prepare
  -> detect_structure
  -> detect_text
  -> assemble_boxir
  -> asset_plan
  -> asset_analyze

Checkpoint
run0_analysis -> asset_draft -> approved_asset_plan -> asset_materialize

Phase 2: Reconstruction
approved_asset_plan
  -> materialize approved assets
  -> svg/run1 + refine loop
  -> export PPTX export
```

The checkpoint is a hard contract. Phase 2 uses the approved asset plan, not
the raw run0 output, as its primary asset/source strategy input.

## Backend Job Model

### BatchJob

Represents one batch submission. It stores:

- `batch_id`
- input mode: `upload`, `zip`, or `local_dir`
- normalized job config snapshot
- requested `max_concurrent_cases`
- `auto_run_svg_after_analysis`
- status summary: queued, running, waiting_review, completed, failed, canceled
- aggregate counts for cases and stages

### CaseJob

Represents one image. It stores:

- `case_id`
- parent `batch_id`
- case run root
- current phase and stage
- current status
- latest error summary and error artifact path
- artifact manifest path

### StageRun

Represents one concrete stage execution. It stores:

- `stage_run_id`
- `case_id`
- stage name
- attempt number
- status
- started/ended timestamps
- log paths
- input/output artifact paths
- failure detail, if any

### AssetDraft And ApprovedAssetPlan

`AssetDraft` is overwritten whenever the user saves canvas edits.
`ApprovedAssetPlan` is written when the user approves a case or a batch auto-run
checkpoint approves it.

The service does not expose rollback UI, but it should append edit events to a
light audit log so failures can be debugged.

## Queue And Concurrency

The first implementation uses an in-process worker pool suitable for one
FastAPI process. This is enough for local/self-hosted usage and a small cloud
test service.

Concurrency has two levels:

- Case-level limit: `max_concurrent_cases`.
- Resource-level semaphores:
  - SAM
  - OCR
  - Codex/run0 and SVG generation
  - RMBG
  - export/PPTX

This avoids the common failure mode where a global "5 workers" setting starts
too many heavyweight model or Codex operations at once.

The job model should be compatible with replacing the in-process queue later
with Redis/RQ/Celery/Arq without changing the public API.

## API Design

The first API is polling-based.

```text
POST   /api/batches
GET    /api/batches/{batch_id}
GET    /api/batches/{batch_id}/cases

GET    /api/cases/{case_id}
GET    /api/cases/{case_id}/artifacts
GET    /api/cases/{case_id}/assets
PATCH  /api/cases/{case_id}/asset-draft
POST   /api/cases/{case_id}/approve-assets
POST   /api/cases/{case_id}/run-stage
POST   /api/cases/{case_id}/cancel
POST   /api/cases/{case_id}/retry

GET    /api/artifacts/{artifact_token}
```

The frontend polls batch and case endpoints. Server-sent events or WebSocket
updates can be added later without changing the job state model.

## Artifact Contract

Every case run root keeps existing DrawAI outputs and adds workbench files.

```text
reports/workbench/
  asset_draft.json
  approved_asset_plan.json
  edit_history.jsonl
  workbench_manifest.json
```

`asset_draft.json` and `approved_asset_plan.json` use the same element shape:

```json
{
  "schema": "drawai.workbench_asset_plan.v1",
  "case_id": "case id",
  "source": "run0|user_edit|auto_approved",
  "elements": [
    {
      "box_id": "B012",
      "source_candidate_ids": ["B012"],
      "bbox": [10, 20, 100, 160],
      "source_strategy": "svg_self_draw",
      "visual_role": "arrow",
      "type": "arrow",
      "confidence": "high",
      "reason": "short reason",
      "evidence": ["short evidence item"]
    }
  ]
}
```

The approved plan must validate:

- every bbox is finite and has positive area
- every `source_strategy` is one of `svg_self_draw`, `crop`, `crop_nobg`
- original run0 candidates remain covered unless explicitly replaced by added
  or split elements
- element ids are unique
- new ids are stable and short

After approval, the backend uses the approved plan to regenerate
`svg_to_ppt/assets/asset_manifest.json` through the same materialization path
used by run0 refined assets. The SVG stage then treats the approved asset plan
and regenerated asset manifest as its primary structured inputs.

## Frontend Information Architecture

The workbench has three persistent regions.

### Left: Batch And Case Queue

Shows:

- batch list and active batch
- case list with status
- aggregate progress
- failure and review filters
- batch controls: pause, retry failed, auto-run SVG, max concurrency

### Center: Case Workspace

Tabs:

- `Overview`: current image, stage status, key artifacts, next action
- `Canvas Edit`: primary asset editing surface
- `Asset Table`: dense table for filtering, sorting, and batch edits
- `SVG Compare`: original versus SVG outputs
- `Logs`: stage logs, Codex traces, validation reports, session logs

### Right: Inspector

Shows selected asset details:

- selected asset id
- source strategy segmented control
- visual role/type
- confidence and reason
- crop/no-background crop preview
- advanced bbox numeric fields in a collapsed section
- save draft and approve controls

## Canvas Edit Behavior

The canvas overlays editable bboxes on the original image.

Required interactions:

- select asset
- drag selected bbox
- resize using corner and edge handles
- draw new bbox in Add Box mode
- delete selected assets
- multi-select assets
- merge selected assets
- split by duplicating an asset into child boxes that the user can resize
- change source strategy from canvas toolbar or inspector
- filter visible overlays by source strategy or role
- hover to show `box_id`, source strategy, visual role/type, confidence, and
  reason

The canvas should preserve image coordinate accuracy. All edits are saved in
image pixel coordinates, not screen coordinates.

## SVG Compare Behavior

The compare tab shows:

- original image
- final SVG directly rendered in the browser where possible
- optional rendered PNG if browser SVG display differs from validation render
- selectable stages: `semantic_0`, `semantic_1`, `semantic_2`, `semantic_3`,
  `final`
- validation status and PPTX export status
- iteration log summary
- hover information for SVG elements when ids or manifest mappings are
  available

The original and SVG panes should keep matched height and zoom controls.

## Stage Rerun Semantics

Stage reruns must invalidate downstream outputs.

Examples:

- Rerun run0 asset analysis invalidates workbench draft, approved plan, asset
  manifest, SVG, render, and export unless the user explicitly preserves the
  draft by reapplying it.
- Editing and approving assets invalidates SVG and export.
- Rerun SVG invalidates export.
- Rerun export keeps approved assets and SVG.

The UI must display when a downstream artifact is stale relative to the latest
approved asset plan.

## Deployment Profiles

### Self-Hosted

- Local filesystem artifact storage.
- Optional invite code.
- Allows server-local directory input.
- Suitable for local batch processing and research workflows.
- Can use local SAM/OCR/RMBG runtimes.

### Cloud Test Service

- Invite code required.
- Allows upload and zip input only.
- No arbitrary server path input.
- Artifact download goes through authorized API routes.
- Job/case ids are random and unguessable.
- Server paths are never exposed directly to the browser.
- Uses isolated case run roots for Codex sandbox cwd.

## Security And Isolation

- Do not expose local absolute paths in frontend URLs.
- Serve artifacts through backend authorization routes.
- Codex sandbox cwd should be the case run root, not the repository root or
  user home.
- Keep invite code validation at job creation and use a signed batch/case token
  for artifact reads.
- Store session logs and usage data, but show summaries by default.
- Reject SVG/PPT artifact routes that resolve outside the case run root.

## Observability

The UI should make these files easy to inspect:

- `reports/pipeline_summary.json`
- `reports/stage_io_manifest.json`
- `reports/stage_status.json`
- `reports/element_analysis_codex/element_analysis.json`
- `reports/workbench/asset_draft.json`
- `reports/workbench/approved_asset_plan.json`
- `svg_to_ppt/assets/asset_manifest.json`
- `svg/semantic.svg`
- `svg/rendered.png`
- `reports/svg_validation_report.json`
- `reports/svg_to_ppt_export_report.json`
- Codex session logs and trace files

Each stage failure should persist:

- status
- exception type
- concise message
- stderr/stdout tail when subprocesses are involved
- paths to detailed logs

## Testing Strategy

Backend tests:

- create batch from upload and local directory
- invite code validation
- job polling response shapes
- asset draft validation
- approve asset plan and materialize approved assets
- stage rerun invalidation rules
- artifact route path traversal rejection
- resource semaphore behavior with deterministic lightweight test stage runners

Frontend tests:

- batch list renders and polls
- canvas loads original image and overlays
- drag/resize/add box writes correct image pixel coordinates
- source strategy and visual role edits save draft
- approve case calls the expected API
- SVG compare renders original and SVG panes at matched height
- stale downstream artifact warnings appear

Integration smoke:

- run one real image through analysis
- edit one asset strategy and approve
- run reconstruction from approved assets
- verify `semantic.svg`, `rendered.png`, validation report, and optional PPTX
  export report exist

## Acceptance Criteria

- A user can submit a batch and immediately receives a `batch_id`.
- The frontend can poll batch and case status.
- Phase 1 produces run0 asset analysis and opens it in Canvas Edit.
- The user can drag, resize, and add asset boxes on the original image.
- The user can change asset source strategy and visual role.
- Approving assets writes `approved_asset_plan.json`.
- Phase 2 uses the approved plan and regenerated asset manifest.
- The user can rerun analysis, SVG, or export from the UI.
- Failed cases preserve logs and can be retried without losing successful cases.
- The same design supports self-hosted local paths and cloud uploads with
  different config profiles.

## Out Of Scope For First Implementation

- Full account system.
- Multi-user collaboration.
- Version-history UI for asset edits.
- Cloud object storage and Postgres as required dependencies.
- Open Design daemon/runtime integration.
- Real-time WebSocket updates as the only status channel.
