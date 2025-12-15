import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  DashboardCalcRunSummary,
  DashboardResponse,
  fetchDashboard,
  fetchGrindMvpRuns,
} from "../api/client";

type RunsFilter = {
  plantId: string | "all";
  flowsheetVersionId: string | "all";
  scenarioName: string | "all";
  onlyBaselines: boolean;
};

type SortField = "created_at" | "throughput" | "scenario";
type SortOrder = "desc" | "asc";

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return "Дата не указана";
  return new Date(value).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const formatKpiRow = (run: DashboardCalcRunSummary) => {
  const items: string[] = [];
  if (run.throughput_tph != null) items.push(`Производительность: ${run.throughput_tph.toFixed(1)} т/ч`);
  if (run.product_p80_mm != null) items.push(`P80: ${run.product_p80_mm.toFixed(3)} мм`);
  if (run.specific_energy_kwhpt != null)
    items.push(`Удельная энергия: ${run.specific_energy_kwhpt.toFixed(2)} кВт·ч/т`);
  return items.join(" • ");
};

const makeShortComment = (comment: string, maxLength = 80): string => {
  const trimmed = comment.trim();
  if (trimmed.length <= maxLength) return trimmed;
  return `${trimmed.slice(0, maxLength - 1)}…`;
};

const CalcRunCard = ({
  run,
  onOpen,
  isSelected,
  onToggleSelect,
}: {
  run: DashboardCalcRunSummary;
  onOpen: () => void;
  isSelected: boolean;
  onToggleSelect: (id: string) => void;
}) => {
  const scenarioName = run.scenario_name?.trim();
  const displayTitle = scenarioName && scenarioName.length > 0
    ? `Расчёт «${scenarioName}»`
    : `Расчёт от ${formatDateTime(run.created_at)}`;
  const shortId = run.id.slice(0, 8);
  const shortComment = run.comment ? makeShortComment(run.comment) : null;
  const plantLabel = run.plant_name ? `Фабрика: ${run.plant_name}` : run.plant_id ? `Фабрика ID ${run.plant_id}` : "Фабрика не указана";
  const flowsheetLabel = run.flowsheet_name
    ? `Схема: ${run.flowsheet_name}`
    : run.flowsheet_version_id
      ? `Версия схемы ID ${run.flowsheet_version_id}`
      : "Схема не указана";
  const scenarioLabel = run.scenario_name ? `Сценарий: “${run.scenario_name}”` : "Сценарий: не задан";
  const kpi = formatKpiRow(run);
  return (
    <div className="calc-run-card" onClick={onOpen} role="button" tabIndex={0}>
      <div className="card-select">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={(e) => {
            e.stopPropagation();
            onToggleSelect(run.id);
          }}
          onClick={(e) => e.stopPropagation()}
        />
      </div>
      <div className="card-top">
        <div className="card-title">
          {displayTitle}
          {run.is_baseline && <span className="badge badge-baseline">Базовый</span>}
        </div>
        <span className="chip small">{run.model_version || "model"}</span>
      </div>
      <div className="run-card-id" title={run.id}>
        ID: {shortId}
      </div>
      <div className="card-meta">
        <span>{plantLabel}</span>
        <span>•</span>
        <span>{flowsheetLabel}</span>
      </div>
      <div className="card-meta">{scenarioLabel}</div>
      {shortComment && <div className="run-card-comment">Комментарий: {shortComment}</div>}
      <div className="card-meta muted">{formatDateTime(run.created_at)}</div>
      {kpi && <div className="card-kpi">{kpi}</div>}
      {run.baseline_run_id != null && (
        <div className="chip subtle">Сравнение с базовым №{run.baseline_run_id}</div>
      )}
      <div className="card-actions">
        <button className="btn" onClick={onOpen}>
          Открыть
        </button>
      </div>
    </div>
  );
};

export const HomePage = () => {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fallbackRuns, setFallbackRuns] = useState<DashboardCalcRunSummary[]>([]);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [filter, setFilter] = useState<RunsFilter>({
    plantId: "all",
    flowsheetVersionId: "all",
    scenarioName: "all",
    onlyBaselines: false,
  });
  const [sort, setSort] = useState<{ field: SortField; order: SortOrder }>({
    field: "created_at",
    order: "desc",
  });

  const loadDashboard = () => {
    setIsLoading(true);
    setError(null);
    fetchDashboard()
      .then((data) => {
        setDashboard(data);
        if (!data.recent_calc_runs?.length) {
          fetchGrindMvpRuns()
            .then((runs) =>
              setFallbackRuns(
                runs.map((r) => ({
                  id: r.id,
                  model_version: r.model_version,
                  created_at: r.created_at,
                  scenario_name: r.scenario_name,
                  plant_id: r.plant_id,
                  flowsheet_version_id: r.flowsheet_version_id,
                  is_baseline: false,
                  comment: r.comment,
                  throughput_tph: r.throughput_tph,
                  product_p80_mm: r.product_p80_mm,
                  specific_energy_kwhpt: r.specific_energy_kwhpt,
                })),
              ),
            )
            .catch(() => setFallbackRuns([]));
        }
      })
      .catch(() => {
        setError("Не удалось загрузить дашборд");
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const toggleSelect = (id: string) => {
    setSelectedRunIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 4) return prev; // мягкий верхний предел
      return [...prev, id];
    });
  };

  const runs = dashboard?.recent_calc_runs?.length
    ? dashboard.recent_calc_runs
    : fallbackRuns;
  const allRuns = runs ?? [];

  const plantOptions = Array.from(
    allRuns.reduce((acc, run) => {
      if (run.plant_id == null && !run.plant_name) return acc;
      const id = run.plant_id != null ? String(run.plant_id) : String(run.plant_name);
      if (!acc.has(id)) {
        acc.set(id, run.plant_name ?? id);
      }
      return acc;
    }, new Map<string, string>()),
  ).map(([value, label]) => ({ value, label }));

  const flowsheetOptions = Array.from(
    allRuns.reduce((acc, run) => {
      if (run.flowsheet_version_id == null && !run.flowsheet_name) return acc;
      const id = run.flowsheet_version_id != null ? String(run.flowsheet_version_id) : String(run.flowsheet_name);
      if (!acc.has(id)) {
        acc.set(id, run.flowsheet_name ?? id);
      }
      return acc;
    }, new Map<string, string>()),
  ).map(([value, label]) => ({ value, label }));

  const scenarioOptions = Array.from(
    new Set(allRuns.map((run) => run.scenario_name).filter((name): name is string => Boolean(name))),
  ).map((name) => ({ value: name, label: name }));

  const filteredRuns = allRuns
    .filter((run) => (filter.plantId === "all" ? true : String(run.plant_id) === filter.plantId))
    .filter((run) =>
      filter.flowsheetVersionId === "all" ? true : String(run.flowsheet_version_id) === filter.flowsheetVersionId,
    )
    .filter((run) =>
      filter.scenarioName === "all"
        ? true
        : (run.scenario_name ?? "").toLowerCase() === filter.scenarioName.toLowerCase(),
    )
    .filter((run) => (filter.onlyBaselines ? run.is_baseline === true : true));

  const sortedRuns = [...filteredRuns].sort((a, b) => {
    switch (sort.field) {
      case "created_at": {
        const da = a.created_at ? new Date(a.created_at).getTime() : 0;
        const db = b.created_at ? new Date(b.created_at).getTime() : 0;
        return sort.order === "desc" ? db - da : da - db;
      }
      case "throughput": {
        const ta = a.throughput_tph ?? 0;
        const tb = b.throughput_tph ?? 0;
        return sort.order === "desc" ? tb - ta : ta - tb;
      }
      case "scenario": {
        const sa = (a.scenario_name ?? "").toLowerCase();
        const sb = (b.scenario_name ?? "").toLowerCase();
        if (sa === sb) return 0;
        if (sa < sb) return sort.order === "asc" ? -1 : 1;
        return sort.order === "asc" ? 1 : -1;
      }
      default:
        return 0;
    }
  });

  return (
    <div className="page">
      <div className="card wide-card">
        <header className="page-header">
          <div>
            <h1>GrindLab — технологическое моделирование</h1>
            <div className="meta-row">
              <span className="meta-item">Расчёты измельчения и сравнение сценариев</span>
            </div>
          </div>
          <div className="actions">
            <button className="btn secondary" onClick={() => navigate("/calc-scenarios")}>
              Сценарии расчёта
            </button>
            <button className="btn" onClick={() => navigate("/calc-run")}>
              Новый расчёт измельчения
            </button>
          </div>
        </header>

        {isLoading && <div className="muted">Загрузка дашборда…</div>}
        {error && (
          <div className="general-error" style={{ marginBottom: 12 }}>
            {error}{" "}
            <button className="btn secondary" onClick={loadDashboard} style={{ marginLeft: 8 }}>
              Повторить
            </button>
          </div>
        )}

        {dashboard && (
          <section className="section">
            <div className="kpi-grid">
              <div className="metric-card">
                <div className="stat-label">Расчёты</div>
                <div className="stat-value">{dashboard.summary?.calc_runs_total ?? 0}</div>
              </div>
              <div className="metric-card">
                <div className="stat-label">Сценарии</div>
                <div className="stat-value">{dashboard.summary?.scenarios_total ?? 0}</div>
              </div>
              <div className="metric-card">
                <div className="stat-label">Комментарии</div>
                <div className="stat-value">{dashboard.summary?.comments_total ?? 0}</div>
              </div>
              <div className="metric-card">
                <div className="stat-label">Проекты</div>
                <div className="stat-value">{dashboard.summary?.projects_total ?? 0}</div>
              </div>
            </div>
          </section>
        )}

        <section className="section">
          <div className="section-heading">
            <h2>Последние расчёты измельчения</h2>
            <p className="section-subtitle">
              Показаны последние расчёты модели grind_mvp_v1
            </p>
          </div>

          {runs && runs.length > 0 ? (
            <>
              <div className="filters-bar">
                <div className="filter-control">
                  <label>
                    Обогатительная фабрика
                    <select
                      value={filter.plantId}
                      onChange={(e) => setFilter((prev) => ({ ...prev, plantId: e.target.value as RunsFilter["plantId"] }))}
                    >
                      <option value="all">Все фабрики</option>
                      {plantOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="filter-control">
                  <label>
                    Схема измельчения
                    <select
                      value={filter.flowsheetVersionId}
                      onChange={(e) =>
                        setFilter((prev) => ({
                          ...prev,
                          flowsheetVersionId: e.target.value as RunsFilter["flowsheetVersionId"],
                        }))
                      }
                    >
                      <option value="all">Все схемы</option>
                      {flowsheetOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="filter-control">
                  <label>
                    Сценарий расчёта
                    <select
                      value={filter.scenarioName}
                      onChange={(e) =>
                        setFilter((prev) => ({ ...prev, scenarioName: e.target.value as RunsFilter["scenarioName"] }))
                      }
                    >
                      <option value="all">Все сценарии</option>
                      {scenarioOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="filter-checkbox">
                  <input
                    type="checkbox"
                    checked={filter.onlyBaselines}
                    onChange={(e) => setFilter((prev) => ({ ...prev, onlyBaselines: e.target.checked }))}
                  />
                  Показывать только базовые расчёты
                </label>
                <div className="filter-control">
                  <label>
                    Сортировать по
                    <select
                      value={`${sort.field}_${sort.order}`}
                      onChange={(e) => {
                        const [field, order] = e.target.value.split("_") as [SortField, SortOrder];
                        setSort({ field, order });
                      }}
                    >
                      <option value="created_at_desc">По дате: новые сверху</option>
                      <option value="created_at_asc">По дате: старые сверху</option>
                      <option value="throughput_desc">По производительности: от большей к меньшей</option>
                      <option value="throughput_asc">По производительности: от меньшей к большей</option>
                      <option value="scenario_asc">По сценарию: А–Я</option>
                    </select>
                  </label>
                </div>
              </div>
              <div className="calc-runs-grid">
                {sortedRuns.map((run) => (
                  <CalcRunCard
                    key={run.id}
                    run={run}
                    isSelected={selectedRunIds.includes(run.id)}
                    onToggleSelect={toggleSelect}
                    onOpen={() => navigate(`/calc-runs/${run.id}`)}
                  />
                ))}
              </div>
              <div className="calc-runs-actions">
                <span>Выбрано: {selectedRunIds.length}</span>
                <button
                  className="btn"
                  disabled={selectedRunIds.length < 2}
                  onClick={() => navigate(`/calc-runs/compare?ids=${selectedRunIds.join(",")}`)}
                >
                  Сравнить расчёты
                </button>
              </div>
            </>
          ) : !isLoading ? (
            <div className="empty-state">
              Пока нет ни одного расчёта измельчения.
              <br />
              Нажмите «Новый расчёт измельчения», чтобы создать первый.
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
};

export default HomePage;
