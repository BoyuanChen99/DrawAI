# Workbench Status Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only Workbench settings overview that summarizes runtime, model, Agent, LLM, processor, and key capability readiness, with actions that jump to existing settings pages.

**Architecture:** Add a backend `status_overview` module that turns current Workbench settings and runtime probes into a normalized status payload. The frontend adds an `overview` settings category, loads the new endpoint with existing settings calls, renders compact status groups and issue rows, and reuses existing settings navigation/edit helpers for actions.

**Tech Stack:** Python 3.12, FastAPI, pytest, React 19, TypeScript, Vite, existing DrawAI Workbench settings APIs.

---

### Task 1: Backend Status Overview API

**Files:**
- Create: `src/drawai/workbench/status_overview.py`
- Modify: `src/drawai/workbench/agent_settings.py`
- Modify: `src/drawai/workbench/api.py`
- Test: `tests/workbench/test_store_api.py`

- [ ] **Step 1: Write failing API tests**

Add tests near the existing `/api/health` tests in `tests/workbench/test_store_api.py`:

```python
def test_api_status_overview_reports_ready_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = WorkbenchStore(tmp_path / "workspace")
    base_config = _base_config(tmp_path)
    settings = _settings(tmp_path, base_config)
    _write_json(
        store.workspace / "settings" / "api_presets.json",
        {
            "schema": "drawai.workbench.api_presets.v1",
            "presets": [
                {
                    "id": "openai_images",
                    "label": "OpenAI Images",
                    "type": "images_api",
                    "base_url": "https://api.openai.com",
                    "model": "gpt-image-2",
                    "api_key_env": "OPENAI_API_KEY",
                    "api_key": "",
                },
                {
                    "id": "openai_llm",
                    "label": "OpenAI LLM",
                    "type": "llm_responses",
                    "base_url": "https://api.openai.com",
                    "model": "gpt-5",
                    "api_key_env": "OPENAI_API_KEY",
                    "api_key": "",
                },
            ],
        },
    )
    _write_json(
        store.workspace / "settings" / "agent.json",
        {
            "schema": "drawai.workbench.agent_settings.v1",
            "selected_provider_id": "codex_sdk",
            "model": "",
            "reasoning_effort": "",
            "timeout_seconds": 0,
            "llm_model": "gpt-5",
            "llm_base_url": "https://api.openai.com",
            "llm_api_key": "",
            "llm_api_key_env": "OPENAI_API_KEY",
            "llm_wire_api": "responses",
            "llm_extra_body": {},
        },
    )
    _write_json(
        store.workspace / "settings" / "processor.json",
        {
            "schema": "drawai.workbench.processor_settings.v1",
            "processors": {
                "image_generate": {
                    "enabled": True,
                    "driver_id": "openai_images_api",
                    "api_preset_id": "openai_images",
                    "operation": {
                        "meaning": "Generate image assets.",
                        "choose_when": "Choose when an element needs generated pixels.",
                        "avoid_when": "Avoid when source pixels can be cropped.",
                    },
                },
                "image_edit": {
                    "enabled": True,
                    "driver_id": "openai_images_api",
                    "api_preset_id": "openai_images",
                    "operation": {
                        "meaning": "Edit image assets.",
                        "choose_when": "Choose when an element needs edited pixels.",
                        "avoid_when": "Avoid when source pixels can be cropped.",
                    },
                },
            },
        },
    )
    monkeypatch.setattr(
        "drawai.workbench.status_overview.discover_workbench_agent",
        lambda provider_id: {
            "provider_id": provider_id,
            "label": "Codex SDK",
            "kind": "sdk",
            "available": True,
            "status": "ok",
            "detail": "ok",
            "fix": "",
            "auth": {"available": True, "detail": "ok"},
        },
    )
    app = create_app(
        settings,
        store=store,
        runner=WorkbenchRunner(store, settings),
        runtime_probe=lambda name, base_url: {
            "name": name,
            "base_url": base_url,
            "health_url": f"{base_url}/health",
            "status": "online",
        },
    )
    client = TestClient(app)

    response = client.get("/api/workbench/status-overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "drawai.workbench.status_overview.v1"
    assert payload["overall"]["severity"] == "ok"
    assert payload["overall"]["error_count"] == 0
    assert payload["overall"]["warning_count"] == 0
    assert payload["issues"] == []


def test_api_status_overview_reports_runtime_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = WorkbenchStore(tmp_path / "workspace")
    base_config = _base_config(tmp_path)
    settings = _settings(tmp_path, base_config)
    monkeypatch.setattr(
        "drawai.workbench.status_overview.discover_workbench_agent",
        lambda provider_id: {"provider_id": provider_id, "label": "Codex SDK", "available": True, "status": "ok", "auth": {"available": True}},
    )
    app = create_app(
        settings,
        store=store,
        runner=WorkbenchRunner(store, settings),
        runtime_probe=lambda name, base_url: {
            "name": name,
            "base_url": base_url,
            "health_url": f"{base_url}/health",
            "status": "offline" if name == "ocr" else "online",
            "error": "connection refused" if name == "ocr" else "",
        },
    )
    client = TestClient(app)

    response = client.get("/api/workbench/status-overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall"]["severity"] == "error"
    assert any(issue["id"] == "runtime.ocr.offline" for issue in payload["issues"])


def test_api_status_overview_reports_missing_optional_image_capabilities(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = WorkbenchStore(tmp_path / "workspace")
    base_config = _base_config(tmp_path)
    settings = _settings(tmp_path, base_config)
    monkeypatch.setattr(
        "drawai.workbench.status_overview.discover_workbench_agent",
        lambda provider_id: {"provider_id": provider_id, "label": "Codex SDK", "available": True, "status": "ok", "auth": {"available": True}},
    )
    app = create_app(
        settings,
        store=store,
        runner=WorkbenchRunner(store, settings),
        runtime_probe=lambda name, base_url: {"name": name, "base_url": base_url, "health_url": f"{base_url}/health", "status": "online"},
    )
    client = TestClient(app)

    response = client.get("/api/workbench/status-overview")

    assert response.status_code == 200
    payload = response.json()
    issue_ids = {issue["id"] for issue in payload["issues"]}
    assert "capability.image_generate.disabled" in issue_ids
    assert "capability.image_edit.disabled" in issue_ids
    assert payload["overall"]["severity"] == "warning"


def test_api_status_overview_reports_invalid_enabled_processor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = WorkbenchStore(tmp_path / "workspace")
    base_config = _base_config(tmp_path)
    settings = _settings(tmp_path, base_config)
    _write_json(
        store.workspace / "settings" / "processor.json",
        {
            "schema": "drawai.workbench.processor_settings.v1",
            "processors": {
                "image_generate": {
                    "enabled": True,
                    "driver_id": "openai_images_api",
                    "api_preset_id": "",
                    "operation": {
                        "meaning": "Generate image assets.",
                        "choose_when": "Choose when an element needs generated pixels.",
                        "avoid_when": "Avoid when source pixels can be cropped.",
                    },
                }
            },
        },
    )
    monkeypatch.setattr(
        "drawai.workbench.status_overview.discover_workbench_agent",
        lambda provider_id: {"provider_id": provider_id, "label": "Codex SDK", "available": True, "status": "ok", "auth": {"available": True}},
    )
    app = create_app(
        settings,
        store=store,
        runner=WorkbenchRunner(store, settings),
        runtime_probe=lambda name, base_url: {"name": name, "base_url": base_url, "health_url": f"{base_url}/health", "status": "online"},
    )
    client = TestClient(app)

    response = client.get("/api/workbench/status-overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall"]["severity"] == "error"
    assert any(issue["id"] == "settings.processor.invalid" and issue["action"]["target_id"] == "image_generate" for issue in payload["issues"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/workbench/test_store_api.py -k status_overview -v
```

Expected: FAIL because `/api/workbench/status-overview` and `drawai.workbench.status_overview` do not exist yet.

- [ ] **Step 3: Expose focused Agent discovery**

Add this function to `src/drawai/workbench/agent_settings.py` above `discover_workbench_agents()`:

```python
def discover_workbench_agent(provider_id: str) -> dict[str, Any]:
    if provider_id not in AGENT_DEFINITIONS:
        supported = ", ".join(WORKBENCH_SELECTABLE_AGENT_PROVIDER_IDS)
        raise ValueError(f"unsupported Workbench agent provider: {provider_id!r}. Expected one of: {supported}")
    if provider_id not in WORKBENCH_SELECTABLE_AGENT_PROVIDER_IDS:
        supported = ", ".join(WORKBENCH_SELECTABLE_AGENT_PROVIDER_IDS)
        raise ValueError(f"Workbench agent provider is not selectable yet: {provider_id!r}. Expected one of: {supported}")
    return _discover_agent(AGENT_DEFINITIONS[provider_id])
```

Then update `discover_workbench_agents()`:

```python
def discover_workbench_agents() -> list[dict[str, Any]]:
    return [discover_workbench_agent(provider_id) for provider_id in WORKBENCH_SELECTABLE_AGENT_PROVIDER_IDS]
```

- [ ] **Step 4: Implement the overview builder**

Create `src/drawai/workbench/status_overview.py` with helper functions that:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .agent_settings import WorkbenchAgentSettings, discover_workbench_agent, read_workbench_agent_settings
from .api_presets import ApiPreset, api_preset_by_id, read_workbench_api_presets
from .models import WorkbenchSettings
from .processor_settings import (
    PROCESSOR_DEFINITIONS,
    PROCESSOR_DRIVER_DEFINITIONS,
    ProcessorSetting,
    processor_settings_validation,
    read_workbench_processor_settings,
)

STATUS_OVERVIEW_SCHEMA = "drawai.workbench.status_overview.v1"
SEVERITY_ORDER = {"ok": 0, "warning": 1, "error": 2}
BASELINE_PROCESSORS = ("no_process", "crop", "crop_nobg")
CAPABILITY_PROCESSORS = ("image_generate", "image_edit")


def workbench_status_overview_payload(
    workspace: str | Path,
    *,
    settings: WorkbenchSettings,
    runtime_services: Mapping[str, Any],
) -> dict[str, Any]:
    api_presets, api_error = _read_api_presets(workspace)
    agent_settings, agent_error = _read_agent_settings(workspace)
    processor_settings, processor_error = _read_processor_settings(workspace)
    issues: list[dict[str, Any]] = []
    groups = [
        _runtime_group(runtime_services, issues),
        _api_group(api_presets, api_error, issues),
        _agent_group(agent_settings, agent_error, issues),
        _llm_group(agent_settings, api_presets, agent_error, issues),
        _processor_group(processor_settings, processor_error, api_presets, issues),
        _capability_group(processor_settings, processor_error, runtime_services, issues),
    ]
    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    severity = "error" if error_count else "warning" if warning_count else "ok"
    return {
        "schema": STATUS_OVERVIEW_SCHEMA,
        "workspace": str(Path(workspace).expanduser().resolve(strict=False)),
        "cloud_mode": settings.cloud_mode,
        "overall": {
            "severity": severity,
            "label": _overall_label(severity),
            "error_count": error_count,
            "warning_count": warning_count,
        },
        "groups": groups,
        "issues": sorted(issues, key=lambda item: (-SEVERITY_ORDER[item["severity"]], item["id"])),
    }
```

The helper functions should produce concrete `ok`, `warning`, and `error` groups and issues using the rules in the spec.

- [ ] **Step 5: Wire the FastAPI endpoint**

Modify imports in `src/drawai/workbench/api.py`:

```python
from .status_overview import workbench_status_overview_payload
```

Add the route near existing Workbench settings routes:

```python
    @app.get("/api/workbench/status-overview")
    def get_workbench_status_overview_api() -> dict[str, Any]:
        runtime_services = _runtime_services_status(resolved_settings, runtime_probe=runtime_probe)
        return workbench_status_overview_payload(
            resolved_store.workspace,
            settings=resolved_settings,
            runtime_services=runtime_services,
        )
```

- [ ] **Step 6: Run backend tests**

Run:

```bash
uv run pytest tests/workbench/test_store_api.py -k "status_overview or api_health" -v
```

Expected: PASS for new status overview tests and existing health tests.

- [ ] **Step 7: Commit backend API**

Run:

```bash
git add src/drawai/workbench/agent_settings.py src/drawai/workbench/status_overview.py src/drawai/workbench/api.py tests/workbench/test_store_api.py
git commit -m "feat(workbench): add status overview API"
```

### Task 2: Frontend Overview Types, Fetching, and UI

**Files:**
- Modify: `apps/workbench/src/types.ts`
- Modify: `apps/workbench/src/api.ts`
- Modify: `apps/workbench/src/App.tsx`
- Modify: `apps/workbench/src/styles.css`

- [ ] **Step 1: Add TypeScript types**

Add these interfaces to `apps/workbench/src/types.ts`:

```ts
export type WorkbenchOverviewSeverity = "ok" | "warning" | "error";
export type WorkbenchSettingsTargetCategory = "overview" | "api" | "agent" | "llm" | "processor";

export interface WorkbenchStatusOverviewAction {
  label: string;
  category: WorkbenchSettingsTargetCategory;
  target_id: string;
  mode?: string;
}

export interface WorkbenchStatusOverviewIssue {
  id: string;
  severity: WorkbenchOverviewSeverity;
  title: string;
  message: string;
  scope: string;
  action?: WorkbenchStatusOverviewAction;
}

export interface WorkbenchStatusOverviewItem {
  id: string;
  label: string;
  severity: WorkbenchOverviewSeverity;
  value: string;
  detail: string;
}

export interface WorkbenchStatusOverviewGroup {
  id: string;
  label: string;
  severity: WorkbenchOverviewSeverity;
  summary: string;
  items: WorkbenchStatusOverviewItem[];
}

export interface WorkbenchStatusOverviewResponse {
  schema: string;
  workspace: string;
  cloud_mode: boolean;
  overall: {
    severity: WorkbenchOverviewSeverity;
    label: string;
    error_count: number;
    warning_count: number;
  };
  groups: WorkbenchStatusOverviewGroup[];
  issues: WorkbenchStatusOverviewIssue[];
}
```

- [ ] **Step 2: Add the frontend API helper**

Update imports and add this function to `apps/workbench/src/api.ts`:

```ts
export function getWorkbenchStatusOverview(): Promise<WorkbenchStatusOverviewResponse> {
  return requestJson<WorkbenchStatusOverviewResponse>("/api/workbench/status-overview");
}
```

- [ ] **Step 3: Load overview data in settings center**

In `apps/workbench/src/App.tsx`:

```ts
type WorkbenchSettingsCategory = "overview" | "api" | "agent" | "llm" | "processor";
type WorkbenchSettingsDetailCategory = Exclude<WorkbenchSettingsCategory, "overview">;
type WorkbenchSettingsNavItem = { id: WorkbenchSettingsCategory; label: string; icon: WorkbenchSettingsCategory };
```

Add state:

```ts
const [overviewResponse, setOverviewResponse] = useState<WorkbenchStatusOverviewResponse | null>(null);
const [overviewError, setOverviewError] = useState("");
const [settingsCategory, setSettingsCategory] = useState<WorkbenchSettingsCategory>("overview");
const [settingsDetailTarget, setSettingsDetailTarget] = useState<WorkbenchSettingsDetailCategory | null>(null);
```

Load the endpoint in `loadSettings()`:

```ts
const [nextOverviewResponse, nextResponse, nextApiResponse, nextProcessorResponse] = await Promise.all([
  getWorkbenchStatusOverview(),
  getWorkbenchAgentSettings(false),
  getApiPresets(),
  getProcessorSettings()
]);
setOverviewResponse(nextOverviewResponse);
setOverviewError("");
```

After saving settings, refresh overview:

```ts
const nextOverviewResponse = await getWorkbenchStatusOverview();
setOverviewResponse(nextOverviewResponse);
setOverviewError("");
```

- [ ] **Step 4: Add overview navigation actions**

Add this helper inside `WorkbenchSettingsCenter`:

```ts
const openSettingsOverviewAction = (action?: WorkbenchStatusOverviewAction) => {
  if (!action) return;
  setSettingsDetailTarget(null);
  if (action.category === "api") {
    const targetIndex = apiDrafts.findIndex((preset) => preset.id === action.target_id);
    if (targetIndex >= 0) {
      openApiPresetSettings(targetIndex);
      return;
    }
    if (action.mode === "create_images_api") {
      const nextIndex = createApiPresetDraft();
      updateApiPresetDraft(setApiDrafts, nextIndex, { type: "images_api", label: "Images API", id: uniqueApiPresetId(apiDrafts, "images_api") });
      openApiPresetSettings(nextIndex);
      return;
    }
    setSettingsCategory("api");
    return;
  }
  if (action.category === "agent") {
    openAgentSettings(action.target_id || draft.selected_provider_id);
    return;
  }
  if (action.category === "llm") {
    setSettingsCategory("llm");
    if (action.target_id) setSelectedLlmPresetId(action.target_id);
    return;
  }
  if (action.category === "processor") {
    openProcessorSettings(action.target_id);
    return;
  }
  setSettingsCategory("overview");
};
```

- [ ] **Step 5: Render the overview page**

Add `settingsCategory === "overview"` branch before the API branch:

```tsx
{settingsCategory === "overview" && (
  <SettingsOverviewPage
    overview={overviewResponse}
    loading={loading}
    error={overviewError}
    onAction={openSettingsOverviewAction}
  />
)}
```

Add components in `App.tsx`:

```tsx
function SettingsOverviewPage({
  overview,
  loading,
  error,
  onAction
}: {
  overview: WorkbenchStatusOverviewResponse | null;
  loading: boolean;
  error: string;
  onAction: (action?: WorkbenchStatusOverviewAction) => void;
}) {
  if (loading) return <div className="agent-settings-empty">加载中</div>;
  if (error) return <div className="agent-settings-error">{error}</div>;
  if (!overview) return <EmptyState label="暂无状态总览" />;
  return (
    <div className="settings-overview">
      <section className={`settings-overview-summary ${overview.overall.severity}`}>
        <div>
          <span>状态总览</span>
          <strong>{overview.overall.label}</strong>
        </div>
        <dl>
          <div><dt>Error</dt><dd>{overview.overall.error_count}</dd></div>
          <div><dt>Warning</dt><dd>{overview.overall.warning_count}</dd></div>
        </dl>
      </section>
      <div className="settings-overview-groups">
        {overview.groups.map((group) => (
          <article key={group.id} className={`settings-overview-group ${group.severity}`}>
            <header>
              <span>{group.label}</span>
              <strong>{group.summary}</strong>
            </header>
            <div>
              {group.items.map((item) => (
                <div key={item.id} className={`settings-overview-item ${item.severity}`}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <em>{item.detail}</em>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
      <section className="settings-overview-issues">
        <header>
          <span>需要处理</span>
          <strong>{overview.issues.length ? `${overview.issues.length} 项` : "无"}</strong>
        </header>
        {overview.issues.length === 0 ? (
          <EmptyState label="当前配置已就绪" />
        ) : (
          overview.issues.map((issue) => (
            <article key={issue.id} className={`settings-overview-issue ${issue.severity}`}>
              <div>
                <span>{issue.scope}</span>
                <strong>{issue.title}</strong>
                <p>{issue.message}</p>
              </div>
              {issue.action && (
                <button type="button" className="settings-model-action" onClick={() => onAction(issue.action)}>
                  {issue.action.label}
                </button>
              )}
            </article>
          ))
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 6: Add overview CSS**

Add CSS near settings center styles in `apps/workbench/src/styles.css` for `.settings-overview`, `.settings-overview-summary`, `.settings-overview-groups`, `.settings-overview-group`, `.settings-overview-item`, and `.settings-overview-issue`. Use existing palette variables, 8px radii, compact body-sized text, responsive single-column behavior under narrow widths.

- [ ] **Step 7: Run frontend build**

Run:

```bash
npm --prefix apps/workbench run build
```

Expected: PASS.

- [ ] **Step 8: Commit frontend overview**

Run:

```bash
git add apps/workbench/src/types.ts apps/workbench/src/api.ts apps/workbench/src/App.tsx apps/workbench/src/styles.css
git commit -m "feat(workbench): add settings status overview"
```

### Task 3: Final Verification and Publish

**Files:**
- Verify working tree only.

- [ ] **Step 1: Run final backend tests**

Run:

```bash
uv run pytest tests/workbench/test_store_api.py -k "status_overview or api_health" -v
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests and build**

Run:

```bash
npm --prefix apps/workbench test
npm --prefix apps/workbench run build
```

Expected: PASS.

- [ ] **Step 3: Run diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: no whitespace errors; working tree clean after commits.

- [ ] **Step 4: Push branch**

Run:

```bash
git push
```

Expected: branch `caopu/workbench-status-overview-design` updates on `origin`.
