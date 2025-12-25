/**
 * FlowsheetKPIComparison — Сравнение KPI для разных версий технологических схем
 * Отображает все расчёты на графиках с детализацией по сценариям
 */

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from "recharts";
import type { ProjectFlowsheetSummary, ProjectCalcRunListItem } from "../api/client";
import "./FlowsheetKPIComparison.css";

interface FlowsheetKPIComparisonProps {
  summaries: ProjectFlowsheetSummary[];
  recentRuns?: ProjectCalcRunListItem[];
  filterVersionId?: string;
}

type KPIMetric = {
  name: string;
  label: string;
  unit: string;
  formatValue: (value: number | null) => string;
  color: string;
};

const KPI_METRICS: KPIMetric[] = [
  {
    name: "throughput_tph",
    label: "Производительность",
    unit: "т/ч",
    formatValue: (v) => (v !== null ? `${v.toFixed(1)} т/ч` : "-"),
    color: "#3b82f6",
  },
  {
    name: "specific_energy_kwhpt",
    label: "Удельный расход энергии",
    unit: "кВтч/т",
    formatValue: (v) => (v !== null ? `${v.toFixed(2)} кВтч/т` : "-"),
    color: "#f59e0b",
  },
  {
    name: "product_p80_mm",
    label: "P80 продукта",
    unit: "мм",
    formatValue: (v) => (v !== null ? `${(v * 1000).toFixed(0)} мкм` : "-"),
    color: "#10b981",
  },
  {
    name: "circulating_load_pct",
    label: "Циркуляционная нагрузка",
    unit: "%",
    formatValue: (v) => (v !== null ? `${v.toFixed(0)}%` : "-"),
    color: "#8b5cf6",
  },
  {
    name: "power_use_pct",
    label: "Использование мощности",
    unit: "%",
    formatValue: (v) => (v !== null ? `${v.toFixed(0)}%` : "-"),
    color: "#ef4444",
  },
];

/**
 * Подготовка данных для графика: все расчёты группируются по версиям схем
 */
function prepareChartData(
  summaries: ProjectFlowsheetSummary[],
  runs?: ProjectCalcRunListItem[],
  filterVersionId?: string,
) {
  if (!runs || runs.length === 0) {
    // Fallback: используем базовый и лучший из summaries
    return summaries
      .filter((s) => s.has_runs && (s.baseline_run || s.best_project_run))
      .map((summary) => {
        const dataPoint: Record<string, any> = {
          name: summary.flowsheet_version_label || summary.flowsheet_name,
          fullName: `${summary.flowsheet_name} — ${summary.flowsheet_version_label}`,
        };

        KPI_METRICS.forEach((metric) => {
          const baselineKey = metric.name as keyof typeof summary.baseline_run;
          const bestKey = metric.name as keyof typeof summary.best_project_run;

          dataPoint[`${metric.name}_baseline`] =
            summary.baseline_run && summary.baseline_run[baselineKey] !== null
              ? Number(summary.baseline_run[baselineKey])
              : null;
          dataPoint[`${metric.name}_best`] =
            summary.best_project_run && summary.best_project_run[bestKey] !== null
              ? Number(summary.best_project_run[bestKey])
              : null;
        });

        return dataPoint;
      });
  }

  // Группируем расчёты по flowsheet_version_id
  const runsByVersion = new Map<string, ProjectCalcRunListItem[]>();
  runs.forEach((run) => {
    if (run.status === "success" && run.flowsheet_version_id) {
      const versionId = String(run.flowsheet_version_id);
      if (!runsByVersion.has(versionId)) {
        runsByVersion.set(versionId, []);
      }
      runsByVersion.get(versionId)!.push(run);
    }
  });

  // Создаём точки данных для каждого расчёта
  const allDataPoints: Array<Record<string, any>> = [];

  summaries
    .filter((s) => (filterVersionId ? String(s.flowsheet_version_id) === String(filterVersionId) : true))
    .forEach((summary) => {
    const versionRuns = runsByVersion.get(String(summary.flowsheet_version_id)) || [];

    versionRuns.forEach((run, index) => {
      const dataPoint: Record<string, any> = {
        name: `${summary.flowsheet_version_label} — ${run.scenario_name || `Расчёт ${index + 1}`}`,
        fullName: `${summary.flowsheet_name} — ${summary.flowsheet_version_label}`,
        runId: run.id,
        scenarioName: run.scenario_name,
        isBaseline: run.is_baseline || false,
      };

      const kpi = run.result_json?.kpi;
      if (kpi) {
        KPI_METRICS.forEach((metric) => {
          const kpiKey = metric.name === "throughput_tph" ? "throughput_tph" :
                          metric.name === "specific_energy_kwhpt" ? "specific_energy_kwh_per_t" :
                          metric.name === "product_p80_mm" ? "product_p80_mm" :
                          metric.name === "circulating_load_pct" ? "circulating_load_percent" :
                          metric.name === "power_use_pct" ? "mill_utilization_percent" : null;

          if (kpiKey) {
            const value = kpi[kpiKey as keyof typeof kpi];
            dataPoint[metric.name] = value !== null && value !== undefined ? Number(value) : null;
          }
        });
      }

      allDataPoints.push(dataPoint);
    });
  });

  return allDataPoints;
}

export function FlowsheetKPIComparison({ summaries, recentRuns, filterVersionId }: FlowsheetKPIComparisonProps) {
  const chartData = prepareChartData(summaries, recentRuns, filterVersionId);

  if (chartData.length === 0) {
    return (
      <div className="flowsheet-kpi-comparison empty">
        <p className="muted">Нет данных для отображения графиков. Запустите расчёты для версий схем.</p>
      </div>
    );
  }

  return (
    <div className="flowsheet-kpi-comparison">
      <div className="section-heading">
        <h2>Сравнение KPI по версиям схем</h2>
        <p className="section-subtitle">
          {recentRuns && recentRuns.length > 0
            ? `Все расчёты проекта (${chartData.length} успешных)`
            : "Сравнение базового и лучшего расчётов для каждой версии технологической схемы"}
        </p>
      </div>

      {KPI_METRICS.map((metric) => {
        // Проверяем, есть ли данные для этой метрики
        const hasData = chartData.some((d) => d[metric.name] !== null);

        if (!hasData) return null;

        return (
          <div key={metric.name} className="kpi-chart-container">
            <h3 className="kpi-chart-title">{metric.label}</h3>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 100 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="name"
                  angle={-45}
                  textAnchor="end"
                  height={120}
                  tick={{ fill: "#6b7280", fontSize: 11 }}
                  interval={0}
                />
                <YAxis tick={{ fill: "#6b7280", fontSize: 12 }} />
                <Tooltip
                  formatter={(value: any) => {
                    if (value === null || value === undefined) return "-";
                    return metric.formatValue(Number(value));
                  }}
                  labelFormatter={(label) => {
                    const item = chartData.find((d) => d.name === label);
                    return item?.scenarioName || label;
                  }}
                  contentStyle={{
                    backgroundColor: "#ffffff",
                    border: "1px solid #e5e7eb",
                    borderRadius: "6px",
                    padding: "8px",
                  }}
                />
                <Bar dataKey={metric.name} name={metric.label}>
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.isBaseline ? "#10b981" : metric.color}
                      opacity={entry.isBaseline ? 0.8 : 1}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        );
      })}

      <div className="kpi-summary-table">
        <h3>Сводная таблица KPI</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Версия схемы</th>
              <th>Производительность (т/ч)</th>
              <th>Энергия (кВтч/т)</th>
              <th>P80 (мкм)</th>
              <th>Циркуляция (%)</th>
              <th>Мощность (%)</th>
            </tr>
          </thead>
          <tbody>
            {summaries
              .filter((s) => s.has_runs && (s.baseline_run || s.best_project_run))
              .map((summary, idx) => {
                const best = summary.best_project_run;
                const baseline = summary.baseline_run;
                const diff = summary.diff_vs_baseline;

                return (
                  <tr key={idx}>
                    <td>
                      <strong>{summary.flowsheet_version_label || summary.flowsheet_name}</strong>
                      <div className="muted small">{summary.flowsheet_name}</div>
                    </td>
                    <td>
                      {baseline && (
                        <div className="muted small">Базовый: {baseline.throughput_tph?.toFixed(1) || "-"}</div>
                      )}
                      {best && <div>Лучший: {best.throughput_tph?.toFixed(1) || "-"}</div>}
                      {diff && diff.throughput_tph_delta !== null && (
                        <div
                          className={`small ${diff.throughput_tph_delta >= 0 ? "text-success" : "text-danger"}`}
                        >
                          {diff.throughput_tph_delta >= 0 ? "+" : ""}
                          {diff.throughput_tph_delta.toFixed(1)}
                        </div>
                      )}
                    </td>
                    <td>
                      {baseline && (
                        <div className="muted small">
                          Базовый: {baseline.specific_energy_kwhpt?.toFixed(2) || "-"}
                        </div>
                      )}
                      {best && <div>Лучший: {best.specific_energy_kwhpt?.toFixed(2) || "-"}</div>}
                      {diff && diff.specific_energy_kwhpt_delta !== null && (
                        <div
                          className={`small ${diff.specific_energy_kwhpt_delta <= 0 ? "text-success" : "text-danger"}`}
                        >
                          {diff.specific_energy_kwhpt_delta >= 0 ? "+" : ""}
                          {diff.specific_energy_kwhpt_delta.toFixed(2)}
                        </div>
                      )}
                    </td>
                    <td>
                      {baseline && (
                        <div className="muted small">
                          Базовый: {baseline.product_p80_mm ? (baseline.product_p80_mm * 1000).toFixed(0) : "-"}
                        </div>
                      )}
                      {best && (
                        <div>Лучший: {best.product_p80_mm ? (best.product_p80_mm * 1000).toFixed(0) : "-"}</div>
                      )}
                      {diff && diff.p80_mm_delta !== null && (
                        <div className="small muted">
                          {diff.p80_mm_delta >= 0 ? "+" : ""}
                          {(diff.p80_mm_delta * 1000).toFixed(0)} мкм
                        </div>
                      )}
                    </td>
                    <td>
                      {baseline && (
                        <div className="muted small">
                          Базовый: {baseline.circulating_load_pct?.toFixed(0) || "-"}
                        </div>
                      )}
                      {best && <div>Лучший: {best.circulating_load_pct?.toFixed(0) || "-"}</div>}
                      {diff && diff.circulating_load_pct_delta !== null && (
                        <div className="small muted">
                          {diff.circulating_load_pct_delta >= 0 ? "+" : ""}
                          {diff.circulating_load_pct_delta.toFixed(0)}%
                        </div>
                      )}
                    </td>
                    <td>
                      {baseline && (
                        <div className="muted small">Базовый: {baseline.power_use_pct?.toFixed(0) || "-"}</div>
                      )}
                      {best && <div>Лучший: {best.power_use_pct?.toFixed(0) || "-"}</div>}
                      {diff && diff.power_use_pct_delta !== null && (
                        <div className="small muted">
                          {diff.power_use_pct_delta >= 0 ? "+" : ""}
                          {diff.power_use_pct_delta.toFixed(0)}%
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
