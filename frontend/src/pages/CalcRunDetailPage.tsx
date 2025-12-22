import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CalcRunRead, fetchCalcRun, fetchGrindMvpRun, GrindMvpRunDetail } from "../api/client";
import BackToHomeButton from "../components/BackToHomeButton";
import { DEFAULT_KPI_META, ResolvedKpiMeta, resolveKpiMeta } from "../features/kpi/kpiRegistry";

type MetricConfig = ResolvedKpiMeta;

const MISSING_VALUE_TEXT = "—";

const metricLabelWithUnit = (metric: MetricConfig) =>
  metric.unit ? `${metric.label}, ${metric.unit}` : metric.label;

const formatNumber = (value: number | null | undefined, precision: number) =>
  value == null ? MISSING_VALUE_TEXT : value.toFixed(precision);

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

const shortRunId = (id?: string | null) => {
  if (!id) return null;
  const str = String(id);
  return str.includes("-") ? str.split("-")[0] : str.slice(0, 8);
};

const STATUS_LABELS: Record<string, string> = {
  success: "Успешно",
  failed: "Ошибка",
  running: "Выполняется",
  pending: "В очереди",
};

const normalizeErrorMessage = (message?: string | null) => {
  if (!message) return null;
  const hasCyrillic = /[А-Яа-яЁё]/.test(message);
  if (hasCyrillic) return message;
  return "Расчёт завершился с ошибкой. Повторите попытку или обратитесь к администратору.";
};

export const CalcRunDetailPage = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const [meta, setMeta] = useState<CalcRunRead | null>(null);
  const [runDetail, setRunDetail] = useState<GrindMvpRunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [kpiError, setKpiError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!runId) {
      setError("Не указан идентификатор запуска.");
      setMeta(null);
      setRunDetail(null);
      return;
    }

    const load = async () => {
      setLoading(true);
      setError(null);
      setKpiError(null);
      setMeta(null);
      setRunDetail(null);

      const [metaResult, detailResult] = await Promise.allSettled([fetchCalcRun(runId), fetchGrindMvpRun(runId)]);
      if (cancelled) return;

      if (metaResult.status === "fulfilled") {
        setMeta(metaResult.value);
      } else {
        const status = axios.isAxiosError(metaResult.reason) ? metaResult.reason.response?.status : null;
        setError(status === 404 ? "Запуск не найден." : "Не удалось загрузить запуск.");
        setMeta(null);
      }

      if (detailResult.status === "fulfilled") {
        setRunDetail(detailResult.value);
      } else {
        const status = axios.isAxiosError(detailResult.reason) ? detailResult.reason.response?.status : null;
        if (status !== 404) {
          setKpiError("Не удалось загрузить KPI для этого запуска.");
        }
      }

      setLoading(false);
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [runId]);

  const kpiData = useMemo(() => (runDetail?.result?.kpi ?? {}) as Record<string, unknown>, [runDetail]);

  const metrics = useMemo<MetricConfig[]>(() => {
    const map = new Map<string, MetricConfig>();
    DEFAULT_KPI_META.forEach((metaItem) => {
      const resolved = resolveKpiMeta(metaItem.key);
      map.set(resolved.key, resolved);
    });

    Object.keys(kpiData).forEach((key) => {
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
  }, [kpiData]);

  const getKpiValue = (metric: MetricConfig) => {
    for (const key of metric.sourceKeys) {
      const value = kpiData[key];
      if (typeof value === "number") return value;
    }
    return null;
  };

  const hasKpiData = metrics.some((metric) => getKpiValue(metric) != null);

  const fullId = meta?.id ?? runDetail?.id ?? runId ?? "";
  const shortId = shortRunId(fullId);
  const projectId = meta?.project_id ?? runDetail?.project_id ?? runDetail?.input?.project_id ?? null;
  const scenarioName = meta?.scenario_name ?? runDetail?.scenario_name ?? runDetail?.input?.scenario_name;
  const scenarioId = meta?.scenario_id ?? runDetail?.scenario_id ?? runDetail?.input?.scenario_id ?? null;
  const flowsheetVersion =
    meta?.flowsheet_version_id ??
    runDetail?.flowsheet_version_id ??
    (runDetail?.input?.flowsheet_version_id ? String(runDetail.input.flowsheet_version_id) : null);
  const statusLabel = meta?.status ? STATUS_LABELS[meta.status] ?? meta.status : null;
  const errorMessage = normalizeErrorMessage(meta?.error_message);
  const createdAt = meta?.created_at ?? runDetail?.created_at ?? null;
  const updatedAt = meta?.updated_at ?? meta?.created_at ?? runDetail?.created_at ?? null;

  const handleOpenProject = () => {
    if (!projectId) return;
    navigate(`/projects/${projectId}`);
  };

  const renderMetaGrid = () => (
    <div className="grid" style={{ gap: 12 }}>
      <div className="stat">
        <div className="stat-label">Проект</div>
        <div className="stat-value">{projectId ?? MISSING_VALUE_TEXT}</div>
        <div className="muted">Можно вернуться к общему дашборду проекта.</div>
      </div>
      <div className="stat">
        <div className="stat-label">Сценарий</div>
        <div className="stat-value">{scenarioName ?? MISSING_VALUE_TEXT}</div>
        <div className="muted">
          {scenarioId ? `ID: ${scenarioId}` : "Сценарий не задан при запуске."}
        </div>
      </div>
      <div className="stat">
        <div className="stat-label">Версия схемы</div>
        <div className="stat-value">{flowsheetVersion ?? MISSING_VALUE_TEXT}</div>
        <div className="muted">От этой версии зависят доступные KPI.</div>
      </div>
    </div>
  );

  const renderKpiTable = () => {
    if (!runDetail || !metrics.length || !hasKpiData) {
      return <div className="empty-state">KPI отсутствуют для этого запуска</div>;
    }

    return (
      <table className="table">
        <thead>
          <tr>
            <th>Метрика</th>
            <th className="align-right">Значение</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => {
            const value = getKpiValue(metric);
            return (
              <tr key={metric.key}>
                <td>{metricLabelWithUnit(metric)}</td>
                <td className="align-right">{formatNumber(value, metric.precision)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  };

  const showContent = !!meta || !!runDetail;

  return (
    <div className="page">
      <div className="card wide-card">
        <header className="page-header">
          <div>
            <h1>
              Запуск расчёта{" "}
              {shortId && (
                <span className="muted" title={fullId}>
                  №{shortId}
                </span>
              )}
            </h1>
            <div className="meta-row">
              <span className="meta-item">
                Статус:{" "}
                {statusLabel ? <span className="chip small">{statusLabel}</span> : MISSING_VALUE_TEXT}
              </span>
              <span className="meta-sep">•</span>
              <span className="meta-item">Создан: {formatDateTime(createdAt)}</span>
              <span className="meta-sep">•</span>
              <span className="meta-item">Обновлён: {formatDateTime(updatedAt)}</span>
            </div>
            <div className="meta-row">
              <span className="meta-item">Версия модели: {runDetail?.result?.model_version ?? runDetail?.model_version ?? "—"}</span>
              <span className="meta-sep">•</span>
              <span className="meta-item">Запуск: {runDetail?.id ?? meta?.id ?? runId ?? MISSING_VALUE_TEXT}</span>
            </div>
          </div>
          <div className="actions">
            {projectId && (
              <button className="btn secondary" type="button" onClick={handleOpenProject}>
                К проекту
              </button>
            )}
            <BackToHomeButton />
          </div>
        </header>

        {loading && <div className="muted">Загружаем данные запуска...</div>}
        {error && <div className="general-error">{error}</div>}

        {showContent && (
          <>
            {errorMessage && <div className="alert error">{errorMessage}</div>}
            <section className="section">
              <div className="section-heading">
                <h2>Метаданные</h2>
                <p className="section-subtitle">Проект, сценарий и версия схемы, с которой выполнен расчёт.</p>
              </div>
              {renderMetaGrid()}
            </section>

            <section className="section">
              <div className="section-heading">
                <h2>KPI запуска</h2>
                <p className="section-subtitle">Форматирование и порядок метрик совпадает со страницей сравнения.</p>
              </div>
              {kpiError && <div className="alert error">{kpiError}</div>}
              {renderKpiTable()}
            </section>
          </>
        )}
      </div>
    </div>
  );
};

export default CalcRunDetailPage;
