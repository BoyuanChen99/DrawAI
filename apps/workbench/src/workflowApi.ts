import type {
  AgentPromptPreview,
  AgentProviderSpec,
  WorkflowTemplate,
  WorkflowValidationResult
} from "./workflowTypes";

const LOCAL_API_ORIGIN = "http://127.0.0.1:8890";

export async function listWorkflowTemplates(): Promise<{ templates: WorkflowTemplate[] }> {
  return requestJson<{ templates: WorkflowTemplate[] }>("/api/workflow/templates");
}

export async function copyWorkflowTemplate(templateId: string, name: string): Promise<{ template: WorkflowTemplate }> {
  return requestJson<{ template: WorkflowTemplate }>("/api/workflow/templates/copy", {
    method: "POST",
    body: JSON.stringify({ template_id: templateId, name })
  });
}

export async function saveWorkflowTemplate(template: WorkflowTemplate): Promise<{ template: WorkflowTemplate; path: string }> {
  return requestJson<{ template: WorkflowTemplate; path: string }>(`/api/workflow/templates/${encodeURIComponent(template.template_id)}`, {
    method: "PUT",
    body: JSON.stringify(template)
  });
}

export async function validateWorkflowTemplate(template: WorkflowTemplate): Promise<{ validation: WorkflowValidationResult; template: WorkflowTemplate }> {
  return requestJson<{ validation: WorkflowValidationResult; template: WorkflowTemplate }>("/api/workflow/templates/validate", {
    method: "POST",
    body: JSON.stringify(template)
  });
}

export async function listWorkflowProviders(): Promise<{ providers: AgentProviderSpec[] }> {
  return requestJson<{ providers: AgentProviderSpec[] }>("/api/workflow/providers");
}

export async function previewAgentPrompt(payload: {
  preset_id: string;
  node_config: Record<string, unknown>;
  inputs: Array<Record<string, unknown>>;
}): Promise<{ prompt: AgentPromptPreview }> {
  return requestJson<{ prompt: AgentPromptPreview }>("/api/workflow/agent-prompt-preview", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    return await fetchJson<T>(path, init);
  } catch (error) {
    if (isNetworkError(error) && shouldRetryLocalApi(path)) {
      try {
        return await fetchJson<T>(`${localApiOrigin()}${path}`, init);
      } catch (fallbackError) {
        throw drawAiNetworkError(path, fallbackError);
      }
    }
    if (isNetworkError(error)) {
      throw drawAiNetworkError(path, error);
    }
    throw error;
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return (await response.json()) as T;
}

async function responseErrorMessage(response: Response): Promise<string> {
  let message = `${response.status} ${response.statusText}`;
  const clone = response.clone();
  try {
    const payload = await clone.json();
    message = payload.detail || message;
  } catch {
    const text = await response.text();
    if (text) message = text;
  }
  return message;
}

function shouldRetryLocalApi(path: string): boolean {
  if (!path.startsWith("/api")) return false;
  if (typeof window === "undefined") return false;
  const { hostname, port } = window.location;
  return (hostname === "127.0.0.1" || hostname === "localhost") && (port === "5173" || port === "5174");
}

function localApiOrigin(): string {
  const configured = (import.meta.env.VITE_DRAWAI_API_URL || "").trim().replace(/\/$/, "");
  return configured || LOCAL_API_ORIGIN;
}

function isNetworkError(error: unknown): boolean {
  return error instanceof TypeError && /fetch|network|load failed/i.test(error.message);
}

function drawAiNetworkError(path: string, error: unknown): Error {
  const detail = error instanceof Error ? error.message : String(error);
  return new Error(`无法连接 DrawAI 后端（${path}）：${detail}`);
}
