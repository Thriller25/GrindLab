import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import BackToHomeButton from "../components/BackToHomeButton";
import {
  CalcScenario,
  deleteCalcScenario,
  fetchProjectDashboard,
  isAuthExpiredError,
  ProjectDashboardResponse,
  createProjectComment,
  ProjectComment,
  setCalcScenarioBaseline,
  updateScenario,
} from "../api/client";
import { hasAuth } from "../auth/authProvider";

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
  const [recommendModal, setRecommendModal] = useState<{
    id: string;
    name: string;
    is_recommended: boolean;
    recommendation_note: string;
  } | null>(null);
  const [commentModal, setCommentModal] = useState<{ id: string; name: string } | null>(null);
  const [commentText, setCommentText] = useState("");
  const [commentSaving, setCommentSaving] = useState(false);
  const [deleteCandidate, setDeleteCandidate] = useState<CalcScenario | null>(null);
  const [scenarioSaving, setScenarioSaving] = useState(false);
  const [recommendationSaving, setRecommendationSaving] = useState(false);
  const [scenarioDeleting, setScenarioDeleting] = useState(false);
  const [baselineUpdatingId, setBaselineUpdatingId] = useState<string | null>(null);
  const [refreshPending, setRefreshPending] = useState(
    () => new URLSearchParams(location.search).get("refresh") === "1",
  );
  const [pendingScenarioId, setPendingScenarioId] = useState<string | null>(
    () => new URLSearchParams(location.search).get("scenarioId"),
  );
  const [highlightedScenarioId, setHighlightedScenarioId] = useState<string | null>(null);
  const scenarioRowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});
  const highlightTimeoutRef = useRef<number | null>(null);
  const [authExpired, setAuthExpired] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(() => hasAuth());

  const handleAuthExpired = () => {
    setAuthExpired(true);
    setIsAuthenticated(false);
    setRecommendModal(null);
    setRenameModal(null);
    setCommentModal(null);
    setCommentText("");
    setDeleteCandidate(null);
    setScenarioActionError(null);
    setScenarioActionMessage(null);
  };

  const getErrorMessage = (err: unknown, fallback: string) => {
    const detail = (err as any)?.response?.data?.detail;
    if (typeof detail === "string" && /[а-яА-ЯёЁ]/.test(detail)) {
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
  const baselineScenario = useMemo(() => scenarios.find((s) => s.is_baseline) ?? null, [scenarios]);

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
      setError("Не указан идентификатор проекта");
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
    const syncAuthState = () => {
      const hasToken = hasAuth();
      setIsAuthenticated(hasToken);
      if (hasToken) setAuthExpired(false);
    };
    syncAuthState();
    window.addEventListener("storage", syncAuthState);
    window.addEventListener("focus", syncAuthState);
    return () => {
      window.removeEventListener("storage", syncAuthState);
      window.removeEventListener("focus", syncAuthState);
    };
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const scenarioIdFromQuery = params.get("scenarioId");
    if (!scenarioIdFromQuery) return;
    setPendingScenarioId(scenarioIdFromQuery);
    params.delete("scenarioId");
    const nextSearch = params.toString();
    navigate(
      {
        pathname: location.pathname,
        search: nextSearch ? `?${nextSearch}` : "",
      },
      { replace: true },
    );
  }, [location.pathname, location.search, navigate]);

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

  useEffect(() => {
    if (!pendingScenarioId) return;
    const row = scenarioRowRefs.current[pendingScenarioId];
    if (row) {
      scrollToScenario(pendingScenarioId);
      setPendingScenarioId(null);
      return;
    }
    if (scenarios.length && !scenarios.some((scenario) => scenario.id === pendingScenarioId)) {
      setPendingScenarioId(null);
    }
  }, [pendingScenarioId, scenarios, scrollToScenario]);

  useEffect(
    () => () => {
      if (highlightTimeoutRef.current) {
        window.clearTimeout(highlightTimeoutRef.current);
      }
    },
    [],
  );

  const recommendationActionsDisabled = !isAuthenticated || authExpired;
  const summary = data?.summary;
  const commentActionDisabled = !isAuthenticated || authExpired || commentSaving;
  const commentActionTitle = !isAuthenticated
    ? "Требуется вход"
    : authExpired
      ? "Сессия истекла. Войдите снова."
      : undefined;

  const handleStartRun = () => {
    if (!projectId) return;
    navigate(`/calc-run?projectId=${projectId}`);
  };

  const handleRunScenario = (scenarioId: string) => {
    if (!projectId) return;
    navigate(`/calc-run?projectId=${projectId}&scenarioId=${scenarioId}`);
  };

  const handleCompareScenario = (scenarioId: string) => {
    if (!projectId) return;
    navigate(`/projects/${projectId}/scenarios/${scenarioId}/compare`);
  };

  const handleSetBaseline = async (scenarioId: string) => {
    if (!projectId) return;
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    setBaselineUpdatingId(scenarioId);
    try {
      await setCalcScenarioBaseline(scenarioId);
      setScenarioActionMessage("Базовый сценарий обновлён.");
      loadDashboard();
    } catch (err) {
      if (isAuthExpiredError(err)) {
        handleAuthExpired();
      } else {
        setScenarioActionError(getErrorMessage(err, "Не удалось обновить базовый сценарий. Попробуйте ещё раз."));
      }
    } finally {
      setBaselineUpdatingId(null);
    }
  };

  const handleCreateScenario = () => {
    if (!projectId) return;
    navigate(`/calc-scenarios?projectId=${projectId}`);
  };

  const handleOpenRunDetails = useCallback(
    (runId: string) => {
      navigate(`/calc-runs/${runId}`);
    },
    [navigate],
  );

  const scrollToScenario = useCallback(
    (scenarioId: string) => {
      setHighlightedScenarioId(scenarioId);
      const row = scenarioRowRefs.current[scenarioId];
      if (row) {
        row.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      if (highlightTimeoutRef.current) {
        window.clearTimeout(highlightTimeoutRef.current);
      }
      highlightTimeoutRef.current = window.setTimeout(() => {
        setHighlightedScenarioId((current) => (current === scenarioId ? null : current));
        highlightTimeoutRef.current = null;
      }, 4000);
    },
    [],
  );

  const handleOpenCommentTarget = (comment: ProjectComment) => {
    if (comment.calc_run_id) {
      handleOpenRunDetails(comment.calc_run_id);
      return;
    }
    if (comment.scenario_id) {
      scrollToScenario(comment.scenario_id);
    }
  };

  const handleRenameClick = (scenario: CalcScenario) => {
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    setRenameModal({ id: scenario.id, name: scenario.name, description: scenario.description || "" });
  };

  const handleRecommendationClick = (scenario: CalcScenario, nextValue: boolean) => {
    if (recommendationActionsDisabled) return;
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    setRecommendModal({
      id: scenario.id,
      name: scenario.name,
      is_recommended: nextValue,
      recommendation_note: scenario.recommendation_note || "",
    });
  };

  const handleEditRecommendationNote = (scenario: CalcScenario) => {
    handleRecommendationClick(scenario, scenario.is_recommended);
  };

  const handleDeleteClick = (scenario: CalcScenario) => {
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    setDeleteCandidate(scenario);
  };

  const handleOpenCommentModal = (scenario: CalcScenario) => {
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    setCommentModal({ id: scenario.id, name: scenario.name });
    setCommentText("");
  };

  const handleSaveComment = async () => {
    if (!commentModal || !projectId) return;
    const trimmed = commentText.trim();
    if (!trimmed) return;
    setCommentSaving(true);
    setScenarioActionError(null);
    try {
      await createProjectComment(projectId, { scenario_id: commentModal.id, text: trimmed });
      setScenarioActionMessage("Комментарий сохранён.");
      setCommentModal(null);
      setCommentText("");
      loadDashboard();
    } catch (err) {
      if (isAuthExpiredError(err)) {
        handleAuthExpired();
      } else {
        const status = (err as any)?.response?.status;
        if (status === 403) {
          setScenarioActionError("Недостаточно прав для изменения комментариев.");
        } else if (status === 401) {
          handleAuthExpired();
        } else {
          setScenarioActionError("Не удалось сохранить комментарий. Попробуйте ещё раз.");
        }
      }
    } finally {
      setCommentSaving(false);
    }
  };

  const handleRenameScenario = async () => {
    if (!renameModal) return;
    const trimmedName = renameModal.name.trim();
    if (!trimmedName) {
      setScenarioActionError("Введите название сценария");
      return;
    }
    setScenarioSaving(true);
    setScenarioActionError(null);
    try {
      await updateScenario(renameModal.id, {
        name: trimmedName,
        description: renameModal.description.trim() ? renameModal.description.trim() : undefined,
      });
      setScenarioActionMessage("Сценарий переименован.");
      setRenameModal(null);
      loadDashboard();
    } catch (err) {
      if (isAuthExpiredError(err)) {
        handleAuthExpired();
      } else {
        setScenarioActionError(getErrorMessage(err, "Не удалось переименовать сценарий. Попробуйте ещё раз."));
      }
    } finally {
      setScenarioSaving(false);
    }
  };

  const handleSaveRecommendation = async () => {
    if (!recommendModal || recommendationActionsDisabled) return;
    setRecommendationSaving(true);
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    const trimmedNote = recommendModal.recommendation_note.trim();
    const noteToSave = recommendModal.is_recommended && trimmedNote ? trimmedNote : null;
    try {
      await updateScenario(recommendModal.id, {
        is_recommended: recommendModal.is_recommended,
        recommendation_note: noteToSave,
      });
      setScenarioActionMessage(
        recommendModal.is_recommended ? "Сценарий отмечен как рекомендованный." : "Рекомендация снята.",
      );
      setRecommendModal(null);
      loadDashboard();
    } catch (err) {
      if (isAuthExpiredError(err)) {
        handleAuthExpired();
      } else {
        const status = (err as any)?.response?.status;
        if (status === 401) {
          handleAuthExpired();
        } else if (status === 403) {
          setScenarioActionError("Недостаточно прав для изменения рекомендации.");
        } else {
          setScenarioActionError(
            getErrorMessage(err, "Не удалось обновить рекомендацию. Проверьте права доступа и попробуйте снова."),
          );
        }
      }
    } finally {
      setRecommendationSaving(false);
    }
  };

  const handleDeleteScenario = async () => {
    if (!deleteCandidate) return;
    setScenarioActionError(null);
    setScenarioActionMessage(null);
    setScenarioDeleting(true);
    try {
      await deleteCalcScenario(deleteCandidate.id);
      setScenarioActionMessage("Сценарий удалён.");
      setDeleteCandidate(null);
      loadDashboard();
    } catch (err) {
      if (isAuthExpiredError(err)) {
        handleAuthExpired();
      } else {
        const status = (err as any)?.response?.status;
        if (status === 409) {
          setScenarioActionError("Нельзя удалить сценарий: по нему уже есть расчёты.");
        } else {
          setScenarioActionError("Не удалось удалить сценарий. Попробуйте ещё раз.");
        }
      }
    } finally {
      setScenarioDeleting(false);
    }
  };

  return (
    <div className="page">
      <div className="card wide-card">
        <div className="page-header">
          <div>
            <h1>{data?.project?.name ?? "Проект"}</h1>
            {data?.project?.description && <p className="muted">{data.project.description}</p>}
          </div>
          <div className="actions">
            <button className="btn secondary" type="button" onClick={loadDashboard} disabled={isLoading}>
              Обновить
            </button>
            {projectId && (
              <button className="btn secondary" type="button" onClick={handleCreateScenario}>
                Создать сценарий
              </button>
            )}
            {projectId && (
              <button className="btn" type="button" onClick={handleStartRun}>
                Запустить расчёт проекта
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
                                <li
                                  key={run.id}
                                  className="project-item"
                                  onClick={() => handleOpenRunDetails(run.id)}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter" && e.currentTarget === e.target) handleOpenRunDetails(run.id);
                                  }}
                                  role="button"
                                  tabIndex={0}
                                  style={{ cursor: "pointer" }}
                                >
                                  <div className="project-name">
                                    {run.scenario_name || "Без сценария"}
                                    {run.is_baseline && <span className="badge badge-baseline">Базовый</span>}
                                  </div>
                                  <div className="project-updated muted">{formatDateTime(run.started_at)}</div>
                                  {run.status && <div className="chip small">{run.status}</div>}
                                  <div className="actions" style={{ marginTop: 6 }}>
                                    <button
                                      className="btn secondary"
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleOpenRunDetails(run.id);
                                      }}
                                    >
                                      Открыть
                                    </button>
                                  </div>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div className="empty-state">Нет запусков.</div>
                          )}
                        </section>

            <section className="section">
              <div className="section-heading">
                <h2>Последние комментарии</h2>
                <p className="section-subtitle">Всего: {summary?.comments_total ?? data?.recent_comments?.length ?? 0}</p>
              </div>
              {data?.recent_comments?.length ? (
                <ul className="comments-list">
                  {data.recent_comments.map((comment) => (
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
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="empty-state">Комментариев пока нет.</div>
              )}
            </section>

            <section className="section">
              <div className="section-heading">
                <h2>Сценарии</h2>
                <p className="section-subtitle">Всего: {summary?.scenarios_total ?? scenarios.length ?? 0}</p>
              </div>
              {authExpired && <div className="alert error">Сессия истекла. Войдите снова.</div>}
              {scenarioActionError && <div className="alert error">{scenarioActionError}</div>}
              {scenarioActionMessage && <div className="alert success">{scenarioActionMessage}</div>}
              {scenarios.length ? (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Название</th>
                      <th>Версия схемы</th>
                      <th>Базовый</th>
                      <th>Рекомендован</th>
                      <th>Обновлено</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scenarios.map((scenario) => {
                      const versionLabel =
                        flowsheetVersionNameById[String(scenario.flowsheet_version_id)] || String(scenario.flowsheet_version_id);
                      return (
                        <tr
                          key={scenario.id}
                          data-scenario-id={scenario.id}
                          ref={(node) => {
                            scenarioRowRefs.current[scenario.id] = node;
                          }}
                          style={highlightedScenarioId === scenario.id ? { backgroundColor: "#fff6e5" } : undefined}
                        >
                          <td>
                            <div className="project-name">
                              {scenario.name}
                              {scenario.is_recommended && <span className="badge badge-recommended">Рекомендован</span>}
                              {scenario.is_baseline && <span className="badge badge-baseline">Базовый</span>}
                            </div>
                            {scenario.description && <div className="muted">{scenario.description}</div>}
                          </td>
                          <td>{versionLabel}</td>
                          <td>{scenario.is_baseline ? "Да" : "Нет"}</td>
                          <td>
                            {scenario.is_recommended ? "Да" : "—"}
                            {scenario.recommendation_note && <div className="muted">{scenario.recommendation_note}</div>}
                          </td>
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
                                onClick={() => handleOpenCommentModal(scenario)}
                                disabled={commentActionDisabled}
                                title={commentActionTitle}
                              >
                                Комментарий
                              </button>
                              <button
                                className="btn secondary"
                                type="button"
                                onClick={() => handleRenameClick(scenario)}
                                disabled={scenarioSaving}
                              >
                                Переименовать
                              </button>
                              <button
                                className="btn secondary"
                                type="button"
                                onClick={() => handleEditRecommendationNote(scenario)}
                                disabled={recommendationSaving || recommendationActionsDisabled}
                              >
                                Комментарий
                              </button>
                              {!scenario.is_recommended && (
                                <button
                                  className="btn secondary"
                                  type="button"
                                  onClick={() => handleRecommendationClick(scenario, true)}
                                  disabled={recommendationSaving || recommendationActionsDisabled}
                                >
                                  Рекомендовать
                                </button>
                              )}
                              {scenario.is_recommended && (
                                <button
                                  className="btn secondary"
                                  type="button"
                                  onClick={() => handleRecommendationClick(scenario, false)}
                                  disabled={recommendationSaving || recommendationActionsDisabled}
                                >
                                  Снять рекомендацию
                                </button>
                              )}
                              {!scenario.is_baseline && (
                                <button
                                  className="btn secondary"
                                  type="button"
                                  onClick={() => handleCompareScenario(scenario.id)}
                                  disabled={!baselineScenario}
                                  title={
                                    baselineScenario
                                      ? undefined
                                      : "Назначьте базовый сценарий, чтобы сравнить результаты"
                                  }
                                >
                                  Сравнить с базовым
                                </button>
                              )}
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
                                Удалить
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
            <h3>Переименовать сценарий</h3>
            <label>
              Название
              <input
                value={renameModal.name}
                onChange={(e) => setRenameModal({ ...renameModal, name: e.target.value })}
                placeholder="Название сценария"
              />
            </label>
            <label>
              Описание
              <textarea
                value={renameModal.description}
                onChange={(e) => setRenameModal({ ...renameModal, description: e.target.value })}
                placeholder="Необязательное описание"
              />
            </label>
            <div className="actions modal-actions">
              <button className="btn secondary" type="button" onClick={() => setRenameModal(null)} disabled={scenarioSaving}>
                Отмена
              </button>
              <button
                className="btn"
                type="button"
                onClick={handleRenameScenario}
                disabled={scenarioSaving || !renameModal.name.trim()}
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}
      {recommendModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Рекомендация для сценария</h3>
            <p className="section-subtitle">{recommendModal.name}</p>
            <label className="filter-checkbox">
              <input
                type="checkbox"
                checked={recommendModal.is_recommended}
                onChange={(e) =>
                  setRecommendModal({
                    ...recommendModal,
                    is_recommended: e.target.checked,
                  })
                }
              />
              <span>Отметить как рекомендованный</span>
            </label>
            <label>
              Комментарий (опционально)
              <textarea
                value={recommendModal.recommendation_note}
                onChange={(e) =>
                  setRecommendModal({
                    ...recommendModal,
                    recommendation_note: e.target.value,
                  })
                }
                placeholder="Короткое пояснение для команды проекта"
              />
            </label>
            <div className="actions modal-actions">
              <button className="btn secondary" type="button" onClick={() => setRecommendModal(null)} disabled={recommendationSaving}>
                Отмена
              </button>
              <button className="btn" type="button" onClick={handleSaveRecommendation} disabled={recommendationSaving}>
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}
      {commentModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Комментарий к сценарию</h3>
            <p className="section-subtitle">{commentModal.name}</p>
            <label>
              Текст комментария
              <textarea
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="Введите комментарий"
              />
            </label>
            <div className="actions modal-actions">
              <button className="btn secondary" type="button" onClick={() => setCommentModal(null)} disabled={commentSaving}>
                Отмена
              </button>
              <button
                className="btn"
                type="button"
                onClick={handleSaveComment}
                disabled={commentSaving || !commentText.trim() || !isAuthenticated || authExpired}
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteCandidate && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Удаление сценария</h3>
            <p className="section-subtitle">Удалить сценарий «{deleteCandidate.name}» из проекта?</p>
            {deleteCandidate.is_baseline && (
              <p className="section-subtitle">Это базовый сценарий. При удалении базовый статус будет снят.</p>
            )}
            <div className="actions modal-actions">
              <button className="btn secondary" type="button" onClick={() => setDeleteCandidate(null)} disabled={scenarioDeleting}>
                Отмена
              </button>
              <button className="btn danger" type="button" onClick={handleDeleteScenario} disabled={scenarioDeleting}>
                Удалить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectPage;
