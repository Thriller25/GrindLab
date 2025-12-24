/**
 * Flowsheet Page — Страница редактора технологической схемы.
 *
 * Интегрирует FlowsheetCanvas с навигацией и сохранением.
 */

import { useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { FlowsheetCanvas } from "../features/flowsheet";
import type { FlowsheetNode, FlowsheetEdge } from "../features/flowsheet";

export const FlowsheetPage = () => {
  const { projectId, scenarioId } = useParams<{ projectId: string; scenarioId?: string }>();
  const navigate = useNavigate();

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
      </header>

      {/* Canvas */}
      <main style={{ flex: 1, overflow: "hidden" }}>
        <FlowsheetCanvas
          projectId={projectId}
          scenarioId={scenarioId}
          onSave={handleSave}
        />
      </main>
    </div>
  );
};

export default FlowsheetPage;
