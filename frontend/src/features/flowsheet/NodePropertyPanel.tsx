/**
 * NodePropertyPanel — Панель свойств выбранного узла.
 *
 * Показывает параметры узла и позволяет редактировать их.
 * Для feed узлов включает MaterialSelector.
 */

import { useCallback } from "react";
import type { FlowsheetNode, FlowsheetNodeData, MaterialSummary } from "./types";
import { getEquipmentConfig } from "./equipmentConfig";
import { MaterialSelector } from "./MaterialSelector";

interface NodePropertyPanelProps {
  /** Выбранный узел */
  node: FlowsheetNode;
  /** Callback при изменении данных узла */
  onNodeDataChange: (nodeId: string, data: Partial<FlowsheetNodeData>) => void;
  /** Callback при удалении узла */
  onNodeDelete?: (nodeId: string) => void;
}

/**
 * Панель свойств узла
 */
export function NodePropertyPanel({
  node,
  onNodeDataChange,
  onNodeDelete,
}: NodePropertyPanelProps) {
  const config = getEquipmentConfig(node.data.type);

  // Обработчик изменения параметра
  const handleParameterChange = useCallback(
    (paramName: string, value: number | string | boolean) => {
      onNodeDataChange(node.id, {
        parameters: {
          ...node.data.parameters,
          [paramName]: value,
        },
      });
    },
    [node.id, node.data.parameters, onNodeDataChange],
  );

  // Обработчик изменения label
  const handleLabelChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onNodeDataChange(node.id, { label: e.target.value });
    },
    [node.id, onNodeDataChange],
  );

  // Обработчик выбора материала (для feed узлов)
  const handleMaterialSelect = useCallback(
    (material: MaterialSummary | null) => {
      onNodeDataChange(node.id, {
        materialId: material?.id,
        materialName: material?.name,
        // Обновляем параметры из материала, если есть
        ...(material?.solids_tph && {
          parameters: {
            ...node.data.parameters,
            tph: material.solids_tph,
            f80_mm: material.p80_mm ?? node.data.parameters.f80_mm,
          },
        }),
      });
    },
    [node.id, node.data.parameters, onNodeDataChange],
  );

  if (!config) {
    return (
      <div style={panelStyle}>
        <div style={headerStyle}>⚠️ Unknown Node</div>
        <p>Node type "{node.data.type}" is not recognized.</p>
      </div>
    );
  }

  const isFeedNode = node.data.type === "feed";

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <span style={{ fontSize: 24 }}>{config.icon}</span>
        <span style={{ fontWeight: 600, fontSize: 16 }}>{config.label}</span>
      </div>

      {/* Node Label */}
      <div style={sectionStyle}>
        <label style={labelStyle}>Название</label>
        <input
          type="text"
          value={node.data.label || ""}
          onChange={handleLabelChange}
          style={inputStyle}
          placeholder={config.label}
        />
      </div>

      {/* Material Selector (for feed nodes) */}
      {isFeedNode && (
        <div style={sectionStyle}>
          <label style={labelStyle}>
            📦 Материал
            {node.data.materialName && (
              <span style={{ fontWeight: "normal", color: "#22c55e", marginLeft: 8 }}>
                ✓ {node.data.materialName}
              </span>
            )}
          </label>
          <MaterialSelector
            selectedMaterialId={node.data.materialId as string | undefined}
            onSelect={handleMaterialSelect}
          />
          {node.data.materialId && (
            <div style={{ fontSize: 11, color: "#6b7280", marginTop: 4 }}>
              Параметры будут автоматически обновлены из материала
            </div>
          )}
        </div>
      )}

      {/* Parameters */}
      <div style={sectionStyle}>
        <label style={labelStyle}>Параметры</label>
        {config.parameters.map((param) => {
          const value = node.data.parameters[param.name] ?? param.default;
          return (
            <div key={param.name} style={paramRowStyle}>
              <span style={{ color: "#6b7280", flex: 1 }}>
                {param.label}
                {param.unit && <span style={{ color: "#9ca3af" }}> ({param.unit})</span>}
              </span>
              <input
                type={param.type === "bool" ? "checkbox" : param.type === "float" || param.type === "int" ? "number" : "text"}
                value={param.type === "bool" ? undefined : String(value)}
                checked={param.type === "bool" ? Boolean(value) : undefined}
                onChange={(e) => {
                  let newValue: number | string | boolean;
                  if (param.type === "bool") {
                    newValue = e.target.checked;
                  } else if (param.type === "float" || param.type === "int") {
                    newValue = parseFloat(e.target.value) || 0;
                  } else {
                    newValue = e.target.value;
                  }
                  handleParameterChange(param.name, newValue);
                }}
                style={paramInputStyle}
                min={param.min}
                max={param.max}
                step={param.type === "float" ? 0.1 : 1}
              />
            </div>
          );
        })}
      </div>

      {/* Actions */}
      {onNodeDelete && (
        <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid #e5e7eb" }}>
          <button
            type="button"
            onClick={() => onNodeDelete(node.id)}
            style={deleteButtonStyle}
          >
            🗑️ Удалить узел
          </button>
        </div>
      )}
    </div>
  );
}

// ==================== Styles ====================

const panelStyle: React.CSSProperties = {
  width: 280,
  background: "#ffffff",
  borderLeft: "1px solid #e5e7eb",
  padding: 16,
  overflowY: "auto",
  height: "100%",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  marginBottom: 16,
  paddingBottom: 12,
  borderBottom: "1px solid #e5e7eb",
};

const sectionStyle: React.CSSProperties = {
  marginBottom: 16,
};

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 600,
  color: "#374151",
  marginBottom: 6,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  border: "1px solid #d1d5db",
  borderRadius: 6,
  fontSize: 13,
};

const paramRowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "6px 0",
  fontSize: 12,
};

const paramInputStyle: React.CSSProperties = {
  width: 80,
  padding: "4px 8px",
  border: "1px solid #d1d5db",
  borderRadius: 4,
  fontSize: 12,
  textAlign: "right",
};

const deleteButtonStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  background: "#fef2f2",
  border: "1px solid #fecaca",
  borderRadius: 6,
  color: "#dc2626",
  cursor: "pointer",
  fontSize: 13,
};

export default NodePropertyPanel;
