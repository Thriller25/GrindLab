import axios, { AxiosResponse } from "axios";
import { clearAuth, getAccessToken } from "../auth/authProvider";

const rawBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) || "";
const API_BASE_URL = rawBaseUrl.trim() || "http://127.0.0.1:8000";
console.info(`[GrindLab] API base URL: ${API_BASE_URL}`);
const AUTH_EXPIRED_ERROR = { kind: "AUTH_EXPIRED" } as const;

export type AuthExpiredError = typeof AUTH_EXPIRED_ERROR;

export const isAuthExpiredError = (error: unknown): error is AuthExpiredError =>
  Boolean((error as { kind?: unknown })?.kind === AUTH_EXPIRED_ERROR.kind);

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

const withAuthExpirationHandling = async <T>(
  request: () => Promise<AxiosResponse<T>>,
): Promise<T> => {
  try {
    const resp = await request();
    return resp.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearAuth();
      throw AUTH_EXPIRED_ERROR;
    }
    throw error;
  }
};

const withAuthExpirationHandlingVoid = async (request: () => Promise<unknown>): Promise<void> => {
  try {
    await request();
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearAuth();
      throw AUTH_EXPIRED_ERROR;
    }
    throw error;
  }
};

export const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface DashboardSummary {
  calc_runs_total?: number;
  scenarios_total?: number;
  comments_total?: number;
  projects_total?: number;
  calc_runs_by_status?: Record<string, number>;
}

export interface DashboardCalcRunSummary {
  id: string;
  model_version?: string | null;
  created_at?: string | null;
  plant_id?: string | number | null;
  plant_name?: string | null;
  flowsheet_version_id?: string | number | null;
  flowsheet_name?: string | null;
  scenario_name?: string | null;
  comment?: string | null;
  throughput_tph?: number | null;
  product_p80_mm?: number | null;
  specific_energy_kwhpt?: number | null;
  baseline_run_id?: string | number | null;
  is_baseline?: boolean;
}

export interface DashboardResponse {
  user: { id?: string; email?: string; full_name?: string | null };
  summary: DashboardSummary;
  projects: any[];
  member_projects: any[];
  recent_calc_runs: DashboardCalcRunSummary[];
  recent_comments: ProjectComment[];
  favorites?: {
    projects?: any[];
    scenarios?: any[];
    calc_runs?: any[];
  };
}

export type GrindMvpKpi = {
  throughput_tph: number;
  product_p80_mm: number;
  specific_energy_kwh_per_t: number;
  circulating_load_percent: number;
  mill_utilization_percent: number;
};

export type GrindMvpSizePoint = { size_mm: number; cum_percent: number };

export interface GrindMvpBaselineComparison {
  baseline_run_id: string;
  throughput_delta_tph?: number | null;
  product_p80_delta_mm?: number | null;
  specific_energy_delta_kwhpt?: number | null;
  throughput_delta_percent?: number | null;
  specific_energy_delta_percent?: number | null;
}

export interface BaselineKpi {
  throughput_tph: number | null;
  product_p80_mm: number | null;
  specific_energy_kwh_per_t: number | null;
  circulating_load_percent: number | null;
  utilization_percent: number | null;
}

export interface CalcRunBaselineComparison {
  calc_run_id: string;
  baseline_run_id: string;
  current_kpi: BaselineKpi;
  baseline_kpi: BaselineKpi;
  delta: BaselineKpi;
}

export type GrindMvpResult = {
  model_version: string;
  kpi: GrindMvpKpi;
  size_distribution: {
    feed: GrindMvpSizePoint[];
    product: GrindMvpSizePoint[];
  };
  baseline_comparison?: GrindMvpBaselineComparison | null;
};

export interface GrindMvpRunSummary {
  id: string;
  created_at: string;
  model_version: string;
  plant_id?: string | number | null;
  project_id?: number | null;
  plant_name?: string | null;
  flowsheet_version_id?: string | number | null;
  flowsheet_name?: string | null;
   scenario_id?: string | null;
  scenario_name?: string | null;
  comment?: string | null;
  throughput_tph?: number | null;
  product_p80_mm?: number | null;
  specific_energy_kwhpt?: number | null;
  baseline_run_id?: string | number | null;
  is_baseline?: boolean;
}

export interface GrindMvpInput {
  model_version: string;
  plant_id: string | number;
  flowsheet_version_id: string | number;
  project_id?: number | null;
  scenario_id?: string | null;
  scenario_name?: string | null;
  feed: {
    tonnage_tph: number;
    p80_mm: number;
    density_t_per_m3: number;
  };
  mill: {
    type: string;
    power_installed_kw: number;
    power_draw_kw: number;
    ball_charge_percent: number;
    speed_percent_critical: number;
  };
  classifier: {
    type: string;
    cut_size_p80_mm: number;
    circulating_load_percent: number;
  };
  options: {
    use_baseline_run_id: string | number | null;
  };
}

export interface GrindMvpRunDetail {
  id: string;
  created_at: string;
  model_version: string;
  plant_id?: string | null;
  project_id?: number | null;
  flowsheet_version_id?: string | null;
  scenario_id?: string | null;
  scenario_name?: string | null;
  comment?: string | null;
  input: GrindMvpInput;
  result: GrindMvpResult;
}

export interface PlantSummary {
  id: string;
  name: string;
}

export interface PlantDetail extends PlantSummary {
  code?: string | null;
  company?: string | null;
}

export interface FlowsheetVersionSummary {
  id: string;
  name: string;
  flowsheet_id?: string;
}

export interface FlowsheetVersionDetail {
  id: string;
  flowsheet_id: string;
  version_label: string;
  status: string;
  is_active: boolean;
  comment?: string | null;
}

export interface FlowsheetDetail {
  id: string;
  plant_id: string;
  name: string;
  description?: string | null;
  status: string;
}

export interface CalcScenario {
  id: string;
  name: string;
  description?: string | null;
  flowsheet_version_id: string;
  project_id: number;
  is_baseline: boolean;
   is_recommended: boolean;
   recommendation_note?: string | null;
   recommended_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface CalcScenarioListResponse {
  items: CalcScenario[];
  total: number;
}

export async function fetchDashboard(): Promise<DashboardResponse> {
  const resp = await api.get<DashboardResponse>("/api/me/dashboard");
  return resp.data;
}

export type ProjectDTO = {
  id: number;
  name: string;
  description?: string | null;
  owner_user_id?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProjectListResponse = {
  items: ProjectDTO[];
  total: number;
};

export type ProjectSummary = {
  project?: ProjectDTO;
  flowsheet_versions_total?: number;
  scenarios_total?: number;
  calc_runs_total?: number;
  calc_runs_by_status?: Record<string, number>;
  comments_total?: number;
  last_activity_at?: string | null;
};

export type ProjectFlowsheetVersion = {
  id: string;
  flowsheet_id?: string;
  version_label?: string;
  status?: string;
  is_active?: boolean;
  comment?: string | null;
};

export type ProjectCalcRunListItem = {
  id: string;
  flowsheet_version_id?: string;
  scenario_id?: string | null;
  scenario_name?: string | null;
  status?: string;
  started_at?: string | null;
  finished_at?: string | null;
  comment?: string | null;
  error_message?: string | null;
  started_by_user_id?: string | null;
  is_baseline?: boolean;
};

export type ProjectComment = {
  id: string;
  project_id: number;
  scenario_id?: string | null;
  calc_run_id?: string | null;
  target_type?: "scenario" | "calc_run";
  text: string;
  created_at?: string | null;
  author?: string | null;
};

export type ProjectDashboardResponse = {
  project: ProjectDTO;
  summary: ProjectSummary;
  flowsheet_versions: ProjectFlowsheetVersion[];
  scenarios: CalcScenario[];
  recent_calc_runs: ProjectCalcRunListItem[];
  recent_comments: ProjectComment[];
};

export async function fetchMyProjects(): Promise<ProjectListResponse> {
  const resp = await api.get<ProjectListResponse>("/api/projects/my");
  return resp.data;
}

export async function fetchProjectDashboard(projectId: string | number): Promise<ProjectDashboardResponse> {
  const resp = await api.get<ProjectDashboardResponse>(`/api/projects/${projectId}/dashboard`);
  return resp.data;
}

export type CommentListResponse = { items: ProjectComment[]; total: number };

export async function fetchProjectComments(
  projectId: string | number,
  params?: { limit?: number },
): Promise<CommentListResponse> {
  const queryParams = params?.limit ? { limit: params.limit } : undefined;
  const resp = await api.get<CommentListResponse>(`/api/projects/${projectId}/comments`, { params: queryParams });
  return resp.data;
}

export type CreateProjectCommentPayload = {
  scenario_id?: string;
  calc_run_id?: string;
  text: string;
  author?: string;
};

export async function createProjectComment(
  projectId: string | number,
  payload: CreateProjectCommentPayload,
): Promise<ProjectComment> {
  return withAuthExpirationHandling(() => api.post<ProjectComment>(`/api/projects/${projectId}/comments`, payload));
}

export async function seedDemoProject(): Promise<ProjectDTO> {
  const resp = await api.post<ProjectDTO>("/api/projects/demo-seed");
  return resp.data;
}

export interface CalcRun {
  id: string;
  flowsheet_version_id?: string;
  scenario_id?: string | null;
  baseline_run_id?: string | null;
  is_baseline?: boolean;
}

export async function fetchGrindMvpRuns(limit = 20): Promise<GrindMvpRunSummary[]> {
  const resp = await api.get<GrindMvpRunSummary[]>(`/api/calc/grind-mvp-runs?limit=${limit}`);
  return resp.data;
}

export async function fetchGrindMvpRun(runId: string): Promise<GrindMvpRunDetail> {
  const resp = await api.get<GrindMvpRunDetail>(`/api/calc/grind-mvp-runs/${runId}`);
  return resp.data;
}

export async function fetchCalcRunById(runId: string | number): Promise<GrindMvpRunDetail> {
  const resp = await api.get<GrindMvpRunDetail>(`/api/calc/grind-mvp-runs/${runId}`);
  return resp.data;
}

export interface CalcRunRead {
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
  input_json?: any;
  result_json?: any;
}

export async function fetchCalcRun(runId: string | number): Promise<CalcRunRead> {
  const resp = await api.get<CalcRunRead>(`/api/calc-runs/${runId}`);
  return resp.data;
}

export async function fetchCalcRunComments(runId: string, limit = 20): Promise<CommentListResponse> {
  const resp = await api.get<CommentListResponse>(`/api/calc-runs/${runId}/comments`, { params: { limit } });
  return resp.data;
}

export interface CalcRunListItem {
  id: string;
  flowsheet_version_id: string;
  scenario_id?: string | null;
  scenario_name?: string | null;
  project_id?: number | null;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  comment?: string | null;
  error_message?: string | null;
  started_by_user_id?: string | null;
  input_json?: any;
  result_json?: any;
}

export interface CalcRunListResponse {
  items: CalcRunListItem[];
  total: number;
}

export async function fetchLatestCalcRunByScenario(
  scenarioId: string,
  status: string | null = "success",
): Promise<CalcRunRead> {
  const resp = await api.get<CalcRunRead>(`/api/calc-runs/latest/by-scenario/${scenarioId}`, {
    params: { status: status ?? undefined },
  });
  return resp.data;
}

export async function fetchCalcRunBaselineComparison(
  calcRunId: string | number,
): Promise<CalcRunBaselineComparison> {
  const resp = await api.get<CalcRunBaselineComparison>(`/api/calc-runs/${calcRunId}/baseline-comparison`);
  return resp.data;
}

export async function fetchCalcRunsByFlowsheetVersion(
  flowsheetVersionId: string,
  options?: { limit?: number; offset?: number; status?: string | null; scenarioId?: string },
): Promise<CalcRunListResponse> {
  const { limit, offset, status, scenarioId } = options || {};
  const resp = await api.get<CalcRunListResponse>(`/api/calc-runs/by-flowsheet-version/${flowsheetVersionId}`, {
    params: {
      limit,
      offset,
      status: status ?? undefined,
      scenario_id: scenarioId,
    },
  });
  return resp.data;
}

export async function setCalcRunBaseline(runId: string): Promise<CalcRun> {
  const resp = await api.post<CalcRun>(`/api/calc-runs/${runId}/set-baseline`);
  return resp.data;
}

export async function updateCalcRunComment(runId: string, comment: string | null): Promise<GrindMvpRunDetail> {
  return withAuthExpirationHandling(() =>
    api.put<GrindMvpRunDetail>(`/api/calc/grind-mvp-runs/${runId}/comment`, { comment }),
  );
}

export async function fetchPlants(): Promise<PlantSummary[]> {
  const resp = await api.get<PlantSummary[]>("/api/plants");
  return resp.data.map((p) => ({ id: p.id, name: p.name }));
}

export async function fetchPlant(plantId: string): Promise<PlantDetail> {
  const resp = await api.get<PlantDetail>(`/api/plants/${plantId}`);
  return resp.data;
}

type FlowsheetVersionDto = {
  id: string;
  flowsheet_id: string;
  version_label: string;
};

export async function fetchFlowsheetVersionsForPlant(
  plantId: string,
): Promise<FlowsheetVersionSummary[]> {
  const resp = await api.get<FlowsheetVersionDto[]>("/api/flowsheet-versions", {
    params: { plant_id: plantId },
  });
  return resp.data.map((fv) => ({
    id: fv.id,
    name: fv.version_label,
    flowsheet_id: fv.flowsheet_id,
  }));
}

export async function fetchFlowsheetVersion(versionId: string): Promise<FlowsheetVersionDetail> {
  const resp = await api.get<FlowsheetVersionDetail>(`/api/flowsheet-versions/${versionId}`);
  return resp.data;
}

export async function fetchFlowsheet(flowsheetId: string): Promise<FlowsheetDetail> {
  const resp = await api.get<FlowsheetDetail>(`/api/flowsheets/${flowsheetId}`);
  return resp.data;
}

export async function fetchAllFlowsheetVersions(): Promise<FlowsheetVersionSummary[]> {
  const resp = await api.get<FlowsheetVersionDto[]>("/api/flowsheet-versions");
  return resp.data.map((fv) => ({
    id: fv.id,
    name: fv.version_label,
    flowsheet_id: fv.flowsheet_id,
  }));
}

export async function fetchCalcScenariosByFlowsheetVersion(
  flowsheetVersionId: string,
  projectId?: string | number,
): Promise<CalcScenario[]> {
  const resp = await api.get<CalcScenarioListResponse>(`/api/calc-scenarios/by-flowsheet-version/${flowsheetVersionId}`, {
    params: projectId ? { project_id: projectId } : undefined,
  });
  return resp.data.items;
}

export async function fetchCalcScenariosByProject(
  projectId: string | number,
  flowsheetVersionId?: string,
): Promise<CalcScenario[]> {
  const resp = await api.get<CalcScenarioListResponse>(`/api/calc-scenarios/by-project/${projectId}`, {
    params: flowsheetVersionId ? { flowsheet_version_id: flowsheetVersionId } : undefined,
  });
  return resp.data.items;
}

export async function fetchCalcScenario(scenarioId: string): Promise<CalcScenario> {
  const resp = await api.get<CalcScenario>(`/api/calc-scenarios/${scenarioId}`);
  return resp.data;
}

export async function createCalcScenario(payload: {
  flowsheet_version_id: string;
  project_id: number | string;
  name: string;
  description?: string;
  default_input_json: { feed_tph: number; target_p80_microns: number; ore_hardness_ab?: number | null; ore_hardness_ta?: number | null; water_fraction?: number | null };
  is_baseline?: boolean;
  is_recommended?: boolean;
  recommendation_note?: string | null;
}): Promise<CalcScenario> {
  return withAuthExpirationHandling(() => api.post<CalcScenario>("/api/calc-scenarios", payload));
}

export async function setCalcScenarioBaseline(scenarioId: string): Promise<CalcScenario> {
  return withAuthExpirationHandling(() =>
    api.post<CalcScenario>(`/api/calc-scenarios/${scenarioId}/set-baseline`),
  );
}

export type UpdateScenarioPayload = {
  name?: string;
  description?: string | null;
  is_baseline?: boolean;
  is_recommended?: boolean;
  recommendation_note?: string | null;
};

export async function updateScenario(scenarioId: string, payload: UpdateScenarioPayload): Promise<CalcScenario> {
  return withAuthExpirationHandling(() =>
    api.patch<CalcScenario>(`/api/calc-scenarios/${scenarioId}`, payload),
  );
}

export async function updateCalcScenario(
  scenarioId: string,
  payload: UpdateScenarioPayload,
): Promise<CalcScenario> {
  return updateScenario(scenarioId, payload);
}

export async function deleteCalcScenario(scenarioId: string): Promise<void> {
  await withAuthExpirationHandlingVoid(() => api.delete(`/api/calc-scenarios/${scenarioId}`));
}
