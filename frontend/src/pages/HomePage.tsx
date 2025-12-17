import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchDashboard,
  fetchMyProjects,
  seedDemoProject,
  DashboardResponse,
  DashboardCalcRunSummary,
  ProjectDTO,
} from "../api/client";

const formatDateTime = (value?: string | null) => {
  if (!value) return "Дата не указана";
  return new Date(value).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const emptyDashboard: DashboardResponse = {
  user: {},
  summary: {
    calc_runs_total: 0,
    scenarios_total: 0,
    comments_total: 0,
    projects_total: 0,
    calc_runs_by_status: {},
  },
  projects: [],
  member_projects: [],
  recent_calc_runs: [],
  recent_comments: [],
  favorites: { projects: [], scenarios: [], calc_runs: [] },
};

export const HomePage = () => {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<DashboardResponse>(emptyDashboard);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectDTO[]>([]);
  const [projectsTotal, setProjectsTotal] = useState<number>(0);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [isProjectsLoading, setIsProjectsLoading] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);

  const loadDashboard = () => {
    setIsLoading(true);
    setError(null);
    fetchDashboard()
      .then((data) => setDashboard({ ...emptyDashboard, ...data }))
      .catch(() => {
        setError("Не удалось загрузить дашборд");
        setDashboard(emptyDashboard);
      })
      .finally(() => setIsLoading(false));
  };

  const loadProjects = () => {
    setIsProjectsLoading(true);
    setProjectsError(null);
    fetchMyProjects()
      .then((data) => {
        const items = Array.isArray(data?.items) ? data.items : [];
        const total = typeof data?.total === "number" ? data.total : items.length;
        setProjects(items);
        setProjectsTotal(total);
      })
      .catch(() => {
        setProjectsError("Не удалось загрузить список проектов");
        setProjects([]);
        setProjectsTotal(0);
      })
      .finally(() => setIsProjectsLoading(false));
  };
  useEffect(() => {
    loadDashboard();
    loadProjects();
  }, []);

  const runs: DashboardCalcRunSummary[] = useMemo(
    () => dashboard?.recent_calc_runs ?? [],
    [dashboard?.recent_calc_runs],
  );

  const handleSeedProject = async () => {
    setIsSeeding(true);
    try {
      await seedDemoProject();
      loadProjects();
    } catch (e) {
      setProjectsError("Не удалось создать демо-проект");
    } finally {
      setIsSeeding(false);
    }
  };

  return (
    <div className="page">
      <div className="card wide-card">
        <header className="page-header">
          <div>
            <h1>GrindLab — технологическое моделирование</h1>
            <div className="meta-row">
              <span className="meta-item">Расчёты измельчения и сравнение сценариев</span>
            </div>
            {dashboard.user?.email && (
              <div className="meta-row muted">Пользователь: {dashboard.user.email}</div>
            )}
          </div>
          <div className="actions">
            <button className="btn secondary" onClick={() => navigate("/calc-scenarios")}>
              Сценарии расчёта
            </button>
            <button className="btn" onClick={() => navigate("/calc-run")}>
              Новый расчёт измельчения
            </button>
          </div>
        </header>

        {isLoading && <div className="muted">Обновляем дашборд…</div>}
        {error && (
          <div className="general-error">
            {error}{" "}
            <button className="btn secondary" onClick={loadDashboard}>
              Повторить
            </button>
          </div>
        )}

        <section className="section">
          <div className="section-heading">
            <h2>Проекты</h2>
            <p className="section-subtitle">Мои проекты (всего {projectsTotal})</p>
          </div>
          {isProjectsLoading && <div className="muted">Загружаем проекты…</div>}
          {projectsError && (
            <div className="general-error">
              {projectsError}{" "}
              <button className="btn secondary" onClick={loadProjects}>
                Повторить
              </button>
            </div>
          )}
          {projects.length ? (
            <ul className="projects-list">
              {projects.slice(0, 5).map((p) => (
                <li key={p.id} className="project-item">
                  <div className="project-name">{p.name}</div>
                  {p.updated_at && <div className="project-updated">Обновлён: {formatDateTime(p.updated_at)}</div>}
                  <div className="project-actions">
                    <button
                      className="btn secondary"
                      type="button"
                      onClick={() => navigate(`/projects/${p.id}`)}
                    >
                      Открыть
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state">
              <div>Проектов пока нет.</div>
              <button className="btn" onClick={handleSeedProject} disabled={isSeeding}>
                {isSeeding ? "Создаём..." : "Создать демо-проект"}
              </button>
            </div>
          )}
        </section>

        <section className="section">
          <div className="kpi-grid">
            <div className="metric-card">
              <div className="stat-label">Расчёты</div>
              <div className="stat-value">{dashboard.summary?.calc_runs_total ?? 0}</div>
            </div>
            <div className="metric-card">
              <div className="stat-label">Сценарии</div>
              <div className="stat-value">{dashboard.summary?.scenarios_total ?? 0}</div>
            </div>
            <div className="metric-card">
              <div className="stat-label">Комментарии</div>
              <div className="stat-value">{dashboard.summary?.comments_total ?? 0}</div>
            </div>
            <div className="metric-card">
              <div className="stat-label">Проекты</div>
              <div className="stat-value">{dashboard.summary?.projects_total ?? 0}</div>
            </div>
          </div>
        </section>

        <section className="section">
          <div className="section-heading">
            <h2>Последние расчёты измельчения</h2>
            <p className="section-subtitle">Показаны последние расчёты модели grind_mvp_v1</p>
          </div>

          {runs.length ? (
            <div className="calc-runs-grid">
              {runs.map((run) => (
                <div className="calc-run-card" key={run.id}>
                  <div className="card-top">
                    <div className="card-title">
                      {run.scenario_name ? `Расчёт «${run.scenario_name}»` : "Расчёт"}
                      {run.is_baseline && <span className="badge badge-baseline">Базовый</span>}
                    </div>
                    <span className="chip small">{run.model_version || "model"}</span>
                  </div>
                  <div className="card-meta">
                    {run.plant_name || run.plant_id ? (
                      <span>Фабрика: {run.plant_name ?? run.plant_id}</span>
                    ) : (
                      <span>Фабрика не указана</span>
                    )}
                  </div>
                  <div className="card-meta">
                    {run.flowsheet_name || run.flowsheet_version_id ? (
                      <span>Схема: {run.flowsheet_name ?? run.flowsheet_version_id}</span>
                    ) : (
                      <span>Схема не указана</span>
                    )}
                  </div>
                  {run.comment && <div className="run-card-comment">Комментарий: {run.comment}</div>}
                  <div className="card-meta muted">{formatDateTime(run.created_at)}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              Пока нет ни одного расчёта измельчения.
              <br />
              Нажмите «Новый расчёт измельчения», чтобы создать первый.
            </div>
          )}
        </section>

        <section className="section">
          <div className="section-heading">
            <h2>Последние комментарии</h2>
            <p className="section-subtitle">Сообщения по сценариям и расчётам</p>
          </div>
          {dashboard.recent_comments?.length ? (
            <ul className="comments-list">
              {dashboard.recent_comments.map((c, idx) => (
                <li key={idx} className="comment-item">
                  {c.text || JSON.stringify(c)}
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state">Нет комментариев</div>
          )}
        </section>
      </div>
    </div>
  );
};

export default HomePage;
