import { FormEvent, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  CalcScenario,
  createCalcScenario,
  fetchAllFlowsheetVersions,
  fetchCalcScenariosByProject,
  fetchCalcScenariosByFlowsheetVersion,
  fetchProjectDashboard,
  FlowsheetVersionSummary,
  setCalcScenarioBaseline,
} from "../api/client";
import BackToHomeButton from "../components/BackToHomeButton";

export const CalcScenariosPage = () => {
  const location = useLocation();
  const projectIdParam = useMemo(
    () => new URLSearchParams(location.search).get("projectId")?.trim() ?? "",
    [location.search],
  );
  const projectIdNumber = projectIdParam && !Number.isNaN(Number(projectIdParam)) ? Number(projectIdParam) : null;

  const [projectName, setProjectName] = useState<string | null>(null);
  const [flowsheetVersions, setFlowsheetVersions] = useState<FlowsheetVersionSummary[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string>("");
  const [scenarios, setScenarios] = useState<CalcScenario[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [baselineChangingId, setBaselineChangingId] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    if (projectIdParam) {
      fetchProjectDashboard(projectIdParam)
        .then((resp) => {
          const versions = resp.flowsheet_versions.map((fv) => ({
            id: fv.id,
            name: fv.version_label ?? fv.id,
            flowsheet_id: fv.flowsheet_id ?? "",
          }));
          setProjectName(resp.project?.name ?? null);
          setFlowsheetVersions(versions);
          if (versions.length > 0) {
            setSelectedVersionId(versions[0].id);
          }
        })
        .catch(() => setError("Не удалось загрузить версии схем для проекта"));
      return;
    }

    fetchAllFlowsheetVersions()
      .then((items) => {
        setFlowsheetVersions(items);
        if (items.length > 0) {
          setSelectedVersionId(items[0].id);
        }
      })
      .catch(() => setError("Не удалось загрузить версии схем"));
  }, [projectIdParam]);

  useEffect(() => {
    if (!selectedVersionId) {
      setScenarios([]);
      return;
    }
    setIsLoading(true);
    setError(null);
    const loader = projectIdParam
      ? fetchCalcScenariosByProject(projectIdParam, selectedVersionId)
      : fetchCalcScenariosByFlowsheetVersion(selectedVersionId);
    loader
      .then((items) => setScenarios(items))
      .catch(() => setError("Не удалось загрузить список сценариев"))
      .finally(() => setIsLoading(false));
  }, [projectIdParam, selectedVersionId]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !selectedVersionId) return;
    if (projectIdNumber === null) {
      setError("Не указан projectId для сценария");
      return;
    }
    setIsCreating(true);
    try {
      const created = await createCalcScenario({
        flowsheet_version_id: selectedVersionId,
        project_id: projectIdNumber,
        name: newName.trim(),
        description: newDescription.trim() || undefined,
        default_input_json: {
          feed_tph: 500,
          target_p80_microns: 150,
        },
        is_baseline: false,
      });
      setScenarios((prev) => [...prev, created]);
      setNewName("");
      setNewDescription("");
    } catch {
      setError("Не удалось создать сценарий");
    } finally {
      setIsCreating(false);
    }
  };

  const selectedVersionName = useMemo(() => {
    const fv = flowsheetVersions.find((f) => f.id === selectedVersionId);
    return fv ? `${fv.name} (ID ${fv.id})` : "";
  }, [flowsheetVersions, selectedVersionId]);

  const handleMakeBaseline = async (scenarioId: string) => {
    try {
      setBaselineChangingId(scenarioId);
      const updated = await setCalcScenarioBaseline(scenarioId);
      setScenarios((prev) =>
        prev.map((s) => (s.id === updated.id ? updated : { ...s, is_baseline: false })),
      );
    } catch {
      alert("Не удалось отметить базовый сценарий");
    } finally {
      setBaselineChangingId(null);
    }
  };

  return (
    <div className="page">
      <div className="card wide-card">
        <header className="page-header">
          <div>
            <h1>Сценарии расчётов</h1>
            {projectName && <div className="meta-row">Проект: {projectName}</div>}
            {!projectIdParam && (
              <div className="meta-row">
                <span className="meta-item">Для создания сценария передайте projectId в query.</span>
              </div>
            )}
          </div>
          <BackToHomeButton />
        </header>

        <section className="section">
          <div className="section-heading">
            <h2>Версия схемы</h2>
            <p className="section-subtitle">Выберите версию схемы, для которой создаёте сценарий</p>
          </div>
          <select
            className="input"
            value={selectedVersionId}
            onChange={(e) => setSelectedVersionId(e.target.value)}
          >
            {flowsheetVersions.map((fv) => (
              <option key={fv.id} value={fv.id}>
                {fv.name} (ID {fv.id})
              </option>
            ))}
          </select>
        </section>

        <section className="section">
          <div className="section-heading">
            <h2>Новый сценарий</h2>
            <p className="section-subtitle">
              Текущая версия: {selectedVersionName || "не выбрана"} | ProjectId: {projectIdParam || "—"}
            </p>
          </div>
          <form className="scenario-form" onSubmit={handleCreate}>
            <label>
              Название сценария
              <input value={newName} onChange={(e) => setNewName(e.target.value)} />
            </label>
            <label>
              Описание
              <textarea value={newDescription} onChange={(e) => setNewDescription(e.target.value)} />
            </label>
            <button
              className="btn"
              type="submit"
              disabled={isCreating || !newName.trim() || !selectedVersionId || projectIdNumber === null}
            >
              Создать сценарий
            </button>
          </form>
        </section>

        <section className="section">
          <div className="section-heading">
            <h2>Сценарии</h2>
          </div>
          {isLoading && <div className="muted">Загрузка сценариев...</div>}
          {error && <div className="general-error">{error}</div>}
          {!isLoading && !error && (
            <table className="table scenarios-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Название</th>
                  <th>Описание</th>
                  <th>Базовый</th>
                </tr>
              </thead>
              <tbody>
                {scenarios.length ? (
                  scenarios.map((s) => (
                    <tr key={s.id}>
                      <td>{s.id}</td>
                      <td>{s.name}</td>
                      <td>{s.description || "—"}</td>
                      <td>
                        {s.is_baseline ? (
                          <span>Да</span>
                        ) : (
                          <button
                            type="button"
                            className="btn secondary"
                            onClick={() => handleMakeBaseline(s.id)}
                            disabled={baselineChangingId === s.id}
                          >
                            Сделать базовым
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4}>Нет сценариев для выбранной версии.</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
};

export default CalcScenariosPage;
