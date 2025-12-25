import axios from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  CalcRunRead,
  ProjectComment,
  createProjectComment,
  fetchCalcRun,
  fetchCalcRunComments,
  fetchGrindMvpRun,
  GrindMvpRunDetail,
  isAuthExpiredError,
  PSDData,
  StreamData,
} from "../api/client";
import BackToHomeButton from "../components/BackToHomeButton";
import { PSDChart } from "../components/PSDChart";
import { DEFAULT_KPI_META, ResolvedKpiMeta, resolveKpiMeta } from "../features/kpi/kpiRegistry";
import { hasAuth } from "../auth/authProvider";

type MetricConfig = ResolvedKpiMeta;

const MISSING_VALUE_TEXT = "—";

const metricLabelWithUnit = (metric: MetricConfig) =>
  metric.unit ? `${metric.label}, ${metric.unit}` : metric.label;

const formatNumber = (value: number | null | undefined, precision: number) =>
  value == null ? MISSING_VALUE_TEXT : value.toFixed(precision);

const formatMm = (value: number | null | undefined) =>
  value == null ? MISSING_VALUE_TEXT : `${value.toFixed(3)} мм`;

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

type SizeDistributionPoint = { size_mm: number; cum_percent: number };

function computePx(targetPercent: number, points: SizeDistributionPoint[]): number | null {
  if (!points || points.length < 2) return null;

  const sorted = [...points].sort((a, b) => a.cum_percent - b.cum_percent);

  if (targetPercent <= sorted[0].cum_percent) return sorted[0].size_mm;
  if (targetPercent >= sorted[sorted.length - 1].cum_percent) return sorted[sorted.length - 1].size_mm;

  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i];
    const b = sorted[i + 1];
    if (targetPercent >= a.cum_percent && targetPercent <= b.cum_percent) {
      const span = b.cum_percent - a.cum_percent;
      if (span === 0) return b.size_mm;
      const ratio = (targetPercent - a.cum_percent) / span;
      return a.size_mm + (b.size_mm - a.size_mm) * ratio;
    }
  }

  return null;
}

function convertSizeDistributionToPSD(points: SizeDistributionPoint[]): PSDData {
  return {
    sizes_mm: points.map((p) => p.size_mm),
    cum_passing: points.map((p) => p.cum_percent),
    p80: computePx(80, points) ?? undefined,
    p50: computePx(50, points) ?? undefined,
    p240_passing: undefined,
  };
}

/**
 * Извлечь PSD данные из result_json.streams
 */
function extractPSDFromStreams(resultJson: any): PSDData[] {
  const psdDatasets: PSDData[] = [];

  if (!resultJson || !resultJson.streams) {
    return psdDatasets;
  }

  const streams = resultJson.streams as Record<string, StreamData>;

  for (const [streamId, stream] of Object.entries(streams)) {
    const psd = stream.material?.psd;
    if (!psd || !psd.points || psd.points.length === 0) {
      continue;
    }

    // Преобразуем points в массивы для графика
    const sizes_mm = psd.points.map((p) => p.size_mm);
    const cum_passing = psd.points.map((p) => p.cum_passing);

    psdDatasets.push({
      sizes_mm,
      cum_passing,
      p80: psd.p80,
      p50: psd.p50,
      p240_passing: psd.p240_passing,
    });
  }

  return psdDatasets;
}

function pickProductPSD(resultJson: any): PSDData | null {
  // Сначала проверяем новый формат size_distribution
  if (resultJson?.size_distribution?.product) {
    const product = resultJson.size_distribution.product as Array<{ size_mm: number; cum_percent: number }>;
    if (product.length > 0) {
      return convertSizeDistributionToPSD(product);
    }
  }

  // Fallback: старый формат streams
  if (!resultJson || !resultJson.streams) return null;

  const streams = Object.values(resultJson.streams as Record<string, StreamData>);
  const hasPoints = (stream: StreamData) => Boolean(stream.material?.psd?.points?.length);
  const productStream = streams.find((s) => s.stream_type === "product" && hasPoints(s)) ?? streams.find(hasPoints);
  if (!productStream?.material?.psd) return null;
  const psd = productStream.material.psd;
  return {
    sizes_mm: psd.points?.map((p) => p.size_mm) ?? [],
    cum_passing: psd.points?.map((p) => p.cum_passing) ?? [],
    p80: psd.p80,
    p50: psd.p50,
    p240_passing: psd.p240_passing,
  };
}

/**
 * Extract fact PSD from input_json.fact_psd or result_json.size_distribution.feed
 */
function pickFactPSD(inputJson: any, resultJson?: any): PSDData | null {
  // Проверяем result_json.size_distribution.feed (новый формат)
  if (resultJson?.size_distribution?.feed) {
    const feed = resultJson.size_distribution.feed as Array<{ size_mm: number; cum_percent: number }>;
    if (feed.length > 0) {
      return convertSizeDistributionToPSD(feed);
    }
  }

  // Fallback: старый формат input_json.fact_psd
  if (!inputJson?.fact_psd?.points || inputJson.fact_psd.points.length === 0) return null;

  const points = inputJson.fact_psd.points as Array<{ size_um: number; pass_pct: number }>;
  return {
    sizes_mm: points.map((p) => p.size_um / 1000),
    cum_passing: points.map((p) => p.pass_pct),
    p80: inputJson.fact_psd.p80_um ? inputJson.fact_psd.p80_um / 1000 : undefined,
    p50: inputJson.fact_psd.p50_um ? inputJson.fact_psd.p50_um / 1000 : undefined,
    p240_passing: undefined,
  };
}

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
  const [runComments, setRunComments] = useState<ProjectComment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);
  const [commentSuccess, setCommentSuccess] = useState<string | null>(null);
  const [commentModalOpen, setCommentModalOpen] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [commentSaving, setCommentSaving] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(() => hasAuth());
  const [authExpired, setAuthExpired] = useState(false);

  const loadComments = useCallback(() => {
    if (!runId) return;
    setCommentsLoading(true);
    setCommentError(null);
    fetchCalcRunComments(runId, 20)
      .then((resp) => setRunComments(resp.items ?? []))
      .catch(() => setCommentError("Не удалось загрузить комментарии. Попробуйте ещё раз."))
      .finally(() => setCommentsLoading(false));
  }, [runId]);

  useEffect(() => {
    let cancelled = false;
    if (!runId) {
      setError("Не указан идентификатор запуска.");
      setMeta(null);
      setRunDetail(null);
      setRunComments([]);
      setCommentSuccess(null);
      setCommentError(null);
      setRunComments([]);
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

      if (metaResult.status === "fulfilled" || detailResult.status === "fulfilled") {
        loadComments();
      }
      setLoading(false);
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [runId, loadComments]);

  useEffect(() => {
    const syncAuth = () => {
      const hasToken = hasAuth();
      setIsAuthenticated(hasToken);
      if (hasToken) setAuthExpired(false);
    };
    syncAuth();
    window.addEventListener("storage", syncAuth);
    window.addEventListener("focus", syncAuth);
    return () => {
      window.removeEventListener("storage", syncAuth);
      window.removeEventListener("focus", syncAuth);
    };
  }, []);

  const kpiData = useMemo(() => (runDetail?.result?.kpi ?? {}) as Record<string, unknown>, [runDetail]);

  const psdDatasets = useMemo(() => {
    if (!meta?.result_json) return [];
    return extractPSDFromStreams(meta.result_json);
  }, [meta]);

  const productPsd = useMemo(() => {
    if (!meta?.result_json) return null;
    return pickProductPSD(meta.result_json);
  }, [meta]);
  const targetP80Mm = useMemo(() => {
    const raw =
      meta?.input_json?.target_p80_microns ??
      meta?.input_json?.target_p80_um;

    if (typeof raw === "number" && Number.isFinite(raw)) return raw / 1000;
    if (typeof raw === "string") {
      const num = Number(raw);
      if (Number.isFinite(num)) return num / 1000;
    }
    return null;
  }, [meta]);

  const factPsd = useMemo(() => {
    if (!meta) return null;
    return pickFactPSD(meta.input_json, meta.result_json);
  }, [meta]);

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

  const canComment = Boolean(projectId);
  const commentButtonDisabled = !canComment || !isAuthenticated || authExpired || commentSaving;
  const commentButtonTitle = !isAuthenticated
    ? "Требуется вход"
    : authExpired
      ? "Сессия истекла. Войдите снова."
      : undefined;
  const handleOpenProject = () => {
    if (!projectId) return;
    navigate(`/projects/${projectId}`);
  };

  const openCommentModal = () => {
    setCommentError(null);
    setCommentSuccess(null);
    setCommentModalOpen(true);
    setCommentText("");
  };

  const handleSaveComment = async () => {
    if (!projectId || !runId) {
      setCommentError("Не удалось определить проект и запуск для комментария.");
      return;
    }
    const trimmed = commentText.trim();
    if (!trimmed) return;
    setCommentSaving(true);
    setCommentError(null);
    try {
      await createProjectComment(projectId, { calc_run_id: runId, text: trimmed });
      setCommentModalOpen(false);
      setCommentText("");
      setCommentSuccess("Комментарий сохранён.");
      loadComments();
    } catch (err) {
      if (isAuthExpiredError(err)) {
        setAuthExpired(true);
        setIsAuthenticated(false);
        setCommentModalOpen(false);
        setCommentText("");
        setCommentSuccess(null);
        setCommentError("Сессия истекла. Войдите снова.");
      } else if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 403) {
          setCommentError("Недостаточно прав для изменения комментариев.");
        } else if (status === 400) {
          setCommentError("Комментарии недоступны для этого запуска.");
        } else {
          setCommentError("Не удалось сохранить комментарий. Попробуйте ещё раз.");
        }
      } else {
        setCommentError("Не удалось сохранить комментарий. Попробуйте ещё раз.");
      }
    } finally {
      setCommentSaving(false);
    }
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
            <button
              className="btn secondary"
              type="button"
              onClick={openCommentModal}
              disabled={commentButtonDisabled}
              title={commentButtonTitle}
            >
              Добавить комментарий
            </button>
            <BackToHomeButton />
          </div>
        </header>

        {authExpired && <div className="alert error">Сессия истекла. Войдите снова.</div>}
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

            {(productPsd || factPsd) && (
              <section className="section">
                <div className="section-heading">
                  <h2>Fact vs Model (P80/P50)</h2>
                  <p className="section-subtitle">
                    {factPsd
                      ? "Сравнение измеренной PSD с расчётной моделью и целевым P80/P50."
                      : "Сравнение расчётной PSD продукта с целевым P80."}
                  </p>
                </div>
                <div className="grid" style={{ gap: 12, marginBottom: 16 }}>
                  {factPsd && (
                    <>
                      <div className="stat">
                        <div className="stat-label">Fact P80</div>
                        <div className="stat-value">{formatMm(factPsd.p80)}</div>
                      </div>
                      <div className="stat">
                        <div className="stat-label">Model P80</div>
                        <div className="stat-value">{formatMm(productPsd?.p80)}</div>
                      </div>
                      <div className="stat">
                        <div className="stat-label">Δ P80 (fact - model)</div>
                        <div className="stat-value">{formatMm(factPsd.p80 != null && productPsd?.p80 != null ? factPsd.p80 - productPsd.p80 : null)}</div>
                      </div>
                      <div className="stat">
                        <div className="stat-label">Fact P50</div>
                        <div className="stat-value">{formatMm(factPsd.p50)}</div>
                      </div>
                      <div className="stat">
                        <div className="stat-label">Model P50</div>
                        <div className="stat-value">{formatMm(productPsd?.p50)}</div>
                      </div>
                      <div className="stat">
                        <div className="stat-label">Δ P50 (fact - model)</div>
                        <div className="stat-value">{formatMm(factPsd.p50 != null && productPsd?.p50 != null ? factPsd.p50 - productPsd.p50 : null)}</div>
                      </div>
                    </>
                  )}
                  {!factPsd && productPsd && (
                    <>
                      <div className="stat">
                        <div className="stat-label">Model P80</div>
                        <div className="stat-value">{formatMm(productPsd.p80)}</div>
                      </div>
                      <div className="stat">
                        <div className="stat-label">Target P80</div>
                        <div className="stat-value">{formatMm(targetP80Mm)}</div>
                      </div>
                      <div className="stat">
                        <div className="stat-label">Δ P80 (model - target)</div>
                        <div className="stat-value">{formatMm(productPsd.p80 != null && targetP80Mm != null ? productPsd.p80 - targetP80Mm : null)}</div>
                      </div>
                    </>
                  )}
                </div>
                {factPsd && productPsd ? (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginBottom: 16 }}>
                    <div>
                      <h3 style={{ fontSize: "0.9rem", marginBottom: "0.5rem", color: "#666" }}>Fact PSD</h3>
                      <PSDChart data={factPsd} height={300} />
                    </div>
                    <div>
                      <h3 style={{ fontSize: "0.9rem", marginBottom: "0.5rem", color: "#666" }}>Model PSD (с целевым P80)</h3>
                      <PSDChart data={productPsd} targetP80Mm={targetP80Mm ?? undefined} height={300} />
                    </div>
                  </div>
                ) : productPsd ? (
                  <>
                    <PSDChart data={productPsd} targetP80Mm={targetP80Mm ?? undefined} height={360} />
                    {!targetP80Mm && <div className="muted" style={{ marginTop: 8 }}>Целевой P80 не указан в входных данных.</div>}
                  </>
                ) : null}
              </section>
            )}

            {psdDatasets.length > 0 && (
              <section className="section">
                <div className="section-heading">
                  <h2>Гранулометрический состав</h2>
                  <p className="section-subtitle">Кривые проходов по крупности (PSD) для потоков схемы.</p>
                </div>
                {psdDatasets.map((psd, index) => (
                  <div key={index} style={{ marginBottom: "2rem" }}>
                    <h3 style={{ fontSize: "1rem", marginBottom: "0.5rem", color: "#666" }}>
                      Поток {index + 1}
                    </h3>
                    <PSDChart data={psd} />
                  </div>
                ))}
              </section>
            )}

            <section className="section">
              <div className="section-heading">
                <h2>Комментарии к запуску</h2>
                <p className="section-subtitle">Всего: {runComments.length}</p>
              </div>
              {commentError && <div className="alert error">{commentError}</div>}
              {commentSuccess && <div className="alert success">{commentSuccess}</div>}
              {commentsLoading ? (
                <div className="muted">Загружаем комментарии...</div>
              ) : runComments.length ? (
                <ul className="comments-list">
                  {runComments.map((comment) => (
                    <li key={comment.id} className="comment-item">
                      <div className="comment-text">{comment.text}</div>
                      <div className="muted">
                        {(comment.author && comment.author.trim()) || "anonymous"} · {formatDateTime(comment.created_at)}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="empty-state">Комментариев пока нет.</div>
              )}
            </section>

          </>
        )}
      </div>
            {commentModalOpen && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Комментарий к запуску</h3>
            <label>
              Текст комментария
              <textarea
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="Введите комментарий"
              />
            </label>
            <div className="actions modal-actions">
              <button className="btn secondary" type="button" onClick={() => setCommentModalOpen(false)} disabled={commentSaving}>
                Отмена
              </button>
              <button
                className="btn"
                type="button"
                onClick={handleSaveComment}
                disabled={commentSaving || !commentText.trim() || !isAuthenticated || authExpired}
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CalcRunDetailPage;
