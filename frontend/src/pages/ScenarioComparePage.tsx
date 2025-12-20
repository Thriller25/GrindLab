import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  CalcRunListItem,
  CalcScenario,
  fetchCalcRunsByFlowsheetVersion,
  fetchGrindMvpRun,
  fetchProjectDashboard,
  GrindMvpRunDetail,
  ProjectDashboardResponse,
} from "../api/client";
import BackToHomeButton from "../components/BackToHomeButton";

type MetricDirection = "higher" | "lower";
type MetricVerdict = "better" | "worse" | "same" | "unknown";
type VerdictFilter = "all" | "better" | "worse";

type MetricConfig = {
  key: string;
  label: string;
  direction: MetricDirection;
  digits?: number;
  sourceKeys: string[];
};

const DELTA_EPSILON = 1e-6;
const BASELINE_EPSILON = 1e-9;

const VERDICT_LABELS: Record<MetricVerdict, string> = {
  better: "Лучше",
  worse: "Хуже",
  same: "Без изменений",
  unknown: "—",
};

const METRICS: MetricConfig[] = [
  {
    key: "throughput_tph",
    label: "Производительность, т/ч",
    direction: "higher",
    digits: 2,
    sourceKeys: ["throughput_tph"],
  },
  {
    key: "p80_mm",
    label: "P80 продукта, мм",
    direction: "lower",
    digits: 2,
    sourceKeys: ["product_p80_mm", "p80_mm"],
  },
  {
    key: "specific_energy_kwhpt",
    label: "Удельная энергия, кВт·ч/т",
    direction: "lower",
    digits: 2,
    sourceKeys: ["specific_energy_kwh_per_t", "specific_energy_kwhpt"],
  },
  {
    key: "recirc_load_pct",
    label: "Рециркуляционная нагрузка, %",
    direction: "lower",
    digits: 2,
    sourceKeys: ["circulating_load_percent", "recirc_load_pct"],
  },
  {
    key: "mill_load_pct",
    label: "Загрузка мельницы, %",
    direction: "higher",
    digits: 2,
    sourceKeys: ["mill_utilization_percent", "mill_load_pct"],
    // TODO: позже заменить на оценку по целевому диапазону.
  },
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

const kpiValue = (run: GrindMvpRunDetail | null, keys: string[]): number | null => {
  const kpi = (run?.result?.kpi ?? {}) as Record<string, unknown>;
  for (const key of keys) {
    const value = kpi[key];
    if (typeof value === "number") return value;
  }
  return null;
};

const deltaClass = (delta: number | null, direction: MetricDirection) => {
  if (delta == null || Math.abs(delta) < DELTA_EPSILON) return "";
  const isBetter = direction === "higher" ? delta > 0 : delta < 0;
  return isBetter ? "delta-positive" : "delta-negative";
};

const calcVerdict = (baseValue: number | null, scenarioValue: number | null, direction: MetricDirection): MetricVerdict => {
  if (baseValue == null || scenarioValue == null) return "unknown";
  const delta = scenarioValue - baseValue;
  if (Math.abs(delta) < DELTA_EPSILON) return "same";
  const isBetter = direction === "higher" ? delta > 0 : delta < 0;
  return isBetter ? "better" : "worse";
};

const impactValue = (deltaPct: number | null, delta: number | null, verdict: MetricVerdict) => {
  if (verdict === "same") return 0;
  if (deltaPct != null) return Math.abs(deltaPct);
  if (delta != null) return Math.abs(delta);
  return -Infinity;
};

type MetricRow = {
  metric: MetricConfig;
  baseValue: number | null;
  scenarioValue: number | null;
  delta: number | null;
  deltaPct: number | null;
  verdict: MetricVerdict;
  index: number;
};

const impactOfRow = (row: MetricRow) => impactValue(row.deltaPct, row.delta, row.verdict);

export const ScenarioComparePage = () => {
  const { projectId, scenarioId } = useParams<{ projectId: string; scenarioId: string }>();
  const navigate = useNavigate();

  const [dashboard, setDashboard] = useState<ProjectDashboardResponse | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<CalcScenario | null>(null);
  const [baselineScenario, setBaselineScenario] = useState<CalcScenario | null>(null);
  const [scenarioRuns, setScenarioRuns] = useState<CalcRunListItem[]>([]);
  const [baselineRuns, setBaselineRuns] = useState<CalcRunListItem[]>([]);
  const [selectedScenarioRunId, setSelectedScenarioRunId] = useState<string | null>(null);
  const [selectedBaselineRunId, setSelectedBaselineRunId] = useState<string | null>(null);
  const [scenarioRun, setScenarioRun] = useState<GrindMvpRunDetail | null>(null);
  const [baselineRun, setBaselineRun] = useState<GrindMvpRunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [runsLoading, setRunsLoading] = useState(false);
  const [scenarioRunLoading, setScenarioRunLoading] = useState(false);
  const [baselineRunLoading, setBaselineRunLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [missingState, setMissingState] = useState<MissingState | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("default");
  const [showOnlyDifferent, setShowOnlyDifferent] = useState(false);
  const [verdictFilter, setVerdictFilter] = useState<VerdictFilter>("all");

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
        message: "Сценарии относятся к разным версиям схем. Сравнение доступно только при одинаковой версии.",
        allowBaselineRun: false,
        allowScenarioRun: false,
      });
      setScenarioRuns([]);
      setBaselineRuns([]);
      setSelectedScenarioRunId(null);
      setSelectedBaselineRunId(null);
      setScenarioRun(null);
      setBaselineRun(null);
      return;
    }

    let cancelled = false;
    const loadRuns = async () => {
      setRunsLoading(true);
      setRunsError(null);
      setMissingState(null);
      setScenarioRuns([]);
      setBaselineRuns([]);
      setSelectedScenarioRunId(null);
      setSelectedBaselineRunId(null);
      setScenarioRun(null);
      setBaselineRun(null);
      try {
        const [scenarioResp, baselineResp] = await Promise.all([
          fetchCalcRunsByFlowsheetVersion(selectedScenario.flowsheet_version_id, {
            limit: 10,
            status: "success",
            scenarioId: selectedScenario.id,
          }),
          fetchCalcRunsByFlowsheetVersion(baselineScenario.flowsheet_version_id, {
            limit: 10,
            status: "success",
            scenarioId: baselineScenario.id,
          }),
        ]);

        if (cancelled) return;

        const scenarioItems = Array.isArray(scenarioResp?.items) ? scenarioResp.items : [];
        const baselineItems = Array.isArray(baselineResp?.items) ? baselineResp.items : [];

        setScenarioRuns(scenarioItems);
        setBaselineRuns(baselineItems);

        if (!scenarioItems.length && !baselineItems.length) {
          setMissingState({
            message: "Нет успешных запусков базового и выбранного сценариев. Запустите расчёты, чтобы сравнить.",
            allowBaselineRun: true,
            allowScenarioRun: true,
          });
          return;
        }

        if (!scenarioItems.length) {
          setMissingState({
            message: "Нет успешных запусков выбранного сценария.",
            allowBaselineRun: false,
            allowScenarioRun: true,
          });
          return;
        }

        if (!baselineItems.length) {
          setMissingState({
            message: "Нет успешных запусков базового сценария.",
            allowBaselineRun: true,
            allowScenarioRun: false,
          });
          return;
        }

        const nextScenarioId =
          scenarioItems.find((run) => run.id === selectedScenarioRunId)?.id ?? scenarioItems[0]?.id ?? null;
        const nextBaselineId =
          baselineItems.find((run) => run.id === selectedBaselineRunId)?.id ?? baselineItems[0]?.id ?? null;

        setSelectedScenarioRunId(nextScenarioId);
        setSelectedBaselineRunId(nextBaselineId);
      } catch (err) {
        setRunsError("Не удалось загрузить расчёты для сравнения");
      } finally {
        if (!cancelled) {
          setRunsLoading(false);
        }
      }
    };

    loadRuns();

    return () => {
      cancelled = true;
    };
  }, [selectedScenario, baselineScenario]);

  useEffect(() => {
    if (!selectedScenarioRunId) {
      setScenarioRun(null);
      return;
    }
    if (scenarioRun?.id === selectedScenarioRunId) return;
    setScenarioRun(null);
    let cancelled = false;
    setScenarioRunLoading(true);
    setRunsError(null);
    fetchGrindMvpRun(selectedScenarioRunId)
      .then((data) => {
        if (cancelled) return;
        if (data?.id === selectedScenarioRunId) {
          setScenarioRun(data);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setScenarioRun(null);
        setRunsError("Не удалось загрузить выбранный расчёт сценария");
      })
      .finally(() => {
        if (!cancelled) {
          setScenarioRunLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedScenarioRunId]);

  useEffect(() => {
    if (!selectedBaselineRunId) {
      setBaselineRun(null);
      return;
    }
    if (baselineRun?.id === selectedBaselineRunId) return;
    setBaselineRun(null);
    let cancelled = false;
    setBaselineRunLoading(true);
    setRunsError(null);
    fetchGrindMvpRun(selectedBaselineRunId)
      .then((data) => {
        if (cancelled) return;
        if (data?.id === selectedBaselineRunId) {
          setBaselineRun(data);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setBaselineRun(null);
        setRunsError("Не удалось загрузить выбранный расчёт базового сценария");
      })
      .finally(() => {
        if (!cancelled) {
          setBaselineRunLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedBaselineRunId]);

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

  const getVersionLabel = (id?: string | null) => {
    if (!id) return "";
    const key = String(id);
    return flowsheetVersionNameById[key] || key;
  };

  const scenarioRunOption = useMemo(
    () => scenarioRuns.find((run) => run.id === selectedScenarioRunId) ?? null,
    [scenarioRuns, selectedScenarioRunId],
  );

  const baselineRunOption = useMemo(
    () => baselineRuns.find((run) => run.id === selectedBaselineRunId) ?? null,
    [baselineRuns, selectedBaselineRunId],
  );

  const formatRunLabel = (run: CalcRunListItem | null) => {
    if (!run) return formatDateTime(null);
    const dateValue = run.started_at || run.finished_at || null;
    const parts: string[] = [];
    parts.push(formatDateTime(dateValue));
    const idLabel = shortRunId(run.id);
    if (idLabel) parts.push(idLabel);
    const versionLabel = getVersionLabel(run.flowsheet_version_id);
    if (versionLabel) parts.push(versionLabel);
    return parts.join(" • ");
  };

  const comparisonLoading = runsLoading || scenarioRunLoading || baselineRunLoading;

  const comparisonMetrics = useMemo<MetricRow[]>(() => {
    if (!scenarioRun || !baselineRun) return [];

    return METRICS.map((metric, index) => {
      const baseValue = kpiValue(baselineRun, metric.sourceKeys);
      const scenarioValue = kpiValue(scenarioRun, metric.sourceKeys);
      const delta = baseValue != null && scenarioValue != null ? scenarioValue - baseValue : null;
      const deltaPct =
        baseValue != null && scenarioValue != null && Math.abs(baseValue) > BASELINE_EPSILON
          ? ((scenarioValue - baseValue) / baseValue) * 100
          : null;
      const verdict = calcVerdict(baseValue, scenarioValue, metric.direction);

      return { metric, baseValue, scenarioValue, delta, deltaPct, verdict, index };
    });
  }, [baselineRun, scenarioRun]);

  const sortedMetrics = useMemo(() => {
    const sorted = [...comparisonMetrics];
    if (sortMode !== "absDelta") return sorted.sort((a, b) => a.index - b.index);

    return sorted.sort((a, b) => {
      const aVal = impactOfRow(a);
      const bVal = impactOfRow(b);
      if (aVal === bVal) return a.index - b.index;
      return bVal - aVal;
    });
  }, [comparisonMetrics, sortMode]);

  const filteredMetrics = useMemo(
    () =>
      sortedMetrics.filter((item) => {
        if (showOnlyDifferent && item.verdict === "same") return false;
        if (verdictFilter === "better") return item.verdict === "better";
        if (verdictFilter === "worse") return item.verdict === "worse";
        return true;
      }),
    [showOnlyDifferent, sortedMetrics, verdictFilter],
  );

  const summaryCounts = useMemo<Record<MetricVerdict, number>>(() => {
    const initial: Record<MetricVerdict, number> = { better: 0, worse: 0, same: 0, unknown: 0 };
    comparisonMetrics.forEach(({ verdict }) => {
      initial[verdict] += 1;
    });
    return initial;
  }, [comparisonMetrics]);

  const topImprovements = useMemo(
    () =>
      comparisonMetrics
        .filter((item) => item.verdict === "better")
        .sort((a, b) => impactOfRow(b) - impactOfRow(a))
        .slice(0, 3),
    [comparisonMetrics],
  );

  const topWorsenings = useMemo(
    () =>
      comparisonMetrics
        .filter((item) => item.verdict === "worse")
        .sort((a, b) => impactOfRow(b) - impactOfRow(a))
        .slice(0, 3),
    [comparisonMetrics],
  );

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
                Запустить сценарий
              </button>
            )}
            {allowBaselineRun && baselineScenario && (
              <button
                className="btn secondary"
                type="button"
                onClick={() => handleRunScenario(baselineScenario.id)}
              >
                Запустить базовый
              </button>
            )}
          </div>
        )}
      </div>
    );
  };

  const formatImpactLine = (item: MetricRow) => {
    const digits = item.metric.digits ?? 2;
    const pctText = item.deltaPct == null ? "" : ` (${formatDelta(item.deltaPct, 2)}%)`;
    return `${item.metric.label}: ${formatDelta(item.delta, digits)}${pctText}`;
  };

  const renderTopList = (items: MetricRow[]) => {
    if (!items.length) return <div className="muted">—</div>;
    return (
      <ul>
        {items.map((item) => (
          <li key={item.metric.key}>{formatImpactLine(item)}</li>
        ))}
      </ul>
    );
  };

  const renderComparisonTable = (rows: MetricRow[]) => {
    if (!rows.length) {
      return <div className="muted">Нет метрик по выбранным фильтрам.</div>;
    }

    return (
      <table className="table striped">
        <thead>
          <tr>
            <th>Метрика</th>
            <th>Базовый</th>
            <th>Сценарий</th>
            <th>Δ</th>
            <th>%Δ</th>
            <th>Оценка</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ metric, baseValue, scenarioValue, delta, deltaPct, verdict }) => {
            const className = deltaClass(delta, metric.direction);
            const digits = metric.digits ?? 2;
            const rowClass =
              verdict === "better" ? "kpi-row-better" : verdict === "worse" ? "kpi-row-worse" : "";
            const verdictClass =
              verdict === "better"
                ? "verdict verdict-better"
                : verdict === "worse"
                ? "verdict verdict-worse"
                : verdict === "same"
                ? "verdict verdict-same"
                : "verdict verdict-unknown";

            return (
              <tr key={metric.key} className={rowClass || undefined}>
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
                <td className="align-left">
                  <span className={verdictClass}>{VERDICT_LABELS[verdict]}</span>
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

              <div className="grid" style={{ gap: 12, marginBottom: 12 }}>
                <label className="filter-control">
                  Запуск сценария
                  <select
                    className="input"
                    value={selectedScenarioRunId ?? ""}
                    onChange={(e) => setSelectedScenarioRunId(e.target.value || null)}
                    disabled={runsLoading || !scenarioRuns.length}
                  >
                    {scenarioRuns.length ? (
                      scenarioRuns.map((run) => (
                        <option key={run.id} value={run.id}>
                          {formatRunLabel(run)}
                        </option>
                      ))
                    ) : (
                      <option value="">Нет успешных запусков</option>
                    )}
                  </select>
                </label>
                <label className="filter-control">
                  Запуск базового сценария
                  <select
                    className="input"
                    value={selectedBaselineRunId ?? ""}
                    onChange={(e) => setSelectedBaselineRunId(e.target.value || null)}
                    disabled={runsLoading || !baselineRuns.length}
                  >
                    {baselineRuns.length ? (
                      baselineRuns.map((run) => (
                        <option key={run.id} value={run.id}>
                          {formatRunLabel(run)}
                        </option>
                      ))
                    ) : (
                      <option value="">Нет успешных запусков</option>
                    )}
                  </select>
                </label>
              </div>

              <div className="grid">
                <div className="stat">
                  <div className="stat-label">Сценарий</div>
                  <div className="stat-value">{selectedScenario.name}</div>
                  <div className="muted">Версия схемы: {selectedVersionLabel}</div>
                  <div className="muted">
                    Запуск для сравнения:{" "}
                    {scenarioRunOption ? (
                      <span title={`Расчёт №${scenarioRunOption.id}`}>{formatRunLabel(scenarioRunOption)}</span>
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
                    Запуск для сравнения:{" "}
                    {baselineRunOption ? (
                      <span title={`Расчёт №${baselineRunOption.id}`}>{formatRunLabel(baselineRunOption)}</span>
                    ) : (
                      "—"
                    )}
                  </div>
                </div>
              </div>

              {missingState && renderMissing(missingState)}
              {!missingState && comparisonLoading && <div className="muted">Загружаем метрики...</div>}
              {!missingState && !comparisonLoading && scenarioRun && baselineRun && (
                <section className="section">
                  <div className="section-heading">
                    <h2>Сравнение KPI</h2>
                    <p className="section-subtitle">
                      Δ и %Δ считаются относительно базового сценария. Оценка учитывает направление, в котором KPI
                      считается лучше.
                    </p>
                  </div>
                  <div className="meta-row" style={{ marginBottom: 6 }}>
                    <span className="meta-item">Улучшилось: {summaryCounts.better}</span>
                    <span className="meta-sep">•</span>
                    <span className="meta-item">Ухудшилось: {summaryCounts.worse}</span>
                    <span className="meta-sep">•</span>
                    <span className="meta-item">Без изменений: {summaryCounts.same}</span>
                    <span className="meta-sep">•</span>
                    <span className="meta-item">Не определено: {summaryCounts.unknown}</span>
                  </div>
                  <div
                    className="grid"
                    style={{
                      gap: 10,
                      gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                      marginTop: 6,
                      marginBottom: 10,
                    }}
                  >
                    <div>
                      <div className="stat-label">Топ-3 улучшения</div>
                      {renderTopList(topImprovements)}
                    </div>
                    <div>
                      <div className="stat-label">Топ-3 ухудшения</div>
                      {renderTopList(topWorsenings)}
                    </div>
                  </div>
                  <div className="filters-bar">
                    <label className="filter-control" style={{ maxWidth: 260 }}>
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
                    <label className="filter-control" style={{ maxWidth: 220 }}>
                      Показать
                      <select
                        className="input"
                        value={verdictFilter}
                        onChange={(e) => setVerdictFilter(e.target.value as VerdictFilter)}
                      >
                        <option value="all">Все</option>
                        <option value="better">Только улучшения</option>
                        <option value="worse">Только ухудшения</option>
                      </select>
                    </label>
                    <label className="filter-checkbox" style={{ marginBottom: 6 }}>
                      <input
                        type="checkbox"
                        checked={showOnlyDifferent}
                        onChange={(e) => setShowOnlyDifferent(e.target.checked)}
                      />
                      Показывать только отличающиеся
                    </label>
                  </div>
                  {renderComparisonTable(filteredMetrics)}
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
