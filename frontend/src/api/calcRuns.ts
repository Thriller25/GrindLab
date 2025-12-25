import { api } from "./client";
import type { FlowsheetNode, FlowsheetEdge } from "../features/flowsheet";

export type PSDPoint = {
  size_um: number;
  pass_pct: number;
};

export type FactPSD = {
  points: PSDPoint[];
  p80_um?: number | null;
  p50_um?: number | null;
};

export type CalcInput = {
  feed_tph?: number | null;
  target_p80_microns?: number | null;
  ore_hardness_ab?: number | null;
  ore_hardness_ta?: number | null;
  water_fraction?: number | null;
  fact_psd?: FactPSD | null;
};

export type RunAndSavePayload = {
  flowsheet_version_id: string;
  project_id?: number;
  scenario_id?: string;
  scenario_name?: string | null;
  comment?: string | null;
  nodes: Array<{ id: string; type?: string; data?: any }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    sourceHandle?: string | null;
    targetHandle?: string | null;
  }>;
};

export type CalcRunRead = {
  id: string;
  flowsheet_version_id: string;
  scenario_id?: string | null;
  scenario_name?: string | null;
  project_id?: number | null;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at: string;
  comment?: string | null;
  error_message?: string | null;
  input_json?: CalcInput | null;
  result_json?: any;
};

export async function runAndSaveFlowsheet(
  flowsheetVersionId: string,
  nodes: FlowsheetNode[],
  edges: FlowsheetEdge[],
  opts?: { projectId?: number; scenarioId?: string; scenarioName?: string | null; comment?: string | null },
): Promise<CalcRunRead> {
  const payload: RunAndSavePayload = {
    flowsheet_version_id: flowsheetVersionId,
    project_id: opts?.projectId,
    scenario_id: opts?.scenarioId,
    scenario_name: opts?.scenarioName ?? null,
    comment: opts?.comment ?? null,
    nodes: nodes.map((n) => ({ id: n.id, type: n.type, data: n.data })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
    })),
  };
  const resp = await api.post<CalcRunRead>("/api/calc-runs/run-and-save", payload);
  return resp.data;
}
