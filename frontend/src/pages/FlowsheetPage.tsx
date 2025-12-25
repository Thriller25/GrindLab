/**
 * Flowsheet Page — Страница редактора технологической схемы.
 *
 * Интегрирует FlowsheetCanvas с навигацией и сохранением.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { FlowsheetCanvas } from "../features/flowsheet";
import { fetchCalcScenario } from "../api/client";
import type { FlowsheetNode, FlowsheetEdge } from "../features/flowsheet";

export const FlowsheetPage = () => {
  const { projectId, scenarioId } = useParams<{ projectId: string; scenarioId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [flowsheetVersionId, setFlowsheetVersionId] = useState<string | null>(null);
  const [isLoadingScenario, setIsLoadingScenario] = useState(false);

  /**
   * Загрузка сценария для получения flowsheet_version_id
   */
  useEffect(() => {
    if (!scenarioId) {
      // Try to get from URL param
      const fvId = searchParams.get("flowsheetVersionId");
      if (fvId) {
        setFlowsheetVersionId(fvId);
      }
      return;
    }

    setIsLoadingScenario(true);
    fetchCalcScenario(scenarioId)
      .then((scenario) => {
        if (scenario.flowsheet_version_id) {
          setFlowsheetVersionId(String(scenario.flowsheet_version_id));
        }
      })
      .catch(() => {
        // Fallback to URL param
        const fvId = searchParams.get("flowsheetVersionId");
        if (fvId) {
          setFlowsheetVersionId(fvId);
        }
      })
      .finally(() => {
        setIsLoadingScenario(false);
      });
  }, [scenarioId, searchParams]);

  /**
   * Сохранение схемы (TODO: API интеграция)
   */
  const handleSave = useCallback(
    (nodes: FlowsheetNode[], edges: FlowsheetEdge[]) => {
      console.log("Saving flowsheet:", { projectId, scenarioId, nodes, edges });
      // TODO: POST to backend API
      alert(`Схема сохранена: ${nodes.length} узлов, ${edges.length} соединений`);
    },
    [projectId, scenarioId],
  );

  /**
   * Назад к проекту
   */
  const handleBack = () => {
    if (projectId) {
      navigate(`/projects/${projectId}`);
    } else {
      navigate("/");
    }
  };

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#f3f4f6",
      }}
    >
      {/* Header */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "12px 20px",
          background: "#ffffff",
          borderBottom: "1px solid #e5e7eb",
        }}
      >
        <button
          onClick={handleBack}
          style={{
            padding: "6px 12px",
            background: "#f3f4f6",
            border: "1px solid #d1d5db",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          ← Назад
        </button>
        <h1 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: "#111827" }}>
          📐 Редактор технологической схемы
        </h1>
        {projectId && (
          <span style={{ color: "#6b7280", fontSize: 13 }}>
            Проект: {projectId}
            {scenarioId && ` / Сценарий: ${scenarioId}`}
          </span>
        )}
        {isLoadingScenario && <span style={{ color: "#6b7280", fontSize: 12 }}>загружаем версию схемы…</span>}
      </header>

      {/* Canvas */}
      <main style={{ flex: 1, overflow: "hidden" }}>
        <FlowsheetCanvas
          projectId={projectId}
          scenarioId={scenarioId}
          flowsheetVersionId={flowsheetVersionId || undefined}
          onSave={handleSave}
        />
      </main>
    </div>
  );
};

export default FlowsheetPage;
