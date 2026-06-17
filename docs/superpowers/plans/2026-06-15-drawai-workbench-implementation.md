# DrawAI Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and locally deploy a batch-first DrawAI workbench with FastAPI job APIs and a React canvas asset editor.

**Architecture:** Add a repo-integrated `drawai.workbench` backend package that wraps existing DrawAI stage functions, stores job state in SQLite, writes workbench artifacts under each case root, and exposes polling APIs. Add a separate Vite/React frontend under `apps/workbench` with batch queue, case workspace, canvas-first asset editing, SVG compare, and logs views.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, SQLite stdlib, existing DrawAI pipeline modules, React, TypeScript, Vite, plain CSS, pytest, FastAPI TestClient.

---

## File Structure

- Create `src/drawai/workbench/__init__.py`: package exports.
- Create `src/drawai/workbench/models.py`: enums, dataclasses, and response helpers shared by API/store/runner.
- Create `src/drawai/workbench/store.py`: SQLite schema, batch/case/stage persistence, artifact token resolution, JSON artifact helpers.
- Create `src/drawai/workbench/assets.py`: convert run0 analysis to draft, validate drafts, approve asset plans, materialize approved raster assets.
- Create `src/drawai/workbench/runner.py`: in-process queue, resource semaphores, real DrawAI stage execution, rerun invalidation.
- Create `src/drawai/workbench/api.py`: FastAPI app, routes, CORS, artifact serving, CLI entrypoint.
- Modify `pyproject.toml`: add FastAPI/Uvicorn/python-multipart/httpx dependencies and `drawai-workbench-api` script.
- Create `tests/workbench/test_assets.py`: asset draft validation and approved materialization.
- Create `tests/workbench/test_store_api.py`: API/job/store behavior with deterministic lightweight stage executor.
- Create `apps/workbench/package.json`: frontend scripts and dependencies.
- Create `apps/workbench/index.html`, `apps/workbench/tsconfig.json`, `apps/workbench/vite.config.ts`: Vite setup.
- Create `apps/workbench/src/main.tsx`, `apps/workbench/src/App.tsx`, `apps/workbench/src/api.ts`, `apps/workbench/src/types.ts`, `apps/workbench/src/styles.css`: workbench UI and canvas editor.

## Task 1: Backend Types And Store

**Files:**
- Create: `src/drawai/workbench/models.py`
- Create: `src/drawai/workbench/store.py`
- Test: `tests/workbench/test_store_api.py`

- [ ] **Step 1: Write store/API persistence tests**

Create tests that initialize a temporary `WorkbenchStore`, create a batch and case, update statuses, store an artifact token, and verify path traversal is rejected.

- [ ] **Step 2: Implement models and SQLite store**

Implement status enums, dataclass-to-dict helpers, SQLite schema creation, CRUD methods, and artifact token generation with path containment checks.

- [ ] **Step 3: Run backend store tests**

Run: `PYTHONPATH=src uv run pytest tests/workbench/test_store_api.py -q`

Expected: store-related tests pass.

## Task 2: Asset Draft And Approval Contract

**Files:**
- Create: `src/drawai/workbench/assets.py`
- Test: `tests/workbench/test_assets.py`

- [ ] **Step 1: Write asset contract tests**

Create tests for converting `element_analysis.json` into `asset_draft.json`, validating bbox/source strategy, writing `approved_asset_plan.json`, and materializing `crop` assets from a tiny real image.

- [ ] **Step 2: Implement asset helpers**

Implement `draft_from_run0_analysis`, `validate_asset_plan`, `write_asset_draft`, `approve_asset_plan`, and compatibility conversion from `source_strategy` to the existing `category` field expected by `materialize_run0_refined_assets`.

- [ ] **Step 3: Run asset tests**

Run: `PYTHONPATH=src uv run pytest tests/workbench/test_assets.py -q`

Expected: asset contract tests pass with real PIL-generated images and real crop files.

## Task 3: Job Runner And Stage Execution

**Files:**
- Create: `src/drawai/workbench/runner.py`
- Modify: `tests/workbench/test_store_api.py`

- [ ] **Step 1: Write runner tests with deterministic stage executor**

Add tests that submit two cases, verify case-level concurrency, verify analysis writes a draft, verify approval triggers reconstruction when requested, and verify rerun invalidates downstream state.

- [ ] **Step 2: Implement `WorkbenchRunner`**

Implement a thread-pool-backed runner that creates per-case config files, calls existing DrawAI public stages for real execution, supports a deterministic executor injection for tests, and records stage runs.

- [ ] **Step 3: Run runner tests**

Run: `PYTHONPATH=src uv run pytest tests/workbench/test_store_api.py -q`

Expected: store/API/runner tests pass.

## Task 4: FastAPI App

**Files:**
- Create: `src/drawai/workbench/api.py`
- Modify: `pyproject.toml`
- Modify: `tests/workbench/test_store_api.py`

- [ ] **Step 1: Write API tests**

Add tests for `POST /api/batches`, polling `GET /api/batches/{id}`, `GET /api/cases/{id}`, `PATCH /asset-draft`, `POST /approve-assets`, `POST /run-stage`, and artifact route containment.

- [ ] **Step 2: Implement FastAPI routes**

Implement invite-code validation, upload/local_dir input handling, batch creation, polling endpoints, asset draft saves, approve/rerun actions, and authorized artifact serving.

- [ ] **Step 3: Run API tests**

Run: `PYTHONPATH=src uv run pytest tests/workbench/test_store_api.py -q`

Expected: API tests pass.

## Task 5: React Workbench

**Files:**
- Create: `apps/workbench/package.json`
- Create: `apps/workbench/index.html`
- Create: `apps/workbench/tsconfig.json`
- Create: `apps/workbench/vite.config.ts`
- Create: `apps/workbench/src/main.tsx`
- Create: `apps/workbench/src/App.tsx`
- Create: `apps/workbench/src/api.ts`
- Create: `apps/workbench/src/types.ts`
- Create: `apps/workbench/src/styles.css`

- [ ] **Step 1: Scaffold frontend files**

Create a Vite/React app without sample marketing pages. First screen is the actual workbench: left batch queue, center case workspace, right inspector.

- [ ] **Step 2: Implement canvas editor**

Implement image overlay boxes with select, drag, resize, add box, delete, source strategy controls, role editing, hover labels, save draft, and approve actions.

- [ ] **Step 3: Implement SVG compare and logs tabs**

Render original and SVG/artifact panes, stage summaries, validation status, and raw JSON/log links.

- [ ] **Step 4: Run frontend build**

Run: `cd apps/workbench && npm install && npm run build`

Expected: Vite production build succeeds.

## Task 6: Local Deployment Verification

**Files:**
- Modify: `README.md` or create focused docs only if needed for run commands.

- [ ] **Step 1: Run focused backend tests**

Run: `PYTHONPATH=src uv run pytest tests/workbench -q`

Expected: all workbench tests pass.

- [ ] **Step 2: Run focused existing regression tests**

Run: `PYTHONPATH=src uv run pytest tests/semantic_ppt/drawai_pipeline/test_public_stages.py tests/semantic_ppt/drawai_pipeline/test_asset_selection.py -q`

Expected: existing pipeline boundary tests still pass.

- [ ] **Step 3: Start local API**

Run: `DRAWAI_WORKBENCH_INVITE_CODES=local-dev uv run drawai-workbench-api --host 127.0.0.1 --port 8890 --workspace .local/workbench`

Expected: `/api/health` returns ok.

- [ ] **Step 4: Start local frontend**

Run: `cd apps/workbench && npm run dev -- --host 127.0.0.1 --port 5174`

Expected: Vite serves the workbench and proxies API calls.

- [ ] **Step 5: Browser smoke**

Open `http://127.0.0.1:5174`, verify the workbench loads, health status is visible, and the New Batch panel is usable.

## Task 7: Commit And Push

**Files:**
- Stage all implementation files.

- [ ] **Step 1: Inspect git diff**

Run: `git diff --stat` and `git diff --cached --stat`.

- [ ] **Step 2: Commit**

Run: `git commit -m "feat: add DrawAI workbench service"`

- [ ] **Step 3: Push**

Run: `git push`

