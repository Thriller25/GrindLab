/**
 * Flowsheet Canvas — Основной компонент редактора схемы.
 *
 * Использует React Flow для визуального построения флоушита.
 */

import { useCallback, useRef, DragEvent, useState, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  ReactFlowProvider,
  ReactFlowInstance,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { nodeTypes } from "./nodeTypes";
import { NodePalette } from "./NodePalette";
import { NodePropertyPanel } from "./NodePropertyPanel";
import { getEquipmentConfig } from "./equipmentConfig";
import type { FlowsheetNode, FlowsheetEdge, FlowsheetNodeData, EquipmentType } from "./types";
import { runSimulation } from "../../api/simulation";

/**
 * Начальные узлы для демонстрации
 */
const initialNodes: FlowsheetNode[] = [
  {
    id: "feed-1",
    type: "feed",
    position: { x: 50, y: 200 },
    data: {
      type: "feed",
      label: "Руда",
      parameters: { tph: 500, solids_pct: 100, f80_mm: 150 },
    },
  },
  {
    id: "jaw-1",
    type: "jaw_crusher",
    position: { x: 300, y: 180 },
    data: {
      type: "jaw_crusher",
      label: "Щековая дробилка",
      parameters: { css: 150, reduction_ratio: 6, capacity_tph: 600 },
    },
  },
  {
    id: "cone-1",
    type: "cone_crusher",
    position: { x: 550, y: 180 },
    data: {
      type: "cone_crusher",
      label: "Конусная дробилка",
      parameters: { css: 25, reduction_ratio: 5, capacity_tph: 400 },
    },
  },
  {
    id: "sag-1",
    type: "sag_mill",
    position: { x: 800, y: 160 },
    data: {
      type: "sag_mill",
      label: "SAG мельница",
      parameters: {
        diameter_m: 10,
        length_m: 5,
        speed_pct: 75,
        ball_charge_pct: 10,
        power_kw: 15000,
      },
    },
  },
  {
    id: "cyclone-1",
    type: "hydrocyclone",
    position: { x: 1050, y: 100 },
    data: {
      type: "hydrocyclone",
      label: "Гидроциклон",
      parameters: { d50_um: 75, sharpness: 2.5, pressure_kpa: 100, num_cyclones: 4 },
    },
  },
  {
    id: "ball-1",
    type: "ball_mill",
    position: { x: 1050, y: 300 },
    data: {
      type: "ball_mill",
      label: "Шаровая мельница",
      parameters: {
        diameter_m: 5,
        length_m: 8,
        speed_pct: 75,
        ball_charge_pct: 35,
        power_kw: 5000,
      },
    },
  },
  {
    id: "product-1",
    type: "product",
    position: { x: 1300, y: 100 },
    data: {
      type: "product",
      label: "Концентрат",
      parameters: {},
    },
  },
];

/**
 * Начальные соединения
 */
const initialEdges: FlowsheetEdge[] = [
  { id: "e-feed-jaw", source: "feed-1", target: "jaw-1", sourceHandle: "out", targetHandle: "feed" },
  { id: "e-jaw-cone", source: "jaw-1", target: "cone-1", sourceHandle: "product", targetHandle: "feed" },
  { id: "e-cone-sag", source: "cone-1", target: "sag-1", sourceHandle: "product", targetHandle: "feed" },
  { id: "e-sag-cyclone", source: "sag-1", target: "cyclone-1", sourceHandle: "product", targetHandle: "feed" },
  { id: "e-cyclone-ball", source: "cyclone-1", target: "ball-1", sourceHandle: "underflow", targetHandle: "feed" },
  { id: "e-ball-cyclone", source: "ball-1", target: "cyclone-1", sourceHandle: "product", targetHandle: "feed" },
  { id: "e-cyclone-product", source: "cyclone-1", target: "product-1", sourceHandle: "overflow", targetHandle: "in" },
];

interface FlowsheetCanvasProps {
  projectId?: string;
  scenarioId?: string;
  readOnly?: boolean;
  onSave?: (nodes: FlowsheetNode[], edges: FlowsheetEdge[]) => void;
}

/**
 * Основной компонент канвы
 */
function FlowsheetCanvasInner({
  readOnly = false,
  onSave,
}: FlowsheetCanvasProps) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance<FlowsheetNode, FlowsheetEdge> | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowsheetNode>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowsheetEdge>(initialEdges);
  const [isDirty, setIsDirty] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [globalKpi, setGlobalKpi] = useState<Record<string, number> | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  // Получить выбранный узел
  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId),
    [nodes, selectedNodeId],
  );

  // Счётчик для генерации ID
  const nodeIdCounter = useRef(100);

  /**
   * Обработка нового соединения
   */
  const onConnect = useCallback(
    (params: Connection) => {
      const newEdge: FlowsheetEdge = {
        ...params,
        id: `e-${params.source}-${params.target}-${Date.now()}`,
        type: "smoothstep",
        animated: true,
        style: { stroke: "#8b5cf6", strokeWidth: 2 },
      };
      setEdges((eds) => addEdge(newEdge, eds));
      setIsDirty(true);
    },
    [setEdges],
  );

  /**
   * Обработка drop из палитры
   */
  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();

      if (!reactFlowInstance || !reactFlowWrapper.current) return;

      const type = event.dataTransfer.getData("application/reactflow") as EquipmentType;
      if (!type) return;

      const config = getEquipmentConfig(type);
      if (!config) return;

      // Вычисляем позицию на канве
      const bounds = reactFlowWrapper.current.getBoundingClientRect();
      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
      });

      // Создаём начальные параметры из config
      const parameters: Record<string, number | string | boolean> = {};
      config.parameters.forEach((p) => {
        parameters[p.name] = p.default;
      });

      // Новый узел
      const newNode: FlowsheetNode = {
        id: `${type}-${nodeIdCounter.current++}`,
        type,
        position,
        data: {
          type,
          label: config.label,
          parameters,
        },
      };

      setNodes((nds) => nds.concat(newNode));
      setIsDirty(true);
    },
    [reactFlowInstance, setNodes],
  );

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  /**
   * Обработка выбора узла
   */
  const onSelectionChange = useCallback(({ nodes: selectedNodes }: { nodes: FlowsheetNode[] }) => {
    if (selectedNodes.length === 1) {
      setSelectedNodeId(selectedNodes[0].id);
    } else {
      setSelectedNodeId(null);
    }
  }, []);

  /**
   * Обновление данных узла (из property panel)
   */
  const handleNodeDataChange = useCallback(
    (nodeId: string, dataUpdate: Partial<FlowsheetNodeData>) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              data: { ...node.data, ...dataUpdate },
            };
          }
          return node;
        }),
      );
      setIsDirty(true);
    },
    [setNodes],
  );

  /**
   * Удаление узла
   */
  const handleNodeDelete = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
      setSelectedNodeId(null);
      setIsDirty(true);
    },
    [setNodes, setEdges],
  );

  /**
   * Удаление узла по Delete
   */
  const onNodesDelete = useCallback(() => {
    setSelectedNodeId(null);
    setIsDirty(true);
  }, []);

  const onEdgesDelete = useCallback(() => {
    setIsDirty(true);
  }, []);

  /**
   * Сохранение схемы
   */
  const handleSave = useCallback(() => {
    onSave?.(nodes, edges);
    setIsDirty(false);
  }, [nodes, edges, onSave]);

  /**
   * Запуск симуляции (EP5 API)
   */
  const handleRun = useCallback(async () => {
    setIsRunning(true);
    setRunError(null);
    setGlobalKpi(null);
    try {
      const result = await runSimulation(nodes, edges);
      if (!result.success) {
        setRunError((result.errors && result.errors[0]) || "Расчёт завершился с ошибкой");
      } else {
        setGlobalKpi(result.global_kpi || {});
      }
    } catch (e) {
      setRunError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsRunning(false);
    }
  }, [nodes, edges]);

  return (
    <div style={{ display: "flex", height: "100%", width: "100%" }}>
      {/* Palette */}
      {!readOnly && <NodePalette />}

      {/* Canvas */}
      <div ref={reactFlowWrapper} style={{ flex: 1, height: "100%" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onInit={setReactFlowInstance}
          onNodesDelete={onNodesDelete}
          onEdgesDelete={onEdgesDelete}
          onSelectionChange={onSelectionChange}
          nodeTypes={nodeTypes}
          fitView
          snapToGrid
          snapGrid={[15, 15]}
          defaultEdgeOptions={{
            type: "smoothstep",
            animated: true,
            style: { stroke: "#8b5cf6", strokeWidth: 2 },
          }}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#d1d5db" />
          <Controls />
          <MiniMap
            nodeColor={(node) => {
              const config = getEquipmentConfig(node.type || "");
              return config?.color || "#6b7280";
            }}
            maskColor="rgba(255, 255, 255, 0.8)"
            style={{ background: "#f9fafb" }}
          />

          {/* Top Panel - Title & Actions */}
          <Panel position="top-center">
            <div
              style={{
                background: "#ffffff",
                padding: "8px 16px",
                borderRadius: 8,
                boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}
            >
              <span style={{ fontWeight: 600, color: "#111827" }}>
                📐 Технологическая схема
              </span>
              <span style={{ color: "#6b7280", fontSize: 12 }}>
                {nodes.length} узлов • {edges.length} соединений
              </span>
              {isDirty && (
                <span style={{ color: "#f59e0b", fontSize: 12 }}>• Не сохранено</span>
              )}
            </div>
          </Panel>

          {/* Save Button */}
          {!readOnly && onSave && (
            <Panel position="top-right">
              <button
                onClick={handleSave}
                disabled={!isDirty}
                style={{
                  padding: "8px 16px",
                  background: isDirty ? "#3b82f6" : "#e5e7eb",
                  color: isDirty ? "#ffffff" : "#9ca3af",
                  border: "none",
                  borderRadius: 8,
                  fontWeight: 500,
                  cursor: isDirty ? "pointer" : "not-allowed",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                }}
              >
                💾 Сохранить
              </button>
            </Panel>
          )}

          {/* Run Button */}
          {!readOnly && (
            <Panel position="bottom-right">
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <button
                  onClick={handleRun}
                  disabled={isRunning}
                  style={{
                    padding: "8px 16px",
                    background: isRunning ? "#e5e7eb" : "#10b981",
                    color: isRunning ? "#9ca3af" : "#ffffff",
                    border: "none",
                    borderRadius: 8,
                    fontWeight: 500,
                    cursor: isRunning ? "not-allowed" : "pointer",
                    boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                  }}
                >
                  {isRunning ? "Рассчитываем…" : "▶ Рассчитать"}
                </button>

                {/* KPI summary */}
                {runError && (
                  <div style={{ color: "#b91c1c", background: "#fee2e2", padding: 8, borderRadius: 6, maxWidth: 360 }}>
                    {runError}
                  </div>
                )}
                {!!globalKpi && (
                  <div
                    style={{
                      background: "#ffffff",
                      border: "1px solid #e5e7eb",
                      borderRadius: 8,
                      padding: 12,
                      minWidth: 260,
                      maxWidth: 360,
                    }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: 8 }}>Результаты расчёта</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 6 }}>
                      {[
                        ["total_feed_tph", "Питание, т/ч"],
                        ["total_product_tph", "Продукт, т/ч"],
                        ["product_p80_mm", "P80, мм"],
                        ["product_p50_mm", "P50, мм"],
                        ["product_p98_mm", "P98, мм"],
                        ["product_passing_240_mesh_pct", "% -240 mesh"],
                        ["circulating_load_pct", "Цирк. нагрузка, %"],
                        ["specific_energy_kwh_t", "Удельная энергия, кВт·ч/т"],
                        ["mass_balance_error_pct", "Баланс массы, %"],
                      ].map(([key, label]) => (
                        <>
                          <div style={{ color: "#6b7280" }}>{label}</div>
                          <div style={{ textAlign: "right" }}>
                            {globalKpi && typeof (globalKpi as any)[key] === "number"
                              ? (globalKpi as any)[key].toFixed(
                                  key.endsWith("_mm") ? 3 : key.endsWith("_pct") ? 1 : 2,
                                )
                              : "—"}
                          </div>
                        </>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Panel>
          )}
        </ReactFlow>
      </div>

      {/* Property Panel (right side) */}
      {!readOnly && selectedNode && (
        <NodePropertyPanel
          node={selectedNode}
          onNodeDataChange={handleNodeDataChange}
          onNodeDelete={handleNodeDelete}
        />
      )}
    </div>
  );
}

/**
 * Обёртка с ReactFlowProvider
 */
export function FlowsheetCanvas(props: FlowsheetCanvasProps) {
  return (
    <ReactFlowProvider>
      <FlowsheetCanvasInner {...props} />
    </ReactFlowProvider>
  );
}

export default FlowsheetCanvas;
