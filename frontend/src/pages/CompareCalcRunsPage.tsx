import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { fetchCalcRunById, GrindMvpRunDetail } from "../api/client";
import BackToHomeButton from "../components/BackToHomeButton";

const formatNumber = (value: number | undefined, digits = 2) => (value != null ? value.toFixed(digits) : "—");
const formatSize = (value: number | undefined) => (value != null ? value.toFixed(3) : "—");
const formatPercent = (value: number | undefined) => (value != null ? value.toFixed(1) : "—");
const formatDateTime = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }) : "—";

type BetterDirection = "up" | "down";

type MetricKey =
  | "throughput_tph"
  | "product_p80_mm"
  | "specific_energy_kwh_per_t"
  | "circulating_load_percent"
  | "mill_utilization_percent";

const KPI_CONFIG: Record<
  MetricKey,
  {
    betterDirection: BetterDirection;
  }
> = {
  throughput_tph: { betterDirection: "up" },
  product_p80_mm: { betterDirection: "down" },
  specific_energy_kwh_per_t: { betterDirection: "down" },
  circulating_load_percent: { betterDirection: "down" },
  mill_utilization_percent: { betterDirection: "up" },
};

function getDeltaClass(
  metricKey: MetricKey,
  baselineValue: number | undefined,
  currentValue: number | undefined,
): "better" | "worse" | "neutral" {
  const cfg = KPI_CONFIG[metricKey];
  if (!cfg || baselineValue == null || currentValue == null) return "neutral";
  const delta = currentValue - baselineValue;
  if (Math.abs(delta) < 1e-9) return "neutral";
  const isBetter =
    (cfg.betterDirection === "up" && delta > 0) || (cfg.betterDirection === "down" && delta < 0);
  return isBetter ? "better" : "worse";
}

export const CompareCalcRunsPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const params = new URLSearchParams(location.search);
  const idsParam = params.get("ids") ?? "";
  const ids = idsParam
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const [runs, setRuns] = useState<GrindMvpRunDetail[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [baselineId, setBaselineId] = useState<string | null>(null);

  useEffect(() => {
    if (ids.length < 2) {
      setError("Для сравнения выберите минимум два расчёта");
      setRuns([]);
      return;
    }
    setIsLoading(true);
    setError(null);
    Promise.all(ids.map((id) => fetchCalcRunById(id)))
      .then((results) => {
        setRuns(results);
        setBaselineId((prev) => prev || results[0]?.id || null);
      })
      .catch(() => setError("Не удалось загрузить данные для сравнения"))
      .finally(() => setIsLoading(false));
  }, [idsParam]);

  const baselineRun = useMemo(() => runs.find((r) => r.id === baselineId) || runs[0], [baselineId, runs]);

  const bestWorst = (values: (number | undefined)[], lowerBetter: boolean) => {
    const present = values.map((v, i) => ({ v, i })).filter(({ v }) => v != null);
    if (!present.length) return { best: null as number | null, worst: null as number | null };
    const vals = present.map((p) => p.v as number);
    const bestVal = lowerBetter ? Math.min(...vals) : Math.max(...vals);
    const worstVal = lowerBetter ? Math.max(...vals) : Math.min(...vals);
    return {
      best: present.find((p) => p.v === bestVal)?.i ?? null,
      worst: present.find((p) => p.v === worstVal)?.i ?? null,
    };
  };

  const comparisons: Record<MetricKey, { best: number | null; worst: number | null }> = useMemo(() => {
    const throughput = runs.map((r) => r.result.kpi.throughput_tph);
    const p80 = runs.map((r) => r.result.kpi.product_p80_mm);
    const energy = runs.map((r) => r.result.kpi.specific_energy_kwh_per_t);
    const cload = runs.map((r) => r.result.kpi.circulating_load_percent);
    const util = runs.map((r) => r.result.kpi.mill_utilization_percent);

    return {
      throughput_tph: bestWorst(throughput, false),
      product_p80_mm: bestWorst(p80, true),
      specific_energy_kwh_per_t: bestWorst(energy, true),
      circulating_load_percent: bestWorst(cload, false),
      mill_utilization_percent: bestWorst(util, false),
    };
  }, [runs]);

  const metrics: { key: MetricKey; label: string; formatter: (v: number | undefined) => string; lowerBetter: boolean }[] =
    [
      { key: "throughput_tph", label: "Производительность, т/ч", formatter: (v) => formatNumber(v, 2), lowerBetter: false },
      { key: "product_p80_mm", label: "P80 продукта, мм", formatter: formatSize, lowerBetter: true },
      { key: "specific_energy_kwh_per_t", label: "Удельная энергия, кВт·ч/т", formatter: (v) => formatNumber(v, 2), lowerBetter: true },
      { key: "circulating_load_percent", label: "Циркуляционная нагрузка, %", formatter: formatPercent, lowerBetter: false },
      { key: "mill_utilization_percent", label: "Использование мощности, %", formatter: formatPercent, lowerBetter: false },
    ];

  const valueFor = (run: GrindMvpRunDetail, key: MetricKey) => run.result.kpi[key];
  const deltaFor = (run: GrindMvpRunDetail, key: MetricKey) => {
    if (!baselineRun) return null;
    if (run.id === baselineRun.id) return null;
    const base = valueFor(baselineRun, key);
    const val = valueFor(run, key);
    if (base == null || val == null) return null;
    return val - base;
  };

  const flowsheetUniform =
    runs.length > 0 &&
    runs.every(
      (r) =>
        (r.flowsheet_version_id || r.input.flowsheet_version_id) ===
        (runs[0].flowsheet_version_id || runs[0].input.flowsheet_version_id),
    );

  if (ids.length < 2) {
    return (
      <div className="page">
        <div className="card">
          <p>Для сравнения выберите минимум два расчёта.</p>
          <button className="btn" onClick={() => navigate("/")}>
            На главную
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="card wide-card">
        <header className="page-header">
          <div>
            <h1>Сравнение расчётов измельчения</h1>
            <div className="meta-row">
              <span className="meta-item">Выбранные расчёты: {ids.join(", ")}</span>
              <span className="meta-sep">•</span>
              <span className="meta-item">
                {flowsheetUniform
                  ? `Версия схемы: ${runs[0]?.flowsheet_version_id || runs[0]?.input.flowsheet_version_id || "—"}`
                  : "Сравниваются разные версии схем"}
              </span>
            </div>
          </div>
          <div className="actions">
            <BackToHomeButton />
            <button className="btn secondary" onClick={() => navigate("/calc-run")}>
              Новый расчёт измельчения
            </button>
          </div>
        </header>

        {isLoading && <div className="muted">Загрузка сравнения…</div>}
        {error && <div className="general-error">{error}</div>}

        {!isLoading && !error && runs.length >= 2 && (
          <>
            {!flowsheetUniform && (
              <div className="compare-warning">
                <strong>Внимание:</strong> сравниваются расчёты с разными версиями схем. Для корректного анализа лучше
                сравнивать расчёты в рамках одной версии схемы.
              </div>
            )}

            <section className="section">
              <div className="section-heading">
                <h2>Выбранные расчёты</h2>
                <p className="section-subtitle">
                  Базовый для дельт: {baselineRun ? `Расчёт №${baselineRun.id}` : "не выбран"}
                </p>
              </div>
              <div className="calc-runs-grid">
                {runs.map((run) => (
                  <div key={run.id} className="calc-run-card" style={{ cursor: "default" }}>
                    <div className="card-top">
                      <div className="card-title">
                        Расчёт №{run.id}
                        <label style={{ marginLeft: 8, fontSize: 12 }}>
                          <input
                            type="radio"
                            name="baseline"
                            checked={baselineRun?.id === run.id}
                            onChange={() => setBaselineId(run.id)}
                          />{" "}
                          Базовый
                        </label>
                      </div>
                      <span className="chip small">{run.model_version || "model"}</span>
                    </div>
                    <div className="card-meta">
                      <span>Фабрика: {run.plant_id || run.input.plant_id || "—"}</span>
                    </div>
                    <div className="card-meta">
                      <span>Версия схемы: {run.flowsheet_version_id || run.input.flowsheet_version_id || "—"}</span>
                    </div>
                    <div className="card-meta">
                      <span>Сценарий: {run.scenario_name || run.input.scenario_name || "—"}</span>
                    </div>
                    <div className="card-meta muted">Создан: {formatDateTime(run.created_at)}</div>
                  </div>
                ))}
              </div>
            </section>

            <section className="section">
              <div className="section-heading">
                <h2>Ключевые показатели</h2>
                <p className="section-subtitle">
                  Δ рассчитывается как «текущий − базовый расчёт». Зелёным отмечены значения лучше базового, красным — хуже.
                </p>
              </div>
              <table className="compare-table">
                <thead>
                  <tr>
                    <th>Показатель</th>
                    {runs.map((run) => (
                      <th key={run.id}>
                        Расчёт №{run.id}
                        {baselineRun?.id === run.id ? " (базовый)" : ""}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {metrics.map((metric) => {
                    const comp = comparisons[metric.key];
                    return (
                      <tr key={metric.key}>
                        <td>{metric.label}</td>
                        {runs.map((run, idx) => {
                          const val = valueFor(run, metric.key);
                          const delta = deltaFor(run, metric.key);
                          const baselineValue = valueFor(baselineRun, metric.key);
                          const deltaClass =
                            run.id === baselineRun?.id ? "neutral" : getDeltaClass(metric.key, baselineValue, val);
                          const classes = [
                            "kpi-cell",
                            run.id === baselineRun?.id ? "kpi-baseline-cell" : "",
                            deltaClass ? `kpi-cell-${deltaClass}` : "",
                          ]
                            .filter(Boolean)
                            .join(" ");
                          const title =
                            deltaClass === "better"
                              ? "Лучше базового расчёта"
                              : deltaClass === "worse"
                              ? "Хуже базового расчёта"
                              : undefined;
                          return (
                            <td key={run.id} className={classes} title={title}>
                              <div>{metric.formatter(val)}</div>
                              {run.id === baselineRun?.id ? (
                                <div className="delta" style={{ color: "#6b7280" }}>Δ —</div>
                              ) : (
                                delta != null && (
                                  <div
                                    className={`delta ${
                                      delta > 0 ? "delta-positive" : delta < 0 ? "delta-negative" : ""
                                    }`}
                                  >
                                    Δ {delta > 0 ? "+" : ""}
                                    {formatNumber(delta, 2)}
                                  </div>
                                )
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>
          </>
        )}
      </div>
    </div>
  );
};

export default CompareCalcRunsPage;
