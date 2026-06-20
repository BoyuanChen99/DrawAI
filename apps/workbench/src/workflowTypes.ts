export type WorkflowPortCardinality = "single" | "many";

export interface WorkflowPort {
  port_id: string;
  label: string;
  types: string[];
  required: boolean;
  cardinality: WorkflowPortCardinality;
  formats: string[];
  description: string;
}

export interface WorkflowNode {
  node_id: string;
  node_type: string;
  title: string;
  inputs: WorkflowPort[];
  outputs: WorkflowPort[];
  config: Record<string, unknown>;
  position: { x?: number; y?: number };
  description: string;
}

export interface WorkflowEdge {
  edge_id: string;
  source_node_id: string;
  source_port_id: string;
  target_node_id: string;
  target_port_id: string;
  enabled_types: string[];
}

export interface WorkflowTemplate {
  schema: string;
  template_id: string;
  name: string;
  description: string;
  version: number;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  defaults: Record<string, unknown>;
}

export interface WorkflowValidationError {
  code: string;
  message: string;
  node_id: string;
  edge_id: string;
  details: Record<string, unknown>;
}

export interface WorkflowValidationResult {
  ok: boolean;
  errors: WorkflowValidationError[];
}

export interface AgentProviderSpec {
  provider_id: string;
  label: string;
  kind: "sdk" | "cli" | string;
  resource_key: string;
  default_max_concurrent: number;
  executable: string;
  supports_images: boolean;
  description: string;
}

export interface AgentPromptPreview {
  preset_id: string;
  provider_id: string;
  text: string;
  inputs: Array<Record<string, unknown>>;
  outputs: Array<Record<string, unknown>>;
  options: Record<string, unknown>;
}
