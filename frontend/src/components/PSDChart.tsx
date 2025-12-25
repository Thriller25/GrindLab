/**
 * PSDChart — График гранулометрического состава (Particle Size Distribution)
 *
 * Отображает кривую кумулятивного прохода с маркерами P80, P50, P240
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

export interface PSDData {
  sizes_mm: number[];
  cum_passing: number[];
  p80?: number;
  p50?: number;
  p240_passing?: number; // % прохода через 240 mesh (0.063 мм)
}

export interface PSDChartProps {
  data: PSDData;
  title?: string;
  height?: number;
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
function prepareChartData(data: PSDData) {
  return data.sizes_mm.map((size, i) => ({
    size_mm: size,
    cum_passing: data.cum_passing[i],
    sizeLabel: formatSize(size),
  }));
}

export function PSDChart({ data, title = "Гранулометрический состав", height = 400 }: PSDChartProps) {
  const chartData = prepareChartData(data);

  return (
    <div className="psd-chart">
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
          <Legend verticalAlign="top" height={36} />

          {/* Основная кривая PSD */}
          <Line
            type="monotone"
            dataKey="cum_passing"
            stroke="#2563eb"
            strokeWidth={2}
            dot={{ r: 4 }}
            name="Cumulative Passing"
          />

          {/* Маркер P80 */}
          {data.p80 && (
            <ReferenceLine
              x={data.p80}
              stroke="#ef4444"
              strokeDasharray="5 5"
              label={{ value: `P80: ${formatSize(data.p80)}`, position: "top" }}
            />
          )}

          {/* Маркер P50 */}
          {data.p50 && (
            <ReferenceLine
              x={data.p50}
              stroke="#f59e0b"
              strokeDasharray="5 5"
              label={{ value: `P50: ${formatSize(data.p50)}`, position: "top" }}
            />
          )}

          {/* Маркер 240 mesh (0.063 мм) */}
          {data.p240_passing !== undefined && (
            <ReferenceLine
              x={0.063}
              stroke="#10b981"
              strokeDasharray="3 3"
              label={{ value: `240 mesh: ${data.p240_passing.toFixed(1)}%`, position: "bottom" }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
