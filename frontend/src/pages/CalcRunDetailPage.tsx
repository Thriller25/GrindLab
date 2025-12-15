import axios from "axios";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  CalcRunBaselineComparison,
  BaselineKpi,
  fetchFlowsheet,
  fetchFlowsheetVersion,
  fetchGrindMvpRun,
  fetchPlant,
  fetchCalcRunBaselineComparison,
  setCalcRunBaseline,
  updateCalcRunComment,
  FlowsheetDetail,
  FlowsheetVersionDetail,
  GrindMvpBaselineComparison,
  GrindMvpRunDetail,
  PlantDetail,
  getApiBaseUrl,
} from "../api/client";
import BackToHomeButton from "../components/BackToHomeButton";

function KpiDelta({
  label,
  delta,
  deltaPercent,
}: {
  label: string;
  delta?: number | null;
  deltaPercent?: number | null;
}) {
  if (delta == null) return null;
  const sign = delta > 0 ? "+" : "";
  const className = delta > 0 ? "delta delta-positive" : delta < 0 ? "delta delta-negative" : "delta";
  return (
    <div className="metric-card delta-card">
      <div className="stat-label">{label}</div>
      <div className={className}>
        {sign}
        {delta.toFixed(2)}
        {deltaPercent != null && (
          <span className="delta-percent">
            {" "}
            ({sign}
            {deltaPercent.toFixed(1)}%)
          </span>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

type FriendlyMeta = {
  plant: string;
  flowsheet: string;
  version: string;
};

const formatDateTime = (value: string) =>
  new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

const formatNumber = (value: number, digits = 2) => value.toFixed(digits);
const formatSize = (value: number) => value.toFixed(3);
const formatPercent = (value: number) => value.toFixed(1);

export const CalcRunDetailPage = () => {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState<GrindMvpRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [commentDraft, setCommentDraft] = useState<string>("");
  const [isSavingComment, setIsSavingComment] = useState(false);
  const [meta, setMeta] = useState<FriendlyMeta>({
    plant: "",
    flowsheet: "",
    version: "",
  });
  const [metaLoading, setMetaLoading] = useState(false);
  const [baselineComparison, setBaselineComparison] = useState<CalcRunBaselineComparison | null>(null);
  const [baselineLoading, setBaselineLoading] = useState(false);
  const [baselineError, setBaselineError] = useState<string | null>(null);
  const [isSettingBaseline, setIsSettingBaseline] = useState(false);

  useEffect(() => {
    setCommentDraft(run?.comment ?? "");
  }, [run?.comment]);

  useEffect(() => {
    if (!runId) {
      setError("Не указан идентификатор расчёта");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetchGrindMvpRun(runId)
      .then(setRun)
      .catch(() => setError("Не удалось загрузить расчёт"))
      .finally(() => setLoading(false));
  }, [runId]);

  const reloadRunAndBaseline = async (id: string) => {
    const loadedRun = await fetchGrindMvpRun(id);
    setRun(loadedRun);
    setBaselineLoading(true);
    setBaselineError(null);
    try {
      const comparison = await fetchCalcRunBaselineComparison(id);
      setBaselineComparison(comparison);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        setBaselineComparison(null);
      } else {
        setBaselineError("Не удалось загрузить сравнение с базовым расчётом");
      }
    } finally {
      setBaselineLoading(false);
    }
  };

  const handleSaveComment = async () => {
    if (!run) return;
    setIsSavingComment(true);
    try {
      const updated = await updateCalcRunComment(run.id, commentDraft.trim() === "" ? null : commentDraft);
      setRun(updated);
      setCommentDraft(updated.comment ?? "");
      alert("Комментарий сохранён");
    } catch {
      alert("Не удалось сохранить комментарий");
    } finally {
      setIsSavingComment(false);
    }
  };

  useEffect(() => {
    if (!run?.id) {
      setBaselineComparison(null);
      return;
    }

    setBaselineLoading(true);
    setBaselineError(null);

    fetchCalcRunBaselineComparison(run.id)
      .then(setBaselineComparison)
      .catch((error) => {
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          setBaselineComparison(null);
        } else {
          setBaselineError("Не удалось загрузить сравнение с базовым расчётом");
        }
      })
      .finally(() => setBaselineLoading(false));
  }, [run?.id]);

  const handleMakeBaseline = async () => {
    if (!run?.id) return;
    setIsSettingBaseline(true);
    try {
      await setCalcRunBaseline(run.id);
      await reloadRunAndBaseline(run.id);
    } catch (error) {
      alert("Не удалось назначить базовый расчёт");
    } finally {
      setIsSettingBaseline(false);
    }
  };

  useEffect(() => {
    const loadMeta = async () => {
      if (!run) return;
      const plantId = run.input?.plant_id ? String(run.input.plant_id) : run.plant_id || "";
      const flowsheetVersionId = run.input?.flowsheet_version_id
        ? String(run.input.flowsheet_version_id)
        : run.flowsheet_version_id || "";

      let plantLabel = plantId ? `Фабрика ID ${plantId}` : "Фабрика не указана";
      let flowsheetLabel = "Схема не указана";
      let versionLabel = flowsheetVersionId ? `Версия ID ${flowsheetVersionId}` : "Версия не указана";

      setMeta({ plant: plantLabel, flowsheet: flowsheetLabel, version: versionLabel });
      if (!plantId && !flowsheetVersionId) return;

      setMetaLoading(true);
      try {
        let flowsheetId = "";

        if (flowsheetVersionId) {
          try {
            const fv: FlowsheetVersionDetail = await fetchFlowsheetVersion(flowsheetVersionId);
            versionLabel = fv.version_label || versionLabel;
            flowsheetId = fv.flowsheet_id;
            flowsheetLabel = `Схема ID ${flowsheetId}`;
          } catch {
            // keep fallback labels
          }
        }

        if (flowsheetId) {
          try {
            const fs: FlowsheetDetail = await fetchFlowsheet(flowsheetId);
            flowsheetLabel = fs.name || flowsheetLabel;
            if (!plantId) {
              try {
                const plant: PlantDetail = await fetchPlant(fs.plant_id);
                plantLabel = plant.name || plantLabel;
              } catch {
                plantLabel = `Фабрика ID ${fs.plant_id}`;
              }
            }
          } catch {
            // ignore
          }
        }

        if (plantId) {
          try {
            const plant: PlantDetail = await fetchPlant(plantId);
            plantLabel = plant.name || plantLabel;
          } catch {
            // keep fallback
          }
        }
      } finally {
        setMeta({ plant: plantLabel, flowsheet: flowsheetLabel, version: versionLabel });
        setMetaLoading(false);
      }
    };

    loadMeta();
  }, [run]);

  function renderBaselineKpi(label: string, key: keyof BaselineKpi): JSX.Element | null {
    if (!baselineComparison) return null;

    const current = baselineComparison.current_kpi[key];
    const baseline = baselineComparison.baseline_kpi[key];
    const delta = baselineComparison.delta[key];

    if (current == null || baseline == null || delta == null) {
      return null;
    }

    const isLowerBetter = key === "product_p80_mm" || key === "specific_energy_kwhpt";

    let status: "better" | "worse" | "same" = "same";
    if (delta !== 0) {
      const isBetter = isLowerBetter ? delta < 0 : delta > 0;
      status = isBetter ? "better" : "worse";
    }

    return (
      <div key={key} className={`baseline-kpi baseline-kpi--${status}`}>
        <div className="baseline-kpi-label">{label}</div>
        <div className="baseline-kpi-values">
          <span className="baseline-kpi-current">Текущий: {current.toFixed(2)}</span>
          <span className="baseline-kpi-baseline">Базовый: {baseline.toFixed(2)}</span>
        </div>
        <div className="baseline-kpi-delta">
          Δ {delta >= 0 ? "+" : ""}
          {delta.toFixed(2)}
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="page">
        <div className="card">Загрузка...</div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="page">
        <div className="card error">{error ?? "Расчёт не найден"}</div>
      </div>
    );
  }

  const kpi = run.result.kpi;
  const sizeDist = run.result.size_distribution;
  const comparison: GrindMvpBaselineComparison | null = run.result.baseline_comparison ?? null;
  const scenarioName = run.scenario_name || run.input?.scenario_name || "Без названия";
  const plantLabel = metaLoading ? "Загрузка..." : meta.plant;
  const flowsheetLabel = metaLoading ? "Загрузка..." : meta.flowsheet;
  const versionLabel = metaLoading ? "Загрузка..." : meta.version;
  const createdAt = formatDateTime(run.created_at);
  const isSelfBaseline = !!(baselineComparison && baselineComparison.baseline_run_id === run.id);

  return (
    <div className="page">
      <div className="card wide-card">
        <header className="page-header">
          <div>
            <h1>Расчёт №{run.id} (grind_mvp_v1)</h1>
            <div className="meta-row">
              <span className="meta-item">Фабрика: {plantLabel}</span>
              <span className="meta-sep">•</span>
              <span className="meta-item">Схема: {flowsheetLabel}</span>
              <span className="meta-sep">•</span>
              <span className="meta-item">Версия: {versionLabel}</span>
              <span className="meta-sep">•</span>
              <span className="meta-item">Создан: {createdAt}</span>
              <span className="meta-sep">•</span>
              <span className="meta-item">Сценарий: “{scenarioName}”</span>
            </div>
          </div>
          <div className="header-actions">
            {isSelfBaseline && <span className="chip">Базовый расчёт для этой версии схемы</span>}
            {!isSelfBaseline && (
              <button className="btn secondary" onClick={handleMakeBaseline} disabled={isSettingBaseline}>
                Сделать базовым для этой версии схемы
              </button>
            )}
            <div className="actions">
              <BackToHomeButton />
              <button
                className="btn secondary"
                onClick={() => {
                  const base = getApiBaseUrl().replace(/\/$/, "");
                  window.location.href = `${base}/api/calc/grind-mvp-runs/${run.id}/report.xlsx`;
                }}
              >
                Скачать отчёт (Excel)
              </button>
              <button className="btn secondary" onClick={() => navigate("/")}>
                На главную
              </button>
              <button className="btn" onClick={() => navigate("/calc-run", { state: { fromRun: run } })}>
                Новый расчёт по шаблону
              </button>
            </div>
          </div>
        </header>

        <section className="section">
          <div className="section-heading">
            <h2>Ключевые показатели</h2>
          </div>
          <div className="kpi-grid">
            <MetricCard label="Производительность, т/ч" value={formatNumber(kpi.throughput_tph, 2)} />
            <MetricCard label="P80 продукта, мм" value={formatSize(kpi.product_p80_mm)} />
            <MetricCard
              label="Удельная энергия, кВт·ч/т"
              value={formatNumber(kpi.specific_energy_kwh_per_t, 2)}
            />
            <MetricCard
              label="Циркуляционная нагрузка, %"
              value={formatPercent(kpi.circulating_load_percent)}
            />
            <MetricCard
              label="Использование мощности, %"
              value={formatPercent(kpi.mill_utilization_percent)}
            />
          </div>
        </section>

        <section className="section">
          <h2>Эффект относительно базового расчёта</h2>

          {baselineLoading && <div>Загрузка сравнения…</div>}
          {baselineError && <div className="general-error">{baselineError}</div>}

          {!baselineLoading && !baselineError && !baselineComparison && (
            <>
              <p>Базовый расчёт для этой версии схемы пока не выбран.</p>
              <button className="btn secondary" onClick={handleMakeBaseline} disabled={isSettingBaseline}>
                Сделать этот расчёт базовым
              </button>
            </>
          )}

          {!baselineLoading && !baselineError && baselineComparison && isSelfBaseline && (
            <p>Это базовый расчёт для этой версии схемы. Эффект будет рассчитан для других вариантов.</p>
          )}

          {!baselineLoading && !baselineError && baselineComparison && !isSelfBaseline && (
            <>
              <p>
                Текущий расчёт №{baselineComparison.calc_run_id} сравнивается с базовым расчетом №
                {baselineComparison.baseline_run_id}.
              </p>

              <div className="baseline-grid">
                {renderBaselineKpi("Производительность, т/ч", "throughput_tph")}
                {renderBaselineKpi("P80 продукта, мм", "product_p80_mm")}
                {renderBaselineKpi("Удельная энергия, кВт·ч/т", "specific_energy_kwhpt")}
                {renderBaselineKpi("Циркуляционная нагрузка, %", "circulating_load_percent")}
                {renderBaselineKpi("Использование мощности, %", "utilization_percent")}
              </div>
            </>
          )}
        </section>

        <section className="section">
          <div className="section-heading">
            <h2>Комментарий к расчёту</h2>
          </div>
          <textarea
            value={commentDraft}
            onChange={(e) => setCommentDraft(e.target.value)}
            placeholder="Добавьте комментарий к расчёту"
            rows={4}
          />
          <div className="actions" style={{ marginTop: 8 }}>
            <button className="btn" onClick={handleSaveComment} disabled={isSavingComment}>
              {isSavingComment ? "Сохранение…" : "Сохранить комментарий"}
            </button>
          </div>
        </section>

        {comparison && (
          <section className="section">
            <div className="section-heading">
              <h2>Сравнение с базовым сценарием</h2>
              <p className="section-subtitle">Базовый расчёт: №{comparison.baseline_run_id}</p>
            </div>
            <div className="kpi-grid">
              <KpiDelta
                label="Производительность, т/ч"
                delta={comparison.throughput_delta_tph}
                deltaPercent={comparison.throughput_delta_percent}
              />
              <KpiDelta label="P80 продукта, мм" delta={comparison.product_p80_delta_mm} />
              <KpiDelta
                label="Удельная энергия, кВт·ч/т"
                delta={comparison.specific_energy_delta_kwhpt}
                deltaPercent={comparison.specific_energy_delta_percent}
              />
            </div>
          </section>
        )}

        <section className="section">
          <div className="section-heading">
            <h2>Гранулометрический состав питания</h2>
          </div>
          <table className="table striped">
            <thead>
              <tr>
                <th className="col-size">Размер, мм</th>
                <th className="col-percent">Сумм., %</th>
              </tr>
            </thead>
            <tbody>
              {sizeDist.feed.map((p, idx) => (
                <tr key={idx}>
                  <td className="align-left">{formatSize(p.size_mm)}</td>
                  <td className="align-right">{formatPercent(p.cum_percent)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="section">
          <div className="section-heading">
            <h2>Гранулометрический состав продукта</h2>
          </div>
          <table className="table striped">
            <thead>
              <tr>
                <th className="col-size">Размер, мм</th>
                <th className="col-percent">Сумм., %</th>
              </tr>
            </thead>
            <tbody>
              {sizeDist.product.map((p, idx) => (
                <tr key={idx}>
                  <td className="align-left">{formatSize(p.size_mm)}</td>
                  <td className="align-right">{formatPercent(p.cum_percent)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
};

export default CalcRunDetailPage;
