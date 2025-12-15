import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  CalcScenario,
  createCalcScenario,
  fetchAllFlowsheetVersions,
  fetchCalcScenariosByFlowsheetVersion,
  FlowsheetVersionSummary,
  setCalcScenarioBaseline,
} from "../api/client";
import BackToHomeButton from "../components/BackToHomeButton";

export const CalcScenariosPage = () => {
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
    fetchAllFlowsheetVersions()
      .then((items) => {
        setFlowsheetVersions(items);
        if (items.length > 0) {
          setSelectedVersionId(items[0].id);
        }
      })
      .catch(() => setError("Не удалось загрузить версии схем"));
  }, []);

  useEffect(() => {
    if (!selectedVersionId) {
      setScenarios([]);
      return;
    }
    setIsLoading(true);
    setError(null);
    fetchCalcScenariosByFlowsheetVersion(selectedVersionId)
      .then(setScenarios)
      .catch(() => setError("Не удалось загрузить сценарии"))
      .finally(() => setIsLoading(false));
  }, [selectedVersionId]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !selectedVersionId) return;
    setIsCreating(true);
    try {
      const created = await createCalcScenario({
        flowsheet_version_id: selectedVersionId,
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
      alert("Не удалось назначить базовый сценарий");
    } finally {
      setBaselineChangingId(null);
    }
  };

  return (
    <div className="page">
      <div className="card wide-card">
        <header className="page-header">
          <div>
            <h1>Сценарии расчёта измельчения</h1>
            <div className="meta-row">
              <span className="meta-item">Шаблоны сценариев для модели grind_mvp_v1.</span>
            </div>
          </div>
          <BackToHomeButton />
        </header>

        <section className="section">
          <div className="section-heading">
            <h2>Версия схемы</h2>
            <p className="section-subtitle">Выберите версию схемы, чтобы увидеть её сценарии.</p>
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
            <h2>Создать сценарий</h2>
            <p className="section-subtitle">
              Для версии: {selectedVersionName || "не выбрана"}
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
            <button className="btn" type="submit" disabled={isCreating || !newName.trim() || !selectedVersionId}>
              Создать сценарий
            </button>
          </form>
        </section>

        <section className="section">
          <div className="section-heading">
            <h2>Список сценариев</h2>
          </div>
          {isLoading && <div className="muted">Загрузка сценариев…</div>}
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
                    <td colSpan={4}>Для этой версии схемы пока нет сценариев.</td>
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
