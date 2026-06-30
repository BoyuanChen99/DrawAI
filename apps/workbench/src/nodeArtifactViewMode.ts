import type { WorkflowNodeViewer } from "./types";

export type WorkflowNodeArtifactViewMode = "artifact" | "agent_log";

type AgentLogsLike = Partial<WorkflowNodeViewer["agent_logs"]> | null | undefined;
type ArtifactsLike = Partial<WorkflowNodeViewer["artifacts"][number]>[] | null | undefined;

export function defaultWorkflowNodeArtifactViewMode(viewer: {
  available: boolean;
  artifacts?: ArtifactsLike;
  agent_logs?: AgentLogsLike;
}): WorkflowNodeArtifactViewMode {
  if (workflowNodeViewerHasOutputArtifacts(viewer)) {
    return "artifact";
  }
  if (!viewer.available && workflowNodeViewerHasAgentLogs(viewer)) {
    return "agent_log";
  }
  return "artifact";
}

export function workflowNodeViewerHasOutputArtifacts(viewer: {
  artifacts?: ArtifactsLike;
}): boolean {
  return (viewer.artifacts || []).some(
    (artifact) => Boolean(artifact.exists && artifact.url) && artifact.role !== "log" && artifact.kind !== "agent_log"
  );
}

export function workflowNodeViewerHasAgentLogs(viewer: {
  agent_logs?: AgentLogsLike;
}): boolean {
  const logs = viewer.agent_logs;
  if (!logs) return false;

  if ((logs.session_events || []).length > 0) return true;
  if ((logs.trace_events || []).length > 0) return true;
  if ((logs.runtime_log_tail || []).length > 0) return true;
  if ((logs.files || []).some((file) => file.exists && file.url)) return true;

  return Boolean(logs.session_summary && Object.keys(logs.session_summary).length > 0);
}
