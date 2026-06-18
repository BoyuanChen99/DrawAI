import { PointerEvent, useEffect, useMemo, useState } from "react";
import {
  copyWorkflowTemplate,
  listWorkflowProviders,
  listWorkflowTemplates,
  previewAgentPrompt,
  saveWorkflowTemplate,
  validateWorkflowTemplate
} from "./workflowApi";
import type {
  AgentPromptPreview,
  AgentProviderSpec,
  WorkflowEdge,
  WorkflowNode,
  WorkflowTemplate,
  WorkflowValidationResult
} from "./workflowTypes";

type DraggingNode = {
  nodeId: string;
  pointerId: number;
  startClientX: number;
  startClientY: number;
  startX: number;
  startY: number;
};

const NODE_WIDTH = 184;
const NODE_HEIGHT = 96;
const DEFAULT_COPY_NAME = "Custom DrawAI DAG";

export default function WorkflowWorkspace({ onError }: { onError: (message: string) => void }) {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [providers, setProviders] = useState<AgentProviderSpec[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [draft, setDraft] = useState<WorkflowTemplate | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [validation, setValidation] = useState<WorkflowValidationResult | null>(null);
  const [promptPreview, setPromptPreview] = useState<AgentPromptPreview | null>(null);
  const [copyName, setCopyName] = useState(DEFAULT_COPY_NAME);
  const [dragging, setDragging] = useState<DraggingNode | null>(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    void loadWorkflowData();
  }, []);

  async function loadWorkflowData(preferredTemplateId = selectedTemplateId) {
    try {
      setBusy("load");
      const [templateResponse, providerResponse] = await Promise.all([
        listWorkflowTemplates(),
        listWorkflowProviders()
      ]);
      setTemplates(templateResponse.templates);
      setProviders(providerResponse.providers);
      const next =
        templateResponse.templates.find((item) => item.template_id === preferredTemplateId) ||
        templateResponse.templates[0] ||
        null;
      setSelectedTemplateId(next?.template_id || "");
      setDraft(next ? cloneTemplate(next) : null);
      setSelectedNodeId(next?.nodes[0]?.node_id || "");
      setValidation(null);
      setPromptPreview(null);
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }

  const selectedNode = useMemo(
    () => draft?.nodes.find((node) => node.node_id === selectedNodeId) || null,
    [draft, selectedNodeId]
  );
  const selectedTemplate = templates.find((template) => template.template_id === selectedTemplateId) || null;
  const readOnly = Boolean(draft?.defaults?.read_only);
  const canvasSize = useMemo(() => workflowCanvasSize(draft), [draft]);
  const nodeStats = useMemo(() => workflowNodeStats(draft), [draft]);

  async function copySelectedTemplate() {
    const sourceId = selectedTemplateId || "default_drawai_dag";
    try {
      setBusy("copy");
      const response = await copyWorkflowTemplate(sourceId, copyName.trim() || DEFAULT_COPY_NAME);
      await loadWorkflowData(response.template.template_id);
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }

  async function validateDraft() {
    if (!draft) return;
    try {
      setBusy("validate");
      const response = await validateWorkflowTemplate(draft);
      setValidation(response.validation);
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }

  async function saveDraft() {
    if (!draft || readOnly) return;
    try {
      setBusy("save");
      const response = await saveWorkflowTemplate(draft);
      setDraft(cloneTemplate(response.template));
      await loadWorkflowData(response.template.template_id);
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }

  async function renderPromptForNode(node: WorkflowNode) {
    if (!draft || node.node_type !== "agent") return;
    const presetId = String(node.config.preset_id || "");
    if (!presetId) {
      onError("这个 Agent 节点没有 preset_id。");
      return;
    }
    try {
      setBusy("prompt");
      const response = await previewAgentPrompt({
        preset_id: presetId,
        node_config: node.config,
        inputs: workflowInputPreview(draft, node)
      });
      setPromptPreview(response.prompt);
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }

  function updateSelectedAgentProvider(providerId: string) {
    if (!selectedNode || selectedNode.node_type !== "agent") return;
    updateNode(selectedNode.node_id, {
      config: { ...selectedNode.config, provider_id: providerId }
    });
    setPromptPreview(null);
  }

  function updateNode(nodeId: string, patch: Partial<WorkflowNode>) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        nodes: current.nodes.map((node) => (node.node_id === nodeId ? { ...node, ...patch } : node))
      };
    });
  }

  function beginNodeDrag(event: PointerEvent<HTMLElement>, node: WorkflowNode) {
    if (readOnly) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging({
      nodeId: node.node_id,
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: node.position.x || 0,
      startY: node.position.y || 0
    });
  }

  function moveNode(event: PointerEvent<HTMLElement>) {
    if (!dragging || dragging.pointerId !== event.pointerId) return;
    const nextX = Math.max(0, dragging.startX + event.clientX - dragging.startClientX);
    const nextY = Math.max(0, dragging.startY + event.clientY - dragging.startClientY);
    updateNode(dragging.nodeId, { position: { x: Math.round(nextX), y: Math.round(nextY) } });
  }

  function endNodeDrag(event: PointerEvent<HTMLElement>) {
    if (dragging?.pointerId === event.pointerId) setDragging(null);
  }

  return (
    <main className="workflow-workspace">
      <aside className="workflow-sidebar">
        <div className="workflow-panel-head">
          <span>Workflow</span>
          <strong>DAG 模板</strong>
        </div>
        <label className="workflow-field">
          <span>模板</span>
          <select
            value={selectedTemplateId}
            onChange={(event) => {
              const template = templates.find((item) => item.template_id === event.target.value) || null;
              setSelectedTemplateId(template?.template_id || "");
              setDraft(template ? cloneTemplate(template) : null);
              setSelectedNodeId(template?.nodes[0]?.node_id || "");
              setValidation(null);
              setPromptPreview(null);
            }}
          >
            {templates.map((template) => (
              <option value={template.template_id} key={template.template_id}>
                {template.name}
              </option>
            ))}
          </select>
        </label>
        <div className="workflow-copy-row">
          <input value={copyName} onChange={(event) => setCopyName(event.target.value)} />
          <button type="button" disabled={busy === "copy"} onClick={() => void copySelectedTemplate()}>
            复制
          </button>
        </div>
        <div className="workflow-stats" aria-label="节点类型">
          <span>Parser <strong>{nodeStats.parser}</strong></span>
          <span>Agent <strong>{nodeStats.agent}</strong></span>
          <span>Processor <strong>{nodeStats.processor}</strong></span>
          <span>Export <strong>{nodeStats.export}</strong></span>
        </div>
        <div className="workflow-actions">
          <button type="button" disabled={!draft || busy === "validate"} onClick={() => void validateDraft()}>
            校验
          </button>
          <button type="button" className="primary" disabled={!draft || readOnly || busy === "save"} onClick={() => void saveDraft()}>
            保存
          </button>
        </div>
        {selectedTemplate && (
          <div className="workflow-template-meta">
            <span>{selectedTemplate.template_id}</span>
            <em>{readOnly ? "内置模板" : "本地模板"}</em>
          </div>
        )}
        {validation && (
          <div className={validation.ok ? "workflow-validation ok" : "workflow-validation failed"}>
            <strong>{validation.ok ? "校验通过" : `${validation.errors.length} 个问题`}</strong>
            {validation.errors.slice(0, 5).map((item) => (
              <span key={`${item.code}-${item.node_id}-${item.edge_id}`}>{item.code}</span>
            ))}
          </div>
        )}
      </aside>

      <section className="workflow-canvas-shell">
        <div className="workflow-canvas-scroll">
          <div className="workflow-canvas" style={{ width: canvasSize.width, height: canvasSize.height }}>
            {draft && <WorkflowEdges template={draft} />}
            {draft?.nodes.map((node) => (
              <article
                key={node.node_id}
                className={`workflow-node node-${node.node_type} ${node.node_id === selectedNodeId ? "active" : ""}`}
                style={{ left: node.position.x || 0, top: node.position.y || 0 }}
                onClick={() => {
                  setSelectedNodeId(node.node_id);
                  setPromptPreview(null);
                }}
                onPointerDown={(event) => beginNodeDrag(event, node)}
                onPointerMove={moveNode}
                onPointerUp={endNodeDrag}
                onPointerCancel={endNodeDrag}
              >
                <div className="workflow-node-head">
                  <span>{node.node_type}</span>
                  <strong>{node.title}</strong>
                </div>
                <div className="workflow-node-ports">
                  <em>{node.inputs.length} in</em>
                  <em>{node.outputs.length} out</em>
                </div>
                <p>{nodeOutputSummary(node)}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <aside className="workflow-inspector">
        {selectedNode ? (
          <>
            <div className="workflow-panel-head">
              <span>{selectedNode.node_type}</span>
              <strong>{selectedNode.title}</strong>
            </div>
            <dl className="workflow-node-meta">
              <div>
                <dt>ID</dt>
                <dd>{selectedNode.node_id}</dd>
              </div>
              <div>
                <dt>输入</dt>
                <dd>{selectedNode.inputs.map((port) => port.types.join(" / ")).join(", ") || "-"}</dd>
              </div>
              <div>
                <dt>输出</dt>
                <dd>{selectedNode.outputs.map((port) => port.types.join(" / ")).join(", ") || "-"}</dd>
              </div>
            </dl>
            {selectedNode.node_type === "agent" && (
              <div className="workflow-agent-box">
                <label className="workflow-field">
                  <span>Provider</span>
                  <select
                    value={String(selectedNode.config.provider_id || "")}
                    disabled={readOnly}
                    onChange={(event) => updateSelectedAgentProvider(event.target.value)}
                  >
                    {providers.map((provider) => (
                      <option value={provider.provider_id} key={provider.provider_id}>
                        {provider.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="workflow-agent-io">
                  <strong>Preset</strong>
                  <span>{String(selectedNode.config.preset_id || "-")}</span>
                </div>
                <button type="button" disabled={busy === "prompt"} onClick={() => void renderPromptForNode(selectedNode)}>
                  预览 Prompt
                </button>
              </div>
            )}
            <div className="workflow-port-list">
              <strong>Ports</strong>
              {[
                ...selectedNode.inputs.map((port, index) => ({ port, direction: "input", index })),
                ...selectedNode.outputs.map((port, index) => ({ port, direction: "output", index }))
              ].map(({ port, direction, index }) => (
                <div className="workflow-port-row" key={`${direction}-${port.port_id}-${port.cardinality}-${index}`}>
                  <span>{port.port_id}</span>
                  <em>{port.types.join(" / ")}</em>
                </div>
              ))}
            </div>
            {promptPreview && (
              <div className="workflow-prompt-preview">
                <div>
                  <span>{promptPreview.provider_id}</span>
                  <strong>{promptPreview.preset_id}</strong>
                </div>
                <pre>{promptPreview.text}</pre>
              </div>
            )}
          </>
        ) : (
          <div className="workflow-empty">选择一个节点</div>
        )}
      </aside>
    </main>
  );
}

function WorkflowEdges({ template }: { template: WorkflowTemplate }) {
  const nodeById = new Map(template.nodes.map((node) => [node.node_id, node]));
  return (
    <svg className="workflow-edges" aria-hidden="true">
      {template.edges.map((edge) => {
        const source = nodeById.get(edge.source_node_id);
        const target = nodeById.get(edge.target_node_id);
        if (!source || !target) return null;
        const start = {
          x: (source.position.x || 0) + NODE_WIDTH,
          y: (source.position.y || 0) + NODE_HEIGHT / 2
        };
        const end = {
          x: target.position.x || 0,
          y: (target.position.y || 0) + NODE_HEIGHT / 2
        };
        const mid = Math.max(42, Math.abs(end.x - start.x) * 0.42);
        const d = `M ${start.x} ${start.y} C ${start.x + mid} ${start.y}, ${end.x - mid} ${end.y}, ${end.x} ${end.y}`;
        return <path key={edge.edge_id} d={d} />;
      })}
    </svg>
  );
}

function workflowInputPreview(template: WorkflowTemplate, node: WorkflowNode): Array<Record<string, unknown>> {
  return template.edges
    .filter((edge) => edge.target_node_id === node.node_id)
    .map((edge) => {
      const source = template.nodes.find((item) => item.node_id === edge.source_node_id);
      const sourcePort = source?.outputs.find((port) => port.port_id === edge.source_port_id);
      const formatId = sourcePort?.formats[0] || "";
      return {
        path: `nodes/${edge.source_node_id}/runs/latest/output/${edge.source_port_id}.${formatId.includes("svg") ? "svg" : "json"}`,
        format_id: formatId,
        type: sourcePort?.types[0] || "",
        source_node_id: edge.source_node_id,
        source_port_id: edge.source_port_id,
        description: sourcePort?.description || `${source?.title || edge.source_node_id} output`
      };
    });
}

function workflowCanvasSize(template: WorkflowTemplate | null): { width: number; height: number } {
  if (!template) return { width: 1200, height: 640 };
  const maxX = Math.max(...template.nodes.map((node) => node.position.x || 0), 900);
  const maxY = Math.max(...template.nodes.map((node) => node.position.y || 0), 480);
  return { width: maxX + NODE_WIDTH + 220, height: maxY + NODE_HEIGHT + 140 };
}

function workflowNodeStats(template: WorkflowTemplate | null): Record<string, number> {
  const stats: Record<string, number> = { parser: 0, agent: 0, processor: 0, export: 0 };
  template?.nodes.forEach((node) => {
    if (node.node_type in stats) stats[node.node_type] += 1;
  });
  return stats;
}

function nodeOutputSummary(node: WorkflowNode): string {
  const formats = node.outputs.flatMap((port) => port.formats);
  if (formats.length > 0) return formats.join(" · ");
  return node.outputs.map((port) => port.types.join("/")).join(" · ") || "control";
}

function cloneTemplate(template: WorkflowTemplate): WorkflowTemplate {
  return JSON.parse(JSON.stringify(template)) as WorkflowTemplate;
}
