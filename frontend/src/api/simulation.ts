import { api } from "./client";
import type { FlowsheetEdge, FlowsheetNode } from "../features/flowsheet";

export type SimulationResult = {
  success: boolean;
  errors?: string[];
  warnings?: string[];
  global_kpi?: Record<string, number>;
  node_kpi?: Record<string, Record<string, number>>;
};

export async function runSimulation(
  nodes: FlowsheetNode[],
  edges: FlowsheetEdge[],
): Promise<SimulationResult> {
  // Отправляем только необходимые поля
  const payload = {
    nodes: nodes.map((n) => ({ id: n.id, type: n.type, data: n.data })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
    })),
  };

  const resp = await api.post<SimulationResult>("/api/simulation/run", payload);
  return resp.data;
}
