/**
 * Flowsheet Feature — Экспорты модуля.
 */

export { FlowsheetCanvas } from "./FlowsheetCanvas";
export { NodePalette } from "./NodePalette";
export { EquipmentNode } from "./EquipmentNode";
export { nodeTypes } from "./nodeTypes";
export { EQUIPMENT_CONFIGS, getEquipmentConfig, getEquipmentByCategory, CATEGORY_LABELS, CATEGORY_COLORS } from "./equipmentConfig";
export type {
  NodeCategory,
  EquipmentType,
  PortConfig,
  EquipmentParameter,
  EquipmentConfig,
  FlowsheetNodeData,
  FlowsheetNode,
  FlowsheetEdgeData,
  FlowsheetEdge,
  FlowsheetSchema,
  CanvasState,
} from "./types";
