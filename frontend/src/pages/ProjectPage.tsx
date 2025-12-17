import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import BackToHomeButton from "../components/BackToHomeButton";
import { fetchProjectDashboard, ProjectDashboardResponse } from "../api/client";

export const ProjectPage = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<ProjectDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = () => {
    if (!projectId) {
      setError("Не указан идентификатор проекта");
      setData(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    fetchProjectDashboard(projectId)
      .then((resp) => setData(resp))
      .catch(() => setError("Не удалось загрузить проект"))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadDashboard();
  }, [projectId]);

  const summary = data?.summary;

  return (
    <div className="page">
      <div className="card wide-card">
        <div className="page-header">
          <div>
            <h1>{data?.project?.name ?? "Проект"}</h1>
            {data?.project?.description && <p className="muted">{data.project.description}</p>}
          </div>
          <div className="actions">
            {projectId && (
              <button className="btn" type="button" onClick={() => navigate(`/calc-run?projectId=${projectId}`)}>
                РќРѕРІС‹Р№ СЂР°СЃС‡РµС‚ РґР»СЏ РїСЂРѕРµРєС‚Р°
              </button>
            )}
            <BackToHomeButton />
          </div>
        </div>

        {isLoading && <div className="muted">Загружаем проект…</div>}
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
                  <div className="stat-label">Версии схем</div>
                  <div className="stat-value">
                    {summary?.flowsheet_versions_total ?? data.flowsheet_versions.length ?? 0}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="stat-label">Сценарии</div>
                  <div className="stat-value">{summary?.scenarios_total ?? data.scenarios.length ?? 0}</div>
                </div>
                <div className="metric-card">
                  <div className="stat-label">Расчёты</div>
                  <div className="stat-value">{summary?.calc_runs_total ?? 0}</div>
                </div>
              </div>
            </section>

            <section className="section">
              <div className="section-heading">
                <h2>Сценарии</h2>
                <p className="section-subtitle">
                  Всего {summary?.scenarios_total ?? data.scenarios.length ?? 0}
                </p>
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
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="empty-state">Сценариев пока нет.</div>
              )}
            </section>

            <section className="section">
              <div className="section-heading">
                <h2>Версии схем</h2>
                <p className="section-subtitle">
                  Всего {summary?.flowsheet_versions_total ?? data.flowsheet_versions.length ?? 0}
                </p>
              </div>
              {data.flowsheet_versions.length ? (
                <ul className="projects-list">
                  {data.flowsheet_versions.map((version) => (
                    <li key={version.id} className="project-item">
                      <div className="project-name">{version.version_label || "Версия схемы"}</div>
                      <div className="project-updated muted">ID: {version.id}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="empty-state">Версии схем пока не прикреплены.</div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
};

export default ProjectPage;
