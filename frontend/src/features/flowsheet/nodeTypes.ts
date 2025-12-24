/**
 * Node Types — Карта кастомных типов узлов для React Flow.
 *
 * Вынесено в отдельный файл для поддержки Fast Refresh.
 */

import { EquipmentNode } from "./EquipmentNode";

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
