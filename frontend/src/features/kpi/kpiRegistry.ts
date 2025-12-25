export type GoalType = "higher_is_better" | "lower_is_better" | "target_range" | "unknown";

export type KpiGoal = {
  type: GoalType;
  min?: number | null;
  max?: number | null;
};

export type KpiMeta = {
  key: string;
  label: string;
  unit?: string;
  precision?: number;
  aliases?: string[];
  defaultGoal: KpiGoal;
};

export type ResolvedKpiMeta = Omit<KpiMeta, "precision" | "aliases"> & {
  precision: number;
  aliases: string[];
  sourceKeys: string[];
};

const DEFAULT_PRECISION = 2;

export const DEFAULT_KPI_META: KpiMeta[] = [
  {
    key: "throughput_tph",
    label: "Производительность",
    unit: "т/ч",
    precision: 2,
    defaultGoal: { type: "higher_is_better" },
  },
  {
    key: "p80_mm",
    label: "P80 продукта",
    unit: "мм",
    precision: 2,
    aliases: ["product_p80_mm"],
    defaultGoal: { type: "lower_is_better" },
  },
  {
    key: "product_p50_mm",
    label: "P50 продукта",
    unit: "мм",
    precision: 2,
    defaultGoal: { type: "lower_is_better" },
  },
  {
    key: "product_p98_mm",
    label: "P98 продукта",
    unit: "мм",
    precision: 2,
    defaultGoal: { type: "lower_is_better" },
  },
  {
    key: "product_passing_240_mesh_pct",
    label: "% -240 mesh в продукте",
    unit: "%",
    precision: 1,
    defaultGoal: { type: "target_range" },
  },
  {
    key: "specific_energy_kwhpt",
    label: "Удельная энергозатратность",
    unit: "кВт·ч/т",
    precision: 2,
    aliases: ["specific_energy_kwh_per_t", "specific_energy_kwh_t"],
    defaultGoal: { type: "lower_is_better" },
  },
  {
    key: "recirc_load_pct",
    label: "Циркуляционная нагрузка",
    unit: "%",
    precision: 2,
    aliases: ["circulating_load_percent", "circulating_load_pct"],
    defaultGoal: { type: "target_range" },
  },
  {
    key: "mill_load_pct",
    label: "Загрузка мельницы",
    unit: "%",
    precision: 2,
    aliases: ["mill_utilization_percent"],
    defaultGoal: { type: "target_range" },
  },
];

const metaByKey = new Map<string, KpiMeta>();
const aliasToKey = new Map<string, string>();

DEFAULT_KPI_META.forEach((meta) => {
  metaByKey.set(meta.key, meta);
  (meta.aliases ?? []).forEach((alias) => aliasToKey.set(alias, meta.key));
});

export const resolveKpiMeta = (kpiKey: string): ResolvedKpiMeta => {
  const primaryKey = aliasToKey.get(kpiKey) ?? kpiKey;
  const baseMeta = metaByKey.get(primaryKey);

  if (!baseMeta) {
    return {
      key: primaryKey,
      label: primaryKey,
      unit: "",
      defaultGoal: { type: "unknown" },
      aliases: [],
      precision: DEFAULT_PRECISION,
      sourceKeys: [kpiKey],
    };
  }

  const aliases = baseMeta.aliases ?? [];
  const precision = baseMeta.precision ?? DEFAULT_PRECISION;
  const sourceKeys = Array.from(new Set([baseMeta.key, ...aliases, kpiKey, primaryKey]));

  return {
    ...baseMeta,
    key: baseMeta.key,
    aliases,
    precision,
    sourceKeys,
  };
};
