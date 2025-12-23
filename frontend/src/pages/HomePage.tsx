import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchDashboard,
  fetchMyProjects,
  fetchProjectComments,
  seedDemoProject,
  DashboardResponse,
  DashboardCalcRunSummary,
  ProjectDTO,
  ProjectComment,
} from "../api/client";

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
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
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentsError, setCommentsError] = useState<string | null>(null);

  const loadComments = useCallback(
    async (projectsList: ProjectDTO[]) => {
      if (!projectsList.length) {
        setDashboard((prev) => ({
          ...prev,
          recent_comments: [],
          summary: { ...(prev.summary ?? {}), comments_total: 0 },
        }));
        return;
      }
      setCommentsLoading(true);
      setCommentsError(null);
      try {
        const topProjects = projectsList.slice(0, 3);
        const responses = await Promise.all(
          topProjects.map((project) =>
            fetchProjectComments(project.id, { limit: 5 }).catch(() => ({ items: [], total: 0 })),
          ),
        );
        const merged = responses.flatMap((resp) => resp?.items ?? []);
        merged.sort((a, b) => {
          const aDate = a.created_at ? new Date(a.created_at).getTime() : 0;
          const bDate = b.created_at ? new Date(b.created_at).getTime() : 0;
          return bDate - aDate;
        });
        setDashboard((prev) => ({
          ...prev,
          recent_comments: merged,
          summary: { ...(prev.summary ?? {}), comments_total: merged.length },
        }));
      } catch (err) {
        setCommentsError("Не удалось загрузить комментарии. Попробуйте ещё раз.");
      } finally {
        setCommentsLoading(false);
      }
    },
    [setDashboard],
  );

  const loadDashboard = () => {
    setIsLoading(true);
    setError(null);
    fetchDashboard()
      .then((data) => setDashboard({ ...emptyDashboard, ...data }))
      .catch(() => {
        setError("Не удалось загрузить дашборд");
        // Keep the existing dashboard visible so layout stays intact on errors
        setDashboard((prev) => prev ?? emptyDashboard);
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
        loadComments(items);
        setProjectsTotal(total);
      })
      .catch(() => {
        setProjectsError("Не удалось загрузить список проектов");
      })
      .finally(() => setIsProjectsLoading(false));
  };
  useEffect(() => {
    loadDashboard();
    loadProjects();
  }, []);

  useEffect(() => {
    const handleFocus = () => {
      loadProjects();
      loadDashboard();
    };
    window.addEventListener("focus", handleFocus);
    return () => {
      window.removeEventListener("focus", handleFocus);
    };
  }, []);

  const runs: DashboardCalcRunSummary[] = useMemo(
    () => dashboard?.recent_calc_runs ?? [],
    [dashboard?.recent_calc_runs],
  );
  const comments = useMemo(() => dashboard?.recent_comments ?? [], [dashboard?.recent_comments]);

  const handleOpenCommentTarget = (comment: ProjectComment) => {
    if (comment.calc_run_id) {
      navigate(`/calc-runs/${comment.calc_run_id}`);
      return;
    }
    if (comment.scenario_id && comment.project_id != null) {
      navigate(`/projects/${comment.project_id}?scenarioId=${comment.scenario_id}`);
      return;
    }
    if (comment.project_id != null) {
      navigate(`/projects/${comment.project_id}`);
    }
  };

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
            <p className="section-subtitle">Всего: {dashboard.summary?.comments_total ?? comments.length}</p>
          </div>
          {commentsError && <div className="alert error">{commentsError}</div>}
          {commentsLoading && <div className="muted">Загружаем комментарии...</div>}
          {!commentsLoading && comments.length ? (
            <ul className="comments-list">
              {comments.map((comment) => (
                <li key={comment.id} className="comment-item">
                  <div className="comment-text">{comment.text}</div>
                  <div className="muted">
                    {(comment.author && comment.author.trim()) || "anonymous"} · {formatDateTime(comment.created_at)}
                    {comment.target_type === "scenario" && " · Сценарий"}
                    {comment.target_type === "calc_run" && " · Запуск"}
                  </div>
                  <div className="actions" style={{ gap: 8, marginTop: 4 }}>
                    {comment.scenario_id && (
                      <button className="btn secondary" type="button" onClick={() => handleOpenCommentTarget(comment)}>
                        К сценарию
                      </button>
                    )}
                    {comment.calc_run_id && (
                      <button className="btn secondary" type="button" onClick={() => handleOpenCommentTarget(comment)}>
                        Открыть запуск
                      </button>
                    )}
                    {!comment.scenario_id && !comment.calc_run_id && comment.project_id != null && (
                      <button className="btn secondary" type="button" onClick={() => handleOpenCommentTarget(comment)}>
                        К проекту
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          ) : !commentsLoading ? (
            <div className="empty-state">Комментариев пока нет.</div>
          ) : null}
        </section>
      </div>
    </div>
  );
};

export default HomePage;
