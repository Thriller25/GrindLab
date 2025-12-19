import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import BackToHomeButton from "../components/BackToHomeButton";
import {
  CalcScenario,
  deleteCalcScenario,
  fetchProjectDashboard,
  ProjectDashboardResponse,
  setCalcScenarioBaseline,
  updateCalcScenario,
} from "../api/client";

export const ProjectPage = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [data, setData] = useState<ProjectDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scenarioActionError, setScenarioActionError] = useState<string | null>(null);
  const [scenarioActionMessage, setScenarioActionMessage] = useState<string | null>(null);
  const [renameModal, setRenameModal] = useState<{ id: string; name: string; description: string } | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<CalcScenario | null>(null);
  const [scenarioSaving, setScenarioSaving] = useState(false);
  const [scenarioDeleting, setScenarioDeleting] = useState(false);
  const [baselineUpdatingId, setBaselineUpdatingId] = useState<string | null>(null);
  const [refreshPending, setRefreshPending] = useState(
    () => new URLSearchParams(location.search).get("refresh") === "1",
  );

  const getErrorMessage = (err: unknown, fallback: string) => {
    const detail = (err as any)?.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    return fallback;
  };

  const recentRuns = useMemo(() => data?.recent_calc_runs ?? [], [data]);
  const flowsheetVersionNameById = useMemo(() => {
    if (!data?.flowsheet_versions) return {};
    return data.flowsheet_versions.reduce<Record<string, string>>((acc, version) => {
      acc[String(version.id)] = version.version_label || String(version.id);
      return acc;
    }, {});
  }, [data]);
  const scenarios = useMemo(() => {
    const items = data?.scenarios ?? [];
    return [...items].sort((a, b) => {
      const aDate = a.updated_at || a.created_at || "";
      const bDate = b.updated_at || b.created_at || "";
      return new Date(bDate).getTime() - new Date(aDate).getTime();
    });
  }, [data]);

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
    setScenarioActionError(null);
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

  const handleSetBaseline = async (scenarioId: string) => {
    if (!projectId) return;
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    setBaselineUpdatingId(scenarioId);
    try {
      await setCalcScenarioBaseline(scenarioId);
      setScenarioActionMessage("Baseline updated");
      loadDashboard();
    } catch (err) {
      setScenarioActionError(getErrorMessage(err, "Unable to update baseline for scenario"));
    } finally {
      setBaselineUpdatingId(null);
    }
  };

  const handleCreateScenario = () => {
    if (!projectId) return;
    navigate(`/calc-scenarios?projectId=${projectId}`);
  };

  const handleRenameClick = (scenario: CalcScenario) => {
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    setRenameModal({ id: scenario.id, name: scenario.name, description: scenario.description || "" });
  };

  const handleDeleteClick = (scenario: CalcScenario) => {
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    setDeleteCandidate(scenario);
  };

  const handleRenameScenario = async () => {
    if (!renameModal) return;
    const trimmedName = renameModal.name.trim();
    if (!trimmedName) {
      setScenarioActionError("Scenario name is required");
      return;
    }
    setScenarioSaving(true);
    setScenarioActionError(null);
    try {
      await updateCalcScenario(renameModal.id, {
        name: trimmedName,
        description: renameModal.description.trim() ? renameModal.description.trim() : undefined,
      });
      setScenarioActionMessage("Scenario renamed");
      setRenameModal(null);
      loadDashboard();
    } catch (err) {
      setScenarioActionError(getErrorMessage(err, "Unable to rename scenario"));
    } finally {
      setScenarioSaving(false);
    }
  };

  const handleDeleteScenario = async () => {
    if (!deleteCandidate) return;
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    setScenarioDeleting(true);
    try {
      await deleteCalcScenario(deleteCandidate.id);
      setScenarioActionMessage("Scenario deleted");
      setDeleteCandidate(null);
      loadDashboard();
    } catch (err) {
      setScenarioActionError(getErrorMessage(err, "Unable to delete scenario"));
    } finally {
      setScenarioDeleting(false);
    }
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
                <p className="section-subtitle">Всего: {summary?.scenarios_total ?? scenarios.length ?? 0}</p>
              </div>
              {scenarioActionError && <div className="alert error">{scenarioActionError}</div>}
              {scenarioActionMessage && <div className="alert success">{scenarioActionMessage}</div>}
              {scenarios.length ? (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Название</th>
                      <th>Версия схемы</th>
                      <th>Baseline</th>
                      <th>Обновлено</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scenarios.map((scenario) => {
                      const versionLabel =
                        flowsheetVersionNameById[String(scenario.flowsheet_version_id)] || String(scenario.flowsheet_version_id);
                      return (
                        <tr key={scenario.id}>
                          <td>
                            <div className="project-name">
                              {scenario.name}
                              {scenario.is_baseline && <span className="badge badge-baseline">Baseline</span>}
                            </div>
                            {scenario.description && <div className="muted">{scenario.description}</div>}
                          </td>
                          <td>{versionLabel}</td>
                          <td>{scenario.is_baseline ? "Да" : "Нет"}</td>
                          <td>{formatDateTime(scenario.updated_at || scenario.created_at)}</td>
                          <td>
                            <div className="actions" style={{ gap: 8 }}>
                              <button
                                className="btn secondary"
                                type="button"
                                onClick={() => handleRunScenario(scenario.id)}
                              >
                                Запустить
                              </button>
                              <button
                                className="btn secondary"
                                type="button"
                                onClick={() => handleRenameClick(scenario)}
                                disabled={scenarioSaving}
                              >
                                Переименовать
                              </button>
                              {!scenario.is_baseline && (
                                <button
                                  className="btn"
                                  type="button"
                                  onClick={() => handleSetBaseline(scenario.id)}
                                  disabled={baselineUpdatingId === scenario.id}
                                >
                                  Сделать базовым
                                </button>
                              )}
                              <button
                                className="btn danger"
                                type="button"
                                onClick={() => handleDeleteClick(scenario)}
                                disabled={scenarioDeleting && deleteCandidate?.id === scenario.id}
                              >
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <div className="empty-state">Пока нет сценариев в проекте.</div>
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
      {renameModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Rename scenario</h3>
            <label>
              Name
              <input
                value={renameModal.name}
                onChange={(e) => setRenameModal({ ...renameModal, name: e.target.value })}
                placeholder="Scenario name"
              />
            </label>
            <label>
              Description
              <textarea
                value={renameModal.description}
                onChange={(e) => setRenameModal({ ...renameModal, description: e.target.value })}
                placeholder="Optional description"
              />
            </label>
            <div className="actions modal-actions">
              <button className="btn secondary" type="button" onClick={() => setRenameModal(null)} disabled={scenarioSaving}>
                Cancel
              </button>
              <button
                className="btn"
                type="button"
                onClick={handleRenameScenario}
                disabled={scenarioSaving || !renameModal.name.trim()}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
      {deleteCandidate && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Delete scenario</h3>
            <p className="section-subtitle">Delete "{deleteCandidate.name}" from this project?</p>
            {deleteCandidate.is_baseline && (
              <p className="section-subtitle">Scenario is baseline; it will be cleared on delete.</p>
            )}
            <div className="actions modal-actions">
              <button className="btn secondary" type="button" onClick={() => setDeleteCandidate(null)} disabled={scenarioDeleting}>
                Cancel
              </button>
              <button className="btn danger" type="button" onClick={handleDeleteScenario} disabled={scenarioDeleting}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectPage;
