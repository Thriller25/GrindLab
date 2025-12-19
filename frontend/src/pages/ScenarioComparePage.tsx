import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  CalcScenario,
  fetchGrindMvpRun,
  fetchLatestCalcRunByScenario,
  fetchProjectDashboard,
  GrindMvpRunDetail,
  ProjectDashboardResponse,
} from "../api/client";
import BackToHomeButton from "../components/BackToHomeButton";

type MetricKey =
  | "throughput_tph"
  | "product_p80_mm"
  | "specific_energy_kwh_per_t"
  | "circulating_load_percent"
  | "mill_utilization_percent";

type BetterDirection = "up" | "down";

const METRICS: Array<{ key: MetricKey; label: string; unit?: string; better: BetterDirection; digits?: number }> = [
  { key: "throughput_tph", label: "Производительность, т/ч", better: "up", digits: 2 },
  { key: "product_p80_mm", label: "P80 продукта, мм", better: "down", digits: 2 },
  { key: "specific_energy_kwh_per_t", label: "Удельная энергия, кВт·ч/т", better: "down", digits: 2 },
  { key: "circulating_load_percent", label: "Рециркуляционная нагрузка, %", better: "down", digits: 2 },
  { key: "mill_utilization_percent", label: "Загрузка мельницы, %", better: "up", digits: 2 },
];

type MissingState = { message: string; allowScenarioRun?: boolean; allowBaselineRun?: boolean };
type SortMode = "default" | "absDelta";

const formatNumber = (value: number | null | undefined, digits = 2) =>
  value == null ? "—" : value.toFixed(digits);

const formatDelta = (value: number | null, digits = 2) => {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
};

const shortRunId = (id?: string | null) => {
  if (!id) return null;
  const str = String(id);
  return str.includes("-") ? str.split("-")[0] : str.slice(0, 8);
};

const formatDateTime = (value?: string | null) =>
  value
    ? new Date(value).toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";

const kpiValue = (run: GrindMvpRunDetail | null, key: MetricKey): number | null => {
  const value = run?.result?.kpi?.[key];
  return typeof value === "number" ? value : null;
};

const deltaClass = (delta: number | null, better: BetterDirection) => {
  if (delta == null || Math.abs(delta) < 1e-9) return "";
  const isBetter = better === "up" ? delta > 0 : delta < 0;
  return isBetter ? "delta-positive" : "delta-negative";
};

export const ScenarioComparePage = () => {
  const { projectId, scenarioId } = useParams<{ projectId: string; scenarioId: string }>();
  const navigate = useNavigate();

  const [dashboard, setDashboard] = useState<ProjectDashboardResponse | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<CalcScenario | null>(null);
  const [baselineScenario, setBaselineScenario] = useState<CalcScenario | null>(null);
  const [scenarioRun, setScenarioRun] = useState<GrindMvpRunDetail | null>(null);
  const [baselineRun, setBaselineRun] = useState<GrindMvpRunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [runsLoading, setRunsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [missingState, setMissingState] = useState<MissingState | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("default");

  const flowsheetVersionNameById = useMemo(() => {
    if (!dashboard?.flowsheet_versions) return {};
    return dashboard.flowsheet_versions.reduce<Record<string, string>>((acc, version) => {
      acc[String(version.id)] = version.version_label || String(version.id);
      return acc;
    }, {});
  }, [dashboard?.flowsheet_versions]);

  useEffect(() => {
    if (!projectId || !scenarioId) {
      setError("Не хватает параметров маршрута для сравнения сценариев");
      return;
    }

    setLoading(true);
    setError(null);
    setMissingState(null);
    setRunsError(null);
    fetchProjectDashboard(projectId)
      .then((data) => {
        setDashboard(data);
        const current = data.scenarios.find((s) => s.id === scenarioId) ?? null;
        const baseline = data.scenarios.find((s) => s.is_baseline) ?? null;
        setSelectedScenario(current);
        setBaselineScenario(baseline);
        if (!current) {
          setError("Сценарий не найден в этом проекте");
        } else if (!baseline) {
          setMissingState({
            message: "В проекте не выбран базовый сценарий. Назначьте его на странице проекта.",
            allowBaselineRun: false,
            allowScenarioRun: false,
          });
        } else {
          setMissingState(null);
        }
      })
      .catch(() => setError("Не удалось загрузить данные проекта"))
      .finally(() => setLoading(false));
  }, [projectId, scenarioId]);

  useEffect(() => {
    if (!selectedScenario) return;
    if (!baselineScenario) return;

    if (selectedScenario.flowsheet_version_id !== baselineScenario.flowsheet_version_id) {
      setRunsError(null);
      setMissingState({
        message: "Базовый сценарий относится к другой версии схемы. Назначьте базовый для этой версии.",
        allowBaselineRun: false,
        allowScenarioRun: false,
      });
      setScenarioRun(null);
      setBaselineRun(null);
      return;
    }

    const loadRuns = async () => {
      setRunsLoading(true);
      setRunsError(null);
      setMissingState(null);
      setScenarioRun(null);
      setBaselineRun(null);
      try {
        const [selectedLatest, baselineLatest] = await Promise.all([
          fetchLatestCalcRunByScenario(selectedScenario.id).catch((err: any) => {
            if (err?.response?.status === 404) return null;
            throw err;
          }),
          fetchLatestCalcRunByScenario(baselineScenario.id).catch((err: any) => {
            if (err?.response?.status === 404) return null;
            throw err;
          }),
        ]);

        if (!selectedLatest) {
          setMissingState({
            message: "Нет успешных расчётов для выбранного сценария.",
            allowBaselineRun: false,
            allowScenarioRun: true,
          });
          return;
        }

        if (!baselineLatest) {
          setMissingState({
            message: "Нет успешного базового расчёта.",
            allowBaselineRun: true,
            allowScenarioRun: false,
          });
          return;
        }

        const [selectedRun, baseRun] = await Promise.all([
          fetchGrindMvpRun(selectedLatest.id),
          fetchGrindMvpRun(baselineLatest.id),
        ]);
        setScenarioRun(selectedRun);
        setBaselineRun(baseRun);
      } catch (err) {
        setRunsError("Не удалось загрузить сравнение");
      } finally {
        setRunsLoading(false);
      }
    };

    loadRuns();
  }, [selectedScenario, baselineScenario]);

  const selectedVersionLabel = useMemo(() => {
    if (!selectedScenario) return "—";
    const id = String(selectedScenario.flowsheet_version_id);
    return flowsheetVersionNameById[id] || id;
  }, [flowsheetVersionNameById, selectedScenario]);

  const baselineVersionLabel = useMemo(() => {
    if (!baselineScenario) return "—";
    const id = String(baselineScenario.flowsheet_version_id);
    return flowsheetVersionNameById[id] || id;
  }, [baselineScenario, flowsheetVersionNameById]);

  const handleRunScenario = (id: string) => {
    if (!projectId) return;
    navigate(`/calc-run?projectId=${projectId}&scenarioId=${id}`);
  };

  const handleBackToProject = () => {
    if (projectId) {
      navigate(`/projects/${projectId}`);
    } else {
      navigate("/");
    }
  };

  const renderMissing = (state: MissingState) => {
    const allowScenarioRun = state.allowScenarioRun ?? true;
    const allowBaselineRun = state.allowBaselineRun ?? false;
    const hasActions =
      (allowScenarioRun && selectedScenario) || (allowBaselineRun && baselineScenario);
    return (
      <div className="empty-state" style={{ marginTop: 12 }}>
        <div>{state.message}</div>
        {hasActions && (
          <div className="actions" style={{ marginTop: 10 }}>
            {allowScenarioRun && selectedScenario && (
              <button className="btn" type="button" onClick={() => handleRunScenario(selectedScenario.id)}>
                Запустить расчёт выбранного сценария
              </button>
            )}
            {allowBaselineRun && baselineScenario && (
              <button
                className="btn secondary"
                type="button"
                onClick={() => handleRunScenario(baselineScenario.id)}
              >
                Запустить расчёт базового сценария
              </button>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderComparisonTable = () => {
    if (!scenarioRun || !baselineRun) return null;

    const metrics = METRICS.map((metric, index) => {
      const baseValue = kpiValue(baselineRun, metric.key);
      const scenarioValue = kpiValue(scenarioRun, metric.key);
      const delta = baseValue != null && scenarioValue != null ? scenarioValue - baseValue : null;
      const deltaPct =
        baseValue != null && scenarioValue != null && Math.abs(baseValue) > 1e-9
          ? ((scenarioValue - baseValue) / baseValue) * 100
          : null;
      return { metric, baseValue, scenarioValue, delta, deltaPct, index };
    });

    const sorted = [...metrics].sort((a, b) => {
      if (sortMode !== "absDelta") return a.index - b.index;
      const aVal = a.deltaPct == null ? -1 : Math.abs(a.deltaPct);
      const bVal = b.deltaPct == null ? -1 : Math.abs(b.deltaPct);
      if (aVal === bVal) return a.index - b.index;
      return bVal - aVal;
    });

    return (
      <table className="table striped">
        <thead>
          <tr>
            <th>Метрика</th>
            <th>Базовый</th>
            <th>Сценарий</th>
            <th>Δ</th>
            <th>%Δ</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(({ metric, baseValue, scenarioValue, delta, deltaPct }) => {
            const className = deltaClass(delta, metric.better);
            const digits = metric.digits ?? 2;
            return (
              <tr key={metric.key}>
                <td>{metric.label}</td>
                <td className="align-right">{formatNumber(baseValue, digits)}</td>
                <td className="align-right">{formatNumber(scenarioValue, digits)}</td>
                <td className="align-right">
                  <span className={`delta ${className}`}>{formatDelta(delta, 2)}</span>
                </td>
                <td className="align-right">
                  <span className={`delta ${className}`}>
                    {deltaPct == null ? "—" : `${formatDelta(deltaPct, 2)}%`}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  };

  return (
    <div className="page">
      <div className="card wide-card">
        <header className="page-header">
          <div>
            <h1>Сравнение сценария с базовым</h1>
            <div className="meta-row">
              <span className="meta-item">Проект: {dashboard?.project?.name ?? projectId ?? "—"}</span>
              <span className="meta-sep">•</span>
              <span className="meta-item">Сценарий: {selectedScenario?.name ?? "—"}</span>
              <span className="meta-sep">•</span>
              <span className="meta-item">Базовый: {baselineScenario?.name ?? "—"}</span>
            </div>
            <div className="meta-row">
              <span className="meta-item">Версия схемы: {selectedVersionLabel}</span>
              <span className="meta-sep">•</span>
              <span className="meta-item">
                Обновлено: {formatDateTime(selectedScenario?.updated_at || selectedScenario?.created_at)}
              </span>
              {baselineScenario && (
                <>
                  <span className="meta-sep">•</span>
                  <span className="meta-item">
                    Базовый обновлён: {formatDateTime(baselineScenario.updated_at || baselineScenario.created_at)}
                  </span>
                </>
              )}
            </div>
          </div>
          <div className="actions">
            <button className="btn secondary" type="button" onClick={handleBackToProject}>
              К проекту
            </button>
            <BackToHomeButton />
          </div>
        </header>

        {loading && <div className="muted">Загружаем данные проекта...</div>}
        {!loading && error && <div className="general-error">{error}</div>}

        {!loading && !error && selectedScenario && (
          <>
            {runsError && <div className="general-error">{runsError}</div>}

            <section className="section">
              <div className="section-heading">
                <h2>Последние успешные расчёты</h2>
                <p className="section-subtitle">
                  Используем последние успешные запуски сценариев для расчёта дельт по KPI.
                </p>
              </div>

              <div className="grid">
                <div className="stat">
                  <div className="stat-label">Сценарий</div>
                  <div className="stat-value">{selectedScenario.name}</div>
                  <div className="muted">Версия схемы: {selectedVersionLabel}</div>
                  <div className="muted">
                    Последний расчёт:{" "}
                    {scenarioRun ? (
                      <span title={`Расчёт №${scenarioRun.id}`}>
                        №{shortRunId(scenarioRun.id)} от {formatDateTime(scenarioRun.created_at)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </div>
                </div>
                <div className="stat">
                  <div className="stat-label">Базовый сценарий</div>
                  <div className="stat-value">{baselineScenario?.name ?? "—"}</div>
                  <div className="muted">Версия схемы: {baselineVersionLabel}</div>
                  <div className="muted">
                    Последний расчёт:{" "}
                    {baselineRun ? (
                      <span title={`Расчёт №${baselineRun.id}`}>
                        №{shortRunId(baselineRun.id)} от {formatDateTime(baselineRun.created_at)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </div>
                </div>
              </div>

              {missingState && renderMissing(missingState)}
              {!missingState && runsLoading && <div className="muted">Загружаем метрики...</div>}
              {!missingState && !runsLoading && scenarioRun && baselineRun && (
                <section className="section">
                  <div className="section-heading">
                    <h2>Сравнение KPI</h2>
                    <p className="section-subtitle">
                      Δ и %Δ считаются относительно базового сценария. Цвет подсветки зависит от того, в какую сторону
                      метрика считается лучше.
                    </p>
                  </div>
                  <div className="filter-control" style={{ maxWidth: 320, marginBottom: 10 }}>
                    <label style={{ gap: 4 }}>
                      Сортировка KPI
                      <select
                        className="input"
                        value={sortMode}
                        onChange={(e) => setSortMode(e.target.value as SortMode)}
                      >
                        <option value="default">По умолчанию</option>
                        <option value="absDelta">По |%Δ| (убывание)</option>
                      </select>
                    </label>
                  </div>
                  {renderComparisonTable()}
                </section>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
};

export default ScenarioComparePage;
