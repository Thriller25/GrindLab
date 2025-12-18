import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import BackToHomeButton from "../components/BackToHomeButton";
import { fetchProjectDashboard, ProjectDashboardResponse } from "../api/client";

export const ProjectPage = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [data, setData] = useState<ProjectDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshPending, setRefreshPending] = useState(
    () => new URLSearchParams(location.search).get("refresh") === "1",
  );

  const recentRuns = useMemo(() => data?.recent_calc_runs ?? [], [data]);

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

  const loadDashboard = useCallback(() => {
    if (!projectId) {
      setError("Project id is required");
      setData(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    fetchProjectDashboard(projectId)
      .then((resp) => setData(resp))
      .catch(() => setError("Не удалось загрузить дашборд проекта"))
      .finally(() => setIsLoading(false));
  }, [projectId]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (!refreshPending || !projectId) return;
    loadDashboard();
    const params = new URLSearchParams(location.search);
    params.delete("refresh");
    const nextSearch = params.toString();
    navigate(
      {
        pathname: location.pathname,
        search: nextSearch ? `?${nextSearch}` : "",
      },
      { replace: true },
    );
    setRefreshPending(false);
  }, [refreshPending, projectId, loadDashboard, location.pathname, location.search, navigate]);

  const summary = data?.summary;

  const handleStartRun = () => {
    if (!projectId) return;
    navigate(`/calc-run?projectId=${projectId}`);
  };

  const handleRunScenario = (scenarioId: string) => {
    if (!projectId) return;
    navigate(`/calc-run?projectId=${projectId}&scenarioId=${scenarioId}`);
  };

  const handleCreateScenario = () => {
    if (!projectId) return;
    navigate(`/calc-scenarios?projectId=${projectId}`);
  };

  return (
    <div className="page">
      <div className="card wide-card">
        <div className="page-header">
          <div>
            <h1>{data?.project?.name ?? "Project"}</h1>
            {data?.project?.description && <p className="muted">{data.project.description}</p>}
          </div>
          <div className="actions">
            <button className="btn secondary" type="button" onClick={loadDashboard} disabled={isLoading}>
              Refresh
            </button>
            {projectId && (
              <button className="btn secondary" type="button" onClick={handleCreateScenario}>
                Create scenario
              </button>
            )}
            {projectId && (
              <button className="btn" type="button" onClick={handleStartRun}>
                Start run for project
              </button>
            )}
            <BackToHomeButton />
          </div>
        </div>

        {isLoading && <div className="muted">Загрузка...</div>}
        {error && (
          <div className="general-error">
            {error}{" "}
            <button className="btn secondary" type="button" onClick={loadDashboard}>
              Повторить
            </button>
          </div>
        )}

        {!isLoading && !error && data && (
          <>
            <section className="section">
              <div className="kpi-grid">
                <div className="metric-card">
                  <div className="stat-label">Версий тех. схем</div>
                  <div className="stat-value">
                    {summary?.flowsheet_versions_total ?? data.flowsheet_versions.length ?? 0}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="stat-label">Сценариев</div>
                  <div className="stat-value">{summary?.scenarios_total ?? data.scenarios.length ?? 0}</div>
                </div>
                <div className="metric-card">
                  <div className="stat-label">Запусков</div>
                  <div className="stat-value">{summary?.calc_runs_total ?? 0}</div>
                </div>
              </div>
            </section>

            <section className="section">
              <div className="section-heading">
                <h2>Последние расчёты</h2>
                <p className="section-subtitle">Всего: {summary?.calc_runs_total ?? recentRuns.length ?? 0}</p>
              </div>
              {recentRuns.length ? (
                <ul className="projects-list">
                  {recentRuns.map((run) => (
                    <li key={run.id} className="project-item">
                      <div className="project-name">
                        {run.scenario_name || "Без сценария"}
                        {run.is_baseline && <span className="badge badge-baseline">Базовый</span>}
                      </div>
                      <div className="project-updated muted">{formatDateTime(run.started_at)}</div>
                      {run.status && <div className="chip small">{run.status}</div>}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="empty-state">Нет запусков.</div>
              )}
            </section>

            <section className="section">
              <div className="section-heading">
                <h2>Сценарии</h2>
                <p className="section-subtitle">Всего: {summary?.scenarios_total ?? data.scenarios.length ?? 0}</p>
              </div>
              {data.scenarios.length ? (
                <ul className="projects-list">
                  {data.scenarios.map((scenario) => (
                    <li key={scenario.id} className="project-item">
                      <div className="project-name">
                        {scenario.name}
                        {scenario.is_baseline && <span className="badge badge-baseline">Базовый</span>}
                      </div>
                      {scenario.description && (
                        <div className="project-updated muted">{scenario.description}</div>
                      )}
                      {projectId && (
                        <div className="actions" style={{ gap: 8 }}>
                          <button
                            className="btn secondary"
                            type="button"
                            onClick={() => handleRunScenario(scenario.id)}
                          >
                            Запустить по сценарию
                          </button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="empty-state">Нет сценариев.</div>
              )}
            </section>

            <section className="section">
              <div className="section-heading">
                <h2>Версии схем</h2>
                <p className="section-subtitle">
                  Всего: {summary?.flowsheet_versions_total ?? data.flowsheet_versions.length ?? 0}
                </p>
              </div>
              {data.flowsheet_versions.length ? (
                <ul className="projects-list">
                  {data.flowsheet_versions.map((version) => (
                    <li key={version.id} className="project-item">
                      <div className="project-name">{version.version_label || "Неизвестная версия"}</div>
                      <div className="project-updated muted">ID: {version.id}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="empty-state">Нет прикрепленных версий схем.</div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
};

export default ProjectPage;
