/**
 * Equipment Node — Кастомный узел для React Flow.
 *
 * Отображает оборудование с портами и параметрами.
 */

import { memo, useMemo } from "react";
import { Handle, Position } from "@xyflow/react";
import type { FlowsheetNodeData } from "./types";
import { getEquipmentConfig } from "./equipmentConfig";

interface EquipmentNodeProps {
  data: FlowsheetNodeData;
  selected?: boolean;
}

/**
 * Кастомный узел оборудования
 */
export const EquipmentNode = memo(({ data, selected }: EquipmentNodeProps) => {
  const config = useMemo(() => getEquipmentConfig(data.type), [data.type]);

  if (!config) {
    return (
      <div style={{ padding: 10, background: "#fee2e2", border: "1px solid #ef4444", borderRadius: 8 }}>
        Unknown: {data.type}
      </div>
    );
  }

  // Стили статуса
  const statusColors = {
    idle: "#6b7280",
    running: "#f59e0b",
    success: "#22c55e",
    error: "#ef4444",
  };

  const statusColor = statusColors[data.status || "idle"];

  // Входные порты (слева)
  const inputPorts = config.ports.filter((p) => p.direction === "input");
  // Выходные порты (справа)
  const outputPorts = config.ports.filter((p) => p.direction === "output");

  return (
    <div
      style={{
        background: "#ffffff",
        border: `2px solid ${selected ? "#3b82f6" : config.color}`,
        borderRadius: 12,
        minWidth: 180,
        boxShadow: selected
          ? "0 0 0 2px rgba(59, 130, 246, 0.3)"
          : "0 2px 8px rgba(0,0,0,0.1)",
        transition: "all 0.2s ease",
      }}
    >
      {/* Header */}
      <div
        style={{
          background: config.color,
          color: "#ffffff",
          padding: "8px 12px",
          borderRadius: "10px 10px 0 0",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span style={{ fontSize: 20 }}>{config.icon}</span>
        <span style={{ fontWeight: 600, fontSize: 14 }}>{data.label || config.label}</span>
        {data.status && (
          <span
            style={{
              marginLeft: "auto",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: statusColor,
            }}
          />
        )}
      </div>

      {/* Body - параметры */}
      <div style={{ padding: "8px 12px", fontSize: 12, color: "#374151" }}>
        {config.parameters.slice(0, 3).map((param) => {
          const value = data.parameters[param.name] ?? param.default;
          return (
            <div
              key={param.name}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "2px 0",
              }}
            >
              <span style={{ color: "#6b7280" }}>{param.label}:</span>
              <span style={{ fontWeight: 500 }}>
                {typeof value === "number" ? value.toFixed(1) : value}
                {param.unit && <span style={{ color: "#9ca3af", marginLeft: 2 }}>{param.unit}</span>}
              </span>
            </div>
          );
        })}
        {config.parameters.length > 3 && (
          <div style={{ color: "#9ca3af", textAlign: "center", marginTop: 4 }}>
            +{config.parameters.length - 3} params...
          </div>
        )}
      </div>

      {/* Input Handles (left) */}
      {inputPorts.map((port, index) => (
        <Handle
          key={port.id}
          type="target"
          position={Position.Left}
          id={port.id}
          style={{
            top: `${30 + ((index + 1) * 100) / (inputPorts.length + 1)}%`,
            width: 12,
            height: 12,
            background: getPortColor(port.portType),
            border: "2px solid #ffffff",
          }}
          title={port.name}
        />
      ))}

      {/* Output Handles (right) */}
      {outputPorts.map((port, index) => (
        <Handle
          key={port.id}
          type="source"
          position={Position.Right}
          id={port.id}
          style={{
            top: `${30 + ((index + 1) * 100) / (outputPorts.length + 1)}%`,
            width: 12,
            height: 12,
            background: getPortColor(port.portType),
            border: "2px solid #ffffff",
          }}
          title={port.name}
        />
      ))}
    </div>
  );
});

EquipmentNode.displayName = "EquipmentNode";

/**
 * Цвет порта по типу потока
 */
function getPortColor(portType: string): string {
  switch (portType) {
    case "solid":
      return "#78716c"; // stone
    case "liquid":
      return "#0ea5e9"; // sky
    case "slurry":
      return "#8b5cf6"; // violet
    case "gas":
      return "#a3e635"; // lime
    default:
      return "#6b7280";
  }
}

/**
 * Карта кастомных типов узлов для React Flow
 */
export const nodeTypes = {
  feed: EquipmentNode,
  jaw_crusher: EquipmentNode,
  cone_crusher: EquipmentNode,
  sag_mill: EquipmentNode,
  ball_mill: EquipmentNode,
  hydrocyclone: EquipmentNode,
  vib_screen: EquipmentNode,
  banana_screen: EquipmentNode,
  product: EquipmentNode,
};
