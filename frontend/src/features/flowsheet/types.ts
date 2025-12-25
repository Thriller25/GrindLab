/**
 * Flowsheet Canvas Types — F4.3 Canvas Editor
 *
 * Типы данных для визуального редактора технологических схем.
 */

import type { Node, Edge } from "@xyflow/react";

/**
 * Категории оборудования
 */
export type NodeCategory =
  | "size_reduction"
  | "classification"
  | "auxiliary"
  | "feed"
  | "product";

/**
 * Типы оборудования, соответствуют backend Node Library
 */
export type EquipmentType =
  | "jaw_crusher"
  | "cone_crusher"
  | "sag_mill"
  | "ball_mill"
  | "hydrocyclone"
  | "vib_screen"
  | "banana_screen"
  | "feed"
  | "product";

/**
 * Конфигурация порта узла
 */
export interface PortConfig {
  id: string;
  name: string;
  direction: "input" | "output";
  portType: "solid" | "liquid" | "slurry" | "gas";
  required: boolean;
}

/**
 * Параметр оборудования
 */
export interface EquipmentParameter {
  name: string;
  label: string;
  type: "float" | "int" | "bool" | "string" | "select";
  unit?: string;
  min?: number;
  max?: number;
  default: number | string | boolean;
  options?: string[]; // для select
}

/**
 * Конфигурация типа оборудования
 */
export interface EquipmentConfig {
  type: EquipmentType;
  category: NodeCategory;
  label: string;
  description: string;
  icon: string; // emoji или путь к иконке
  ports: PortConfig[];
  parameters: EquipmentParameter[];
  color: string;
}

/**
 * Данные узла на канве (с index signature для React Flow)
 */
export interface FlowsheetNodeData {
  [key: string]: unknown;
  type: EquipmentType;
  label: string;
  parameters: Record<string, number | string | boolean>;
  status?: "idle" | "running" | "success" | "error";
  results?: Record<string, unknown>;
  /** ID назначенного материала (для feed узлов) */
  materialId?: string;
  /** Название назначенного материала */
  materialName?: string;
}

/**
 * Типизированный узел React Flow
 */
export type FlowsheetNode = Node<FlowsheetNodeData, EquipmentType>;

/**
 * Данные связи между узлами (с index signature для React Flow)
 */
export interface FlowsheetEdgeData {
  [key: string]: unknown;
  sourcePort?: string;
  targetPort?: string;
  streamType?: "solid" | "liquid" | "slurry";
}

/**
 * Типизированное соединение React Flow
 */
export type FlowsheetEdge = Edge<FlowsheetEdgeData>;

/**
 * Полная схема флоушита
 */
export interface FlowsheetSchema {
  id: string;
  name: string;
  version: number;
  nodes: FlowsheetNode[];
  edges: FlowsheetEdge[];
  createdAt: string;
  updatedAt: string;
}

/**
 * Состояние канвы
 */
export interface CanvasState {
  nodes: FlowsheetNode[];
  edges: FlowsheetEdge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  isDirty: boolean;
  isRunning: boolean;
}

// ==================== Material Types ====================

/**
 * Точка PSD (размер - % прохода)
 */
export interface PSDPoint {
  size_mm: number;
  cum_passing: number;
}

/**
 * Материал для назначения на feed
 */
export interface MaterialSummary {
  id: string;
  name: string;
  source?: string;
  solids_tph?: number;
  p80_mm?: number;
  psd?: PSDPoint[];
  createdAt?: string;
}
