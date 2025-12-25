/**
 * ScenarioPSDComparison — Сравнение PSD кривых между несколькими сценариями
 *
 * Отображает несколько PSD кривых на одном графике для анализа влияния параметров
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Label,
} from "recharts";
import type { PSDData } from "./PSDChart";

export interface ScenarioPSDItem {
  name: string;
  psd: PSDData;
  color?: string;
  strokeDasharray?: string;
}

export interface ScenarioPSDComparisonProps {
  scenarios: ScenarioPSDItem[];
  title?: string;
  height?: number;
  /** Отображать ли линии P80/P50 для каждого сценария */
  showReferenceLines?: boolean;
}

/**
 * Форматирует размер для отображения
 */
function formatSize(size: number): string {
  if (size < 0.001) return `${(size * 1000000).toFixed(0)} µm`;
  if (size < 1) return `${(size * 1000).toFixed(0)} µm`;
  if (size < 10) return `${size.toFixed(2)} mm`;
  return `${size.toFixed(1)} mm`;
}

/**
 * Форматирует данные для Recharts
 */
function prepareComparisonData(scenarios: ScenarioPSDItem[]) {
  if (scenarios.length === 0) return [];

  // Получить все размеры из всех сценариев
  const allSizes = new Set<number>();
  scenarios.forEach((s) => {
    s.psd.sizes_mm.forEach((size) => allSizes.add(size));
  });

  const sortedSizes = Array.from(allSizes).sort((a, b) => a - b);

  // Создать точки с интерполяцией для каждого размера
  return sortedSizes.map((size) => {
    const point: any = {
      size_mm: size,
      sizeLabel: formatSize(size),
    };

    scenarios.forEach((scenario, idx) => {
      const psd = scenario.psd;
      const idx1 = psd.sizes_mm.findIndex((s) => s >= size);
      if (idx1 === -1) {
        point[`scenario_${idx}`] = psd.cum_passing[psd.cum_passing.length - 1];
      } else if (idx1 === 0) {
        point[`scenario_${idx}`] = psd.cum_passing[0];
      } else {
        // Линейная интерполяция
        const size0 = psd.sizes_mm[idx1 - 1];
        const size1 = psd.sizes_mm[idx1];
        const pass0 = psd.cum_passing[idx1 - 1];
        const pass1 = psd.cum_passing[idx1];
        const ratio = (size - size0) / (size1 - size0);
        point[`scenario_${idx}`] = pass0 + ratio * (pass1 - pass0);
      }
    });

    return point;
  });
}

const DEFAULT_COLORS = [
  "#2563eb", // blue
  "#dc2626", // red
  "#16a34a", // green
  "#f59e0b", // amber
  "#7c3aed", // violet
  "#06b6d4", // cyan
  "#ec4899", // pink
  "#8b5cf6", // purple
];

export function ScenarioPSDComparison({
  scenarios,
  title = "Сравнение PSD сценариев",
  height = 400,
  showReferenceLines = false,
}: ScenarioPSDComparisonProps) {
  if (scenarios.length === 0) {
    return (
      <div className="empty-state">
        Нет данных для сравнения. Выберите минимум один сценарий.
      </div>
    );
  }

  const chartData = prepareComparisonData(scenarios);

  return (
    <div className="psd-comparison-chart">
      {title && <h3 style={{ marginBottom: "1rem", fontSize: "1.1rem" }}>{title}</h3>}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={chartData}
          margin={{ top: 5, right: 30, left: 20, bottom: 60 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="size_mm"
            scale="log"
            domain={["auto", "auto"]}
            tickFormatter={formatSize}
            angle={-45}
            textAnchor="end"
            height={80}
          >
            <Label value="Размер частиц" offset={-40} position="insideBottom" />
          </XAxis>
          <YAxis
            domain={[0, 100]}
            label={{ value: "Кумулятивный % прохода", angle: -90, position: "insideLeft" }}
          />
          <Tooltip
            formatter={(value: number | undefined) => (value !== undefined ? `${value.toFixed(1)}%` : "—")}
            labelFormatter={(size: number) => `Размер: ${formatSize(size)}`}
          />
          <Legend verticalAlign="top" height={36} wrapperStyle={{ paddingBottom: "10px" }} />

          {/* Линии для каждого сценария */}
          {scenarios.map((scenario, idx) => {
            const color = scenario.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length];
            return (
              <Line
                key={`scenario_${idx}`}
                type="monotone"
                dataKey={`scenario_${idx}`}
                stroke={color}
                strokeWidth={2}
                dot={false}
                name={scenario.name}
                strokeDasharray={scenario.strokeDasharray}
              />
            );
          })}

          {/* Линии P80 для каждого сценария */}
          {showReferenceLines &&
            scenarios.map((scenario, idx) => {
              if (!scenario.psd.p80) return null;
              const color = scenario.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length];
              return (
                <ReferenceLine
                  key={`p80_${idx}`}
                  x={scenario.psd.p80}
                  stroke={color}
                  strokeDasharray="3 3"
                  opacity={0.5}
                  label={{
                    position: "top",
                    value: `${scenario.name} P80: ${formatSize(scenario.psd.p80)}`,
                    fontSize: 11,
                  }}
                />
              );
            })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
