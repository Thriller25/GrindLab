/**
 * Node Palette — Палитра узлов для drag-and-drop.
 *
 * Позволяет перетаскивать оборудование на канву.
 */

import { memo, DragEvent } from "react";
import {
  CATEGORY_LABELS,
  CATEGORY_COLORS,
  getEquipmentByCategory,
} from "./equipmentConfig";
import type { EquipmentConfig, NodeCategory } from "./types";

interface NodePaletteProps {
  onDragStart?: (event: DragEvent, config: EquipmentConfig) => void;
}

/**
 * Палитра узлов с группировкой по категориям
 */
export const NodePalette = memo(({ onDragStart }: NodePaletteProps) => {
  // Категории в нужном порядке
  const categoryOrder: NodeCategory[] = [
    "feed",
    "size_reduction",
    "classification",
    "product",
  ];

  const handleDragStart = (event: DragEvent, config: EquipmentConfig) => {
    // Передаём тип оборудования через dataTransfer
    event.dataTransfer.setData("application/reactflow", config.type);
    event.dataTransfer.setData("application/json", JSON.stringify(config));
    event.dataTransfer.effectAllowed = "move";
    onDragStart?.(event, config);
  };

  return (
    <div
      style={{
        width: 240,
        height: "100%",
        background: "#f9fafb",
        borderRight: "1px solid #e5e7eb",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #e5e7eb",
          background: "#ffffff",
        }}
      >
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "#111827" }}>
          🔧 Оборудование
        </h3>
        <p style={{ margin: "4px 0 0", fontSize: 12, color: "#6b7280" }}>
          Перетащите на схему
        </p>
      </div>

      {/* Categories */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "8px",
        }}
      >
        {categoryOrder.map((category) => {
          const items = getEquipmentByCategory(category);
          if (items.length === 0) return null;

          return (
            <div key={category} style={{ marginBottom: 16 }}>
              {/* Category Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "4px 8px",
                  marginBottom: 4,
                }}
              >
                <div
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: 3,
                    background: CATEGORY_COLORS[category],
                  }}
                />
                <span style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>
                  {CATEGORY_LABELS[category]}
                </span>
              </div>

              {/* Equipment Items */}
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {items.map((config) => (
                  <PaletteItem
                    key={config.type}
                    config={config}
                    onDragStart={handleDragStart}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer hint */}
      <div
        style={{
          padding: "8px 16px",
          borderTop: "1px solid #e5e7eb",
          background: "#ffffff",
          fontSize: 11,
          color: "#9ca3af",
          textAlign: "center",
        }}
      >
        💡 Двойной клик для параметров
      </div>
    </div>
  );
});

NodePalette.displayName = "NodePalette";

/**
 * Элемент палитры (draggable)
 */
interface PaletteItemProps {
  config: EquipmentConfig;
  onDragStart: (event: DragEvent, config: EquipmentConfig) => void;
}

const PaletteItem = memo(({ config, onDragStart }: PaletteItemProps) => {
  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, config)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 10px",
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        cursor: "grab",
        transition: "all 0.15s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = config.color;
        e.currentTarget.style.boxShadow = `0 2px 8px ${config.color}20`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "#e5e7eb";
        e.currentTarget.style.boxShadow = "none";
      }}
      title={config.description}
    >
      <span style={{ fontSize: 18 }}>{config.icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: "#111827" }}>
          {config.label}
        </div>
        <div
          style={{
            fontSize: 11,
            color: "#9ca3af",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {config.ports.length} порт{config.ports.length > 1 ? "а" : ""}
        </div>
      </div>
    </div>
  );
});

PaletteItem.displayName = "PaletteItem";

export default NodePalette;
