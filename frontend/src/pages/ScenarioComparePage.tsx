import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  CalcRunListItem,
  CalcScenario,
  fetchCalcRunsByFlowsheetVersion,
  fetchGrindMvpRun,
  fetchProjectDashboard,
  GrindMvpRunDetail,
  isAuthExpiredError,
  updateScenario,
  ProjectDashboardResponse,
} from "../api/client";
import BackToHomeButton from "../components/BackToHomeButton";
import {
  DEFAULT_KPI_META,
  GoalType,
  KpiGoal,
  ResolvedKpiMeta,
  resolveKpiMeta,
} from "../features/kpi/kpiRegistry";
import { hasAuth } from "../auth/authProvider";

type MetricVerdict = "better" | "worse" | "same" | "unknown";
type VerdictFilter = "all" | "better" | "worse";

type MetricConfig = ResolvedKpiMeta;

type MetricVerdictResult = {
  verdict: MetricVerdict;
  reason?: string | null;
  baselineRangeScore?: number | null;
  scenarioRangeScore?: number | null;
};

const DELTA_EPSILON = 1e-6;
const BASELINE_EPSILON = 1e-9;

const KPI_GOAL_STORAGE_PREFIX = "grindlab.kpiGoals.v1.project.";
const storageKeyForGoals = (projectId: string, flowsheetVersionId: string | number) =>
  `${KPI_GOAL_STORAGE_PREFIX}${projectId}.flowsheet.${flowsheetVersionId}`;

const UNKNOWN_GOAL: KpiGoal = { type: "unknown" };

const GOAL_TYPE_LABELS: Record<GoalType, string> = {
  higher_is_better: "Больше — лучше",
  lower_is_better: "Меньше — лучше",
  target_range: "Целевой диапазон",
  unknown: "Не задано",
};

const VERDICT_LABELS: Record<MetricVerdict, string> = {
  better: "Лучше",
  worse: "Хуже",
  same: "Без изменений",
  unknown: "Неизвестно",
};

const isGoalType = (value?: string): value is GoalType =>
  value === "higher_is_better" || value === "lower_is_better" || value === "target_range" || value === "unknown";

const toNumberOrNull = (value: unknown) => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
};

const normalizeGoal = (goal?: KpiGoal): KpiGoal => {
  if (!goal || !isGoalType(goal.type)) return { ...UNKNOWN_GOAL };
  if (goal.type !== "target_range") return { type: goal.type };
  return { type: goal.type, min: toNumberOrNull(goal.min), max: toNumberOrNull(goal.max) };
};

const goalEquals = (a: KpiGoal | undefined, b: KpiGoal) =>
  a?.type === b.type && a?.min === b.min && a?.max === b.max;

const defaultGoalForKey = (key: string) => normalizeGoal(resolveKpiMeta(key).defaultGoal ?? UNKNOWN_GOAL);

const ensureGoalsForMetrics = (goals: Record<string, KpiGoal>, metrics: MetricConfig[]) => {
  let changed = false;
  const next = { ...goals };
  metrics.forEach((metric) => {
    const desired = normalizeGoal(goals[metric.key] ?? metric.defaultGoal ?? UNKNOWN_GOAL);
    if (!goalEquals(goals[metric.key], desired)) {
      next[metric.key] = desired;
      changed = true;
    }
  });
  return changed ? next : goals;
};

const loadStoredGoals = (storageKey: string): Record<string, KpiGoal> => {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object") return {};
    return Object.entries(parsed).reduce<Record<string, KpiGoal>>((acc, [key, value]) => {
      acc[key] = normalizeGoal(value as KpiGoal);
      return acc;
    }, {});
  } catch {
    return {};
  }
};

const persistGoals = (storageKey: string, goals: Record<string, KpiGoal>) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(goals));
  } catch {
    // ignore storage errors
  }
};

const extractRange = (goal: KpiGoal) => {
  if (goal.type !== "target_range") return null;
  const min = toNumberOrNull(goal.min);
  const max = toNumberOrNull(goal.max);
  if (min == null || max == null) return null;
  if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
  if (min >= max) return null;
  return { min, max };
};

const describeGoal = (goal: KpiGoal) => {
  if (goal.type === "target_range") {
    const range = extractRange(goal);
    if (range) return `${GOAL_TYPE_LABELS[goal.type]} (${range.min} — ${range.max})`;
    return `${GOAL_TYPE_LABELS[goal.type]} (диапазон не задан)`;
  }
  return GOAL_TYPE_LABELS[goal.type] ?? GOAL_TYPE_LABELS.unknown;
};

const validateRangeGoal = (goal: KpiGoal): string | null => {
  if (goal.type !== "target_range") return null;
  const min = toNumberOrNull(goal.min);
  const max = toNumberOrNull(goal.max);
  if (min == null || max == null) return "Укажите минимум и максимум";
  if (!Number.isFinite(min) || !Number.isFinite(max)) return "Значения должны быть числами";
  if (min >= max) return "Минимум должен быть меньше максимума";
  return null;
};

type MissingState = {
  message: string;
  allowScenarioRun?: boolean;
  allowBaselineRun?: boolean;
  type?: "flowsheet-mismatch" | "missing-runs" | "missing-baseline" | "missing-scenario";
  ctaPath?: string;
  ctaLabel?: string;
  hideSelectors?: boolean;
};
type SortMode = "default" | "absDelta";

const MISSING_VALUE_TEXT = "—";

const metricLabelWithUnit = (metric: MetricConfig) =>
  metric.unit ? `${metric.label}, ${metric.unit}` : metric.label;

const formatNumber = (value: number | null | undefined, precision: number) =>
  value == null ? MISSING_VALUE_TEXT : value.toFixed(precision);

const formatDelta = (value: number | null, precision: number) => {
  if (value == null) return MISSING_VALUE_TEXT;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(precision)}`;
};

const formatPercentDelta = (value: number | null, precision: number) =>
  value == null ? MISSING_VALUE_TEXT : `${formatDelta(value, precision)}%`;

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
    : MISSING_VALUE_TEXT;

const kpiValue = (run: GrindMvpRunDetail | null, keys: string[]): number | null => {
  const kpi = (run?.result?.kpi ?? {}) as Record<string, unknown>;
  for (const key of keys) {
    const value = kpi[key];
    if (typeof value === "number") return value;
  }
  return null;
};

const deltaClass = (delta: number | null, goal: KpiGoal, verdict: MetricVerdict) => {
  if (delta == null || Math.abs(delta) < DELTA_EPSILON) return "";
  if (goal.type === "higher_is_better") return delta > 0 ? "delta-positive" : "delta-negative";
  if (goal.type === "lower_is_better") return delta > 0 ? "delta-negative" : "delta-positive";
  if (verdict === "better") return "delta-positive";
  if (verdict === "worse") return "delta-negative";
  return "";
};

const rangeDistance = (value: number, range: { min: number; max: number }) => {
  if (value < range.min) return range.min - value;
  if (value > range.max) return value - range.max;
  return 0;
};

const calcVerdict = (
  baseValue: number | null,
  scenarioValue: number | null,
  goal: KpiGoal,
): MetricVerdictResult => {
  if (goal.type === "unknown") return { verdict: "unknown", reason: "Направление не задано" };
  if (baseValue == null && scenarioValue == null) return { verdict: "unknown", reason: "Нет данных KPI для сравнения" };
  if (baseValue == null) return { verdict: "unknown", reason: "Нет значения KPI для базового сценария" };
  if (scenarioValue == null) return { verdict: "unknown", reason: "Нет значения KPI для сравниваемого сценария" };
  if (baseValue === 0) return { verdict: "unknown", reason: "Базовое значение равно 0" };
  if (goal.type === "target_range") {
    const range = extractRange(goal);
    if (!range) return { verdict: "unknown", reason: "Диапазон не задан" };
    const baselineScore = rangeDistance(baseValue, range);
    const scenarioScore = rangeDistance(scenarioValue, range);
    if (scenarioScore < baselineScore - DELTA_EPSILON) {
      return { verdict: "better", baselineRangeScore: baselineScore, scenarioRangeScore: scenarioScore };
    }
    if (scenarioScore > baselineScore + DELTA_EPSILON) {
      return { verdict: "worse", baselineRangeScore: baselineScore, scenarioRangeScore: scenarioScore };
    }
    return { verdict: "same", baselineRangeScore: baselineScore, scenarioRangeScore: scenarioScore };
  }

  const delta = scenarioValue - baseValue;
  if (Math.abs(delta) < DELTA_EPSILON) return { verdict: "same" };
  const isBetter = goal.type === "higher_is_better" ? delta > 0 : delta < 0;
  return { verdict: isBetter ? "better" : "worse" };
};

const impactValue = (deltaPct: number | null, delta: number | null, verdict: MetricVerdict) => {
  if (verdict === "same") return 0;
  if (deltaPct != null) return Math.abs(deltaPct);
  if (delta != null) return Math.abs(delta);
  return -Infinity;
};

type MetricRow = {
  metric: MetricConfig;
  goal: KpiGoal;
  baseValue: number | null;
  scenarioValue: number | null;
  delta: number | null;
  deltaPct: number | null;
  verdict: MetricVerdict;
  verdictReason?: string | null;
  rangeScores?: { baseline: number | null; scenario: number | null };
  index: number;
};

const impactOfRow = (row: MetricRow) => {
  if (row.verdict === "same") return 0;
  if (row.rangeScores) {
    const baseScore = row.rangeScores.baseline ?? 0;
    const scenarioScore = row.rangeScores.scenario ?? 0;
    return Math.abs(baseScore - scenarioScore);
  }
  return impactValue(row.deltaPct, row.delta, row.verdict);
};

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
  const [kpiGoals, setKpiGoals] = useState<Record<string, KpiGoal>>({});
  const [goalsReady, setGoalsReady] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [recommendModal, setRecommendModal] = useState<{
    is_recommended: boolean;
    recommendation_note: string;
  } | null>(null);
  const [recommendationSaving, setRecommendationSaving] = useState(false);
  const [recommendationMessage, setRecommendationMessage] = useState<string | null>(null);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [authExpired, setAuthExpired] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(() => hasAuth());

  const handleAuthExpired = () => {
    setAuthExpired(true);
    setIsAuthenticated(false);
    setRecommendModal(null);
    setRecommendationError(null);
    setRecommendationMessage(null);
  };

  useEffect(() => {
    const syncAuthState = () => {
      const hasToken = hasAuth();
      setIsAuthenticated(hasToken);
      if (hasToken) setAuthExpired(false);
    };
    syncAuthState();
    window.addEventListener("storage", syncAuthState);
    window.addEventListener("focus", syncAuthState);
    return () => {
      window.removeEventListener("storage", syncAuthState);
      window.removeEventListener("focus", syncAuthState);
    };
  }, []);

  const recommendationActionsDisabled = !isAuthenticated || authExpired;
  const flowsheetVersionNameById = useMemo(() => {
    if (!dashboard?.flowsheet_versions) return {};
    return dashboard.flowsheet_versions.reduce<Record<string, string>>((acc, version) => {
      acc[String(version.id)] = version.version_label || String(version.id);
      return acc;
    }, {});
  }, [dashboard?.flowsheet_versions]);

  const flowsheetVersionId = useMemo(() => {
    if (selectedScenario?.flowsheet_version_id) return String(selectedScenario.flowsheet_version_id);
    if (baselineScenario?.flowsheet_version_id) return String(baselineScenario.flowsheet_version_id);
    return null;
  }, [baselineScenario?.flowsheet_version_id, selectedScenario?.flowsheet_version_id]);

  const goalsStorageKey = useMemo(() => {
    if (!projectId || !flowsheetVersionId) return null;
    return storageKeyForGoals(projectId, flowsheetVersionId);
  }, [flowsheetVersionId, projectId]);

  useEffect(() => {
    if (!projectId || !scenarioId) {
      setError("Не хватает параметров маршрута для сравнения сценариев");
      return;
    }

    setLoading(true);
    setError(null);
    setMissingState(null);
    setRunsError(null);
    setRecommendationMessage(null);
    setRecommendationError(null);
    setRecommendModal(null);
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
        message:
          "Базовый сценарий относится к другой версии схемы. Сравнение возможно только для сценариев одной версии.",
        allowBaselineRun: false,
        allowScenarioRun: false,
        type: "flowsheet-mismatch",
        ctaPath: projectId ? `/projects/${projectId}` : "/",
        ctaLabel: "Перейти в проект и сменить базовый",
        hideSelectors: true,
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
  }, [baselineScenario, projectId, selectedScenario]);

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

  const kpiKeysInRuns = useMemo(() => {
    const keys = new Set<string>();
    const collectKeys = (run: GrindMvpRunDetail | null) => {
      const kpi = (run?.result?.kpi ?? {}) as Record<string, unknown>;
      Object.keys(kpi).forEach((key) => keys.add(key));
    };
    collectKeys(scenarioRun);
    collectKeys(baselineRun);
    return Array.from(keys);
  }, [baselineRun, scenarioRun]);

  const allMetrics = useMemo<MetricConfig[]>(() => {
    const map = new Map<string, MetricConfig>();
    DEFAULT_KPI_META.forEach((meta) => {
      const resolved = resolveKpiMeta(meta.key);
      map.set(resolved.key, resolved);
    });

    kpiKeysInRuns.forEach((key) => {
      const resolved = resolveKpiMeta(key);
      const existing = map.get(resolved.key);
      if (existing) {
        const mergedKeys = Array.from(new Set([...existing.sourceKeys, ...resolved.sourceKeys]));
        if (mergedKeys.length !== existing.sourceKeys.length) {
          map.set(resolved.key, { ...existing, sourceKeys: mergedKeys });
        }
        return;
      }
      map.set(resolved.key, resolved);
    });
    return Array.from(map.values());
  }, [kpiKeysInRuns]);

  useEffect(() => {
    if (!projectId || !goalsStorageKey) {
      setKpiGoals({});
      setGoalsReady(false);
      return;
    }
    setGoalsReady(false);
    const stored = loadStoredGoals(goalsStorageKey);
    setKpiGoals(stored);
    setSaveMessage(null);
    setGoalsReady(true);
  }, [goalsStorageKey, projectId]);

  useEffect(() => {
    if (!goalsReady) return;
    setKpiGoals((prev) => ensureGoalsForMetrics(prev, allMetrics));
  }, [allMetrics, goalsReady]);

  const goalValidationErrors = useMemo(
    () =>
      allMetrics.reduce<Record<string, string | null>>((acc, metric) => {
        const goal = normalizeGoal(kpiGoals[metric.key] ?? metric.defaultGoal ?? UNKNOWN_GOAL);
        acc[metric.key] = validateRangeGoal(goal);
        return acc;
      }, {}),
    [allMetrics, kpiGoals],
  );

  const hasValidationErrors = useMemo(
    () => Object.values(goalValidationErrors).some((msg) => Boolean(msg)),
    [goalValidationErrors],
  );

  useEffect(() => {
    if (!goalsStorageKey || !goalsReady || hasValidationErrors) return;
    persistGoals(goalsStorageKey, kpiGoals);
  }, [goalsReady, goalsStorageKey, hasValidationErrors, kpiGoals]);

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
  const hideRunSelectors = Boolean(missingState?.hideSelectors);

  const comparisonMetrics = useMemo<MetricRow[]>(() => {
    if (!scenarioRun || !baselineRun) return [];

    return allMetrics.map((metric, index) => {
      const goal = normalizeGoal(kpiGoals[metric.key] ?? metric.defaultGoal ?? UNKNOWN_GOAL);
      const baseValue = kpiValue(baselineRun, metric.sourceKeys);
      const scenarioValue = kpiValue(scenarioRun, metric.sourceKeys);
      const delta = baseValue != null && scenarioValue != null ? scenarioValue - baseValue : null;
      const deltaPct =
        baseValue != null && scenarioValue != null && Math.abs(baseValue) > BASELINE_EPSILON
          ? ((scenarioValue - baseValue) / baseValue) * 100
          : null;
      const verdictResult = calcVerdict(baseValue, scenarioValue, goal);
      const rangeScores =
        verdictResult.baselineRangeScore == null && verdictResult.scenarioRangeScore == null
          ? undefined
          : {
              baseline: verdictResult.baselineRangeScore ?? null,
              scenario: verdictResult.scenarioRangeScore ?? null,
            };

      return {
        metric,
        goal,
        baseValue,
        scenarioValue,
        delta,
        deltaPct,
        verdict: verdictResult.verdict,
        verdictReason: verdictResult.reason,
        rangeScores,
        index,
      };
    });
  }, [allMetrics, baselineRun, kpiGoals, scenarioRun]);

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
        const hasDelta = item.delta != null && Math.abs(item.delta) >= DELTA_EPSILON;
        if (showOnlyDifferent && !hasDelta) return false;
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

  const applyScenarioUpdate = (updated: CalcScenario) => {
    setSelectedScenario((prev) => (prev && prev.id === updated.id ? { ...prev, ...updated } : prev));
    setBaselineScenario((prev) => (prev && prev.id === updated.id ? { ...prev, ...updated } : prev));
    setDashboard((prev) =>
      prev
        ? { ...prev, scenarios: prev.scenarios.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)) }
        : prev,
    );
  };

  const openRecommendationModal = (nextValue?: boolean) => {
    if (!selectedScenario || recommendationActionsDisabled) return;
    setRecommendationError(null);
    setRecommendationMessage(null);
    setRecommendModal({
      is_recommended: nextValue ?? selectedScenario.is_recommended,
      recommendation_note: selectedScenario.recommendation_note || "",
    });
  };

  const handleSaveRecommendation = async () => {
    if (!selectedScenario || !recommendModal || recommendationActionsDisabled) return;
    setRecommendationSaving(true);
    setRecommendationError(null);
    setRecommendationMessage(null);
    const trimmedNote = recommendModal.recommendation_note.trim();
    const noteToSave = recommendModal.is_recommended && trimmedNote ? trimmedNote : null;
    try {
      const updated = await updateScenario(selectedScenario.id, {
        is_recommended: recommendModal.is_recommended,
        recommendation_note: noteToSave,
      });
      applyScenarioUpdate(updated);
      setRecommendationMessage(
        recommendModal.is_recommended ? "Сценарий отмечен как рекомендованный." : "Рекомендация снята.",
      );
      setRecommendModal(null);
    } catch (err) {
      if (isAuthExpiredError(err)) {
        handleAuthExpired();
      } else {
        const status = (err as any)?.response?.status;
        if (status === 401) {
          handleAuthExpired();
        } else if (status === 403) {
          setRecommendationError("Недостаточно прав для изменения рекомендации.");
        } else {
          const detail = (err as any)?.response?.data?.detail;
          setRecommendationError(
            typeof detail === "string"
              ? detail
              : "Не удалось обновить рекомендацию. Авторизуйтесь и попробуйте снова.",
          );
        }
      }
    } finally {
      setRecommendationSaving(false);
    }
  };

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

  const handleOpenRunDetails = (id?: string | null) => {
    if (!id) return;
    navigate(`/calc-runs/${id}`);
  };

  const setGoalForMetric = (metricKey: string, updater: (goal: KpiGoal) => KpiGoal) => {
    setKpiGoals((prev) => {
      const current = normalizeGoal(prev[metricKey] ?? defaultGoalForKey(metricKey));
      const next = normalizeGoal(updater(current));
      if (goalEquals(current, next)) return prev;
      return { ...prev, [metricKey]: next };
    });
    setSaveMessage(null);
  };

  const handleGoalTypeChange = (metricKey: string, type: GoalType) => {
    setGoalForMetric(metricKey, (current) => {
      if (type === "target_range") {
        return { type, min: current.min ?? null, max: current.max ?? null };
      }
      return { type };
    });
  };

  const handleRangeChange = (metricKey: string, bound: "min" | "max", value: string) => {
    setGoalForMetric(metricKey, (current) => {
      const parsed = value.trim() === "" ? null : Number(value);
      const numericValue = parsed != null && Number.isFinite(parsed) ? parsed : null;
      const next: KpiGoal = {
        type: "target_range",
        min: current.min ?? null,
        max: current.max ?? null,
      };
      if (bound === "min") {
        next.min = numericValue;
      } else {
        next.max = numericValue;
      }
      return next;
    });
  };

  const handleSaveGoals = () => {
    if (!goalsStorageKey) return;
    if (hasValidationErrors) {
      setSaveMessage("Исправьте ошибки в целевом диапазоне");
      return;
    }
    const ensured = ensureGoalsForMetrics(kpiGoals, allMetrics);
    setKpiGoals(ensured);
    persistGoals(goalsStorageKey, ensured);
    setSaveMessage("Настройки сохранены");
  };

  const handleResetGoals = () => {
    const defaults = allMetrics.reduce<Record<string, KpiGoal>>((acc, metric) => {
      acc[metric.key] = defaultGoalForKey(metric.key);
      return acc;
    }, {});
    setKpiGoals(defaults);
    setSaveMessage("Настройки сброшены к умолчаниям");
  };

  const renderMissing = (state: MissingState) => {
    const allowScenarioRun = state.allowScenarioRun ?? true;
    const allowBaselineRun = state.allowBaselineRun ?? false;
    const hasCta = Boolean(state.ctaPath && state.ctaLabel);
    const hasActions =
      (allowScenarioRun && selectedScenario) || (allowBaselineRun && baselineScenario) || hasCta;
    return (
      <div className="empty-state" style={{ marginTop: 12 }}>
        <div>{state.message}</div>
        {hasActions && (
          <div className="actions" style={{ marginTop: 10 }}>
            {hasCta && state.ctaPath && state.ctaLabel && (
              <button className="btn" type="button" onClick={() => navigate(state.ctaPath!)}>
                {state.ctaLabel}
              </button>
            )}
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
    const precision = item.metric.precision ?? 2;
    const pctText = item.deltaPct == null ? "" : ` (${formatPercentDelta(item.deltaPct, precision)})`;
    const rangeText =
      item.rangeScores && item.rangeScores.baseline != null && item.rangeScores.scenario != null
        ? ` (расстояние: ${formatNumber(item.rangeScores.baseline, precision)} → ${formatNumber(item.rangeScores.scenario, precision)})`
        : "";
    return `${metricLabelWithUnit(item.metric)}: ${formatDelta(item.delta, precision)}${pctText}${rangeText}`;
  };

  const renderTopList = (items: MetricRow[]) => {
    if (!items.length) return <div className="muted">{MISSING_VALUE_TEXT}</div>;
    return (
      <ul>
        {items.map((item) => (
          <li key={item.metric.key}>{formatImpactLine(item)}</li>
        ))}
      </ul>
    );
  };

  const goalOptions: GoalType[] = ["higher_is_better", "lower_is_better", "target_range", "unknown"];

  const renderComparisonTable = (rows: MetricRow[]) => {
    if (!rows.length) {
      return <div className="muted">Нет метрик по выбранным фильтрам.</div>;
    }

    return (
      <table className="table striped">
        <thead>
          <tr>
            <th>Метрика, ед.</th>
            <th>Базовый</th>
            <th>Сценарий</th>
            <th>Δ</th>
            <th>%Δ</th>
            <th>Оценка</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ metric, goal, baseValue, scenarioValue, delta, deltaPct, verdict, verdictReason }) => {
            const className = deltaClass(delta, goal, verdict);
            const precision = metric.precision ?? 2;
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
            const verdictTitleParts = [describeGoal(goal)];
            if (verdictReason) verdictTitleParts.push(verdictReason);
            const verdictTitle = verdictTitleParts.join(". ");

            return (
              <tr key={metric.key} className={rowClass || undefined}>
                <td>{metricLabelWithUnit(metric)}</td>
                <td className="align-right">{formatNumber(baseValue, precision)}</td>
                <td className="align-right">{formatNumber(scenarioValue, precision)}</td>
                <td className="align-right">
                  <span className={`delta ${className}`}>{formatDelta(delta, precision)}</span>
                </td>
                <td className="align-right">
                  <span className={`delta ${className}`}>
                    {formatPercentDelta(deltaPct, precision)}
                  </span>
                </td>
                <td className="align-left">
                  <span className={verdictClass} title={verdictTitle}>
                    {VERDICT_LABELS[verdict]}
                  </span>
                  {verdict === "unknown" && verdictReason && (
                    <div className="muted" style={{ fontSize: 12 }}>{verdictReason}</div>
                  )}
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
            <div className="meta-row">
              <span className="meta-item">
                Рекомендация: {selectedScenario?.is_recommended ? "Да" : "—"}
              </span>
              {baselineScenario && (
                <>
                  <span className="meta-sep">•</span>
                  <span className="meta-item">
                    Базовый: {baselineScenario.is_recommended ? "Да" : "—"}
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
            {authExpired && <div className="alert error">Сессия истекла. Войдите снова.</div>}
            {recommendationError && <div className="alert error">{recommendationError}</div>}
            {recommendationMessage && <div className="alert success">{recommendationMessage}</div>}

            <section className="section">
              <div className="section-heading">
                <h2>Последние успешные расчёты</h2>
                <p className="section-subtitle">
                  Используем последние успешные запуски сценариев для расчёта дельт по KPI.
                </p>
              </div>
              <div className="actions" style={{ justifyContent: "flex-start", gap: 10, marginBottom: 8 }}>
                {selectedScenario && (
                  <button
                    className="btn secondary"
                    type="button"
                    onClick={() => openRecommendationModal(selectedScenario.is_recommended)}
                    disabled={recommendationSaving || recommendationActionsDisabled}
                  >
                    Комментарий
                  </button>
                )}
                {selectedScenario && (
                  <button
                    className="btn"
                    type="button"
                    onClick={() => openRecommendationModal(!selectedScenario.is_recommended)}
                    disabled={recommendationSaving || recommendationActionsDisabled}
                  >
                    {selectedScenario.is_recommended ? "Снять рекомендацию" : "Рекомендовать сценарий"}
                  </button>
                )}
              </div>

              {!hideRunSelectors && (
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
              )}

              <div className="grid">
                <div className="stat">
                  <div className="stat-label">Сценарий</div>
                  <div className="stat-value">{selectedScenario.name}</div>
                  <div className="muted">Версия схемы: {selectedVersionLabel}</div>
                  <div className="muted">
                    Рекомендация: {selectedScenario.is_recommended ? "Да" : "—"}
                    {selectedScenario.recommendation_note ? ` • ${selectedScenario.recommendation_note}` : ""}
                  </div>
                  <div className="muted">
                    Запуск для сравнения:{" "}
                    {scenarioRunOption ? (
                      <span title={`Расчёт №${scenarioRunOption.id}`}>{formatRunLabel(scenarioRunOption)}</span>
                    ) : (
                      "—"
                    )}
                  </div>
                  {scenarioRunOption && (
                    <div className="actions" style={{ marginTop: 8 }}>
                      <button
                        className="btn secondary"
                        type="button"
                        onClick={() => handleOpenRunDetails(scenarioRunOption.id)}
                      >
                        Открыть запуск
                      </button>
                    </div>
                  )}
                </div>
                <div className="stat">
                  <div className="stat-label">Базовый сценарий</div>
                  <div className="stat-value">{baselineScenario?.name ?? "—"}</div>
                  <div className="muted">Версия схемы: {baselineVersionLabel}</div>
                  <div className="muted">
                    Рекомендация: {baselineScenario?.is_recommended ? "Да" : "—"}
                    {baselineScenario?.recommendation_note ? ` • ${baselineScenario.recommendation_note}` : ""}
                  </div>
                  <div className="muted">
                    Запуск для сравнения:{" "}
                    {baselineRunOption ? (
                      <span title={`Расчёт №${baselineRunOption.id}`}>{formatRunLabel(baselineRunOption)}</span>
                    ) : (
                      "—"
                    )}
                  </div>
                  {baselineRunOption && (
                    <div className="actions" style={{ marginTop: 8 }}>
                      <button
                        className="btn secondary"
                        type="button"
                        onClick={() => handleOpenRunDetails(baselineRunOption.id)}
                      >
                        Открыть запуск
                      </button>
                    </div>
                  )}
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
                  <div className="card" style={{ marginBottom: 12 }}>
                    <div className="section-heading" style={{ marginBottom: 8 }}>
                      <h3>Настройки целей KPI</h3>
                      <p className="section-subtitle">
                        Настройки сохраняются для проекта в браузере. Для «Целевой диапазон» оценка строится по расстоянию до диапазона.
                      </p>
                    </div>
                    <div className="filters-bar" style={{ alignItems: "center", gap: 8 }}>
                      <div className="actions" style={{ justifyContent: "flex-start" }}>
                        <button
                          className="btn"
                          type="button"
                          onClick={handleSaveGoals}
                          disabled={!goalsReady || hasValidationErrors || !goalsStorageKey}
                        >
                          Сохранить
                        </button>
                        <button className="btn secondary" type="button" onClick={handleResetGoals}>
                          Сбросить к умолчаниям
                        </button>
                      </div>
                      {hasValidationErrors && (
                        <div style={{ color: "#b91c1c", fontSize: 13 }}>Исправьте ошибки в целевых диапазонах</div>
                      )}
                      <div className="muted">Изменения применяются сразу. Некорректные диапазоны не сохранятся.</div>
                      {saveMessage && <div className="muted">{saveMessage}</div>}
                    </div>
                    <div className="kpi-grid">
                      {allMetrics.map((metric) => {
                        const goal = normalizeGoal(kpiGoals[metric.key] ?? metric.defaultGoal ?? UNKNOWN_GOAL);
                        const goalError = goalValidationErrors[metric.key];
                        return (
                          <div
                            key={metric.key}
                            className="metric-card"
                            style={{ minHeight: "auto", gap: 8, justifyContent: "flex-start" }}
                          >
                            <div className="stat-label">{metricLabelWithUnit(metric)}</div>
                            <select
                              className="input"
                              value={goal.type}
                              onChange={(e) => handleGoalTypeChange(metric.key, e.target.value as GoalType)}
                            >
                              {goalOptions.map((option) => (
                                <option key={option} value={option}>
                                  {GOAL_TYPE_LABELS[option]}
                                </option>
                              ))}
                            </select>
                            {goal.type === "target_range" && (
                              <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 8 }}>
                                <label className="filter-control">
                                  Мин
                                  <input
                                    className="input"
                                    type="number"
                                    step="any"
                                    value={goal.min ?? ""}
                                    onChange={(e) => handleRangeChange(metric.key, "min", e.target.value)}
                                  />
                                </label>
                                <label className="filter-control">
                                  Макс
                                  <input
                                    className="input"
                                    type="number"
                                    step="any"
                                    value={goal.max ?? ""}
                                    onChange={(e) => handleRangeChange(metric.key, "max", e.target.value)}
                                  />
                                </label>
                              </div>
                            )}
                            {goalError ? (
                              <div style={{ color: "#b91c1c", fontSize: 13 }}>{goalError}</div>
                            ) : (
                              <div className="muted">{describeGoal(goal)}</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
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
      {recommendModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Рекомендация для сценария</h3>
            <p className="section-subtitle">{selectedScenario?.name}</p>
            <label className="filter-checkbox">
              <input
                type="checkbox"
                checked={recommendModal.is_recommended}
                onChange={(e) =>
                  setRecommendModal({
                    ...recommendModal,
                    is_recommended: e.target.checked,
                  })
                }
              />
              <span>Отметить как рекомендованный</span>
            </label>
            <label>
              Комментарий (опционально)
              <textarea
                value={recommendModal.recommendation_note}
                onChange={(e) =>
                  setRecommendModal({
                    ...recommendModal,
                    recommendation_note: e.target.value,
                  })
                }
                placeholder="Короткое пояснение для команды"
              />
            </label>
            <div className="actions modal-actions">
              <button className="btn secondary" type="button" onClick={() => setRecommendModal(null)} disabled={recommendationSaving}>
                Отмена
              </button>
              <button className="btn" type="button" onClick={handleSaveRecommendation} disabled={recommendationSaving}>
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ScenarioComparePage;
