import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "grindlab_token";

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  api.defaults.headers.common.Authorization = `Bearer ${token}`;
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  delete api.defaults.headers.common.Authorization;
}

export const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const existing = getToken();
if (existing) {
  api.defaults.headers.common.Authorization = `Bearer ${existing}`;
}

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
  recent_comments: any[];
  favorites?: {
    projects?: any[];
    scenarios?: any[];
    calc_runs?: any[];
  };
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

export async function fetchMyProjects(): Promise<ProjectDTO[]> {
  const resp = await api.get<ProjectDTO[]>("/api/projects/my");
  return resp.data;
}

export async function seedDemoProject(): Promise<ProjectDTO> {
  const resp = await api.post<ProjectDTO>("/api/projects/demo-seed");
  return resp.data;
}
