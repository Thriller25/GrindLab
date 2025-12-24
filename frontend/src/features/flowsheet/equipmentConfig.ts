/**
 * Equipment Config — Конфигурация оборудования для палитры узлов.
 *
 * Соответствует backend Node Library (F4.2).
 */

import type { EquipmentConfig, NodeCategory } from "./types";

/**
 * Цвета по категориям
 */
export const CATEGORY_COLORS: Record<NodeCategory, string> = {
  size_reduction: "#ef4444", // red
  classification: "#3b82f6", // blue
  auxiliary: "#6b7280", // gray
  feed: "#22c55e", // green
  product: "#a855f7", // purple
};

/**
 * Конфигурации всех типов оборудования
 */
export const EQUIPMENT_CONFIGS: EquipmentConfig[] = [
  // ===== Feed =====
  {
    type: "feed",
    category: "feed",
    label: "Питание",
    description: "Исходный поток материала",
    icon: "📥",
    color: CATEGORY_COLORS.feed,
    ports: [
      { id: "out", name: "Выход", direction: "output", portType: "solid", required: true },
    ],
    parameters: [
      { name: "tph", label: "Производительность", type: "float", unit: "т/ч", min: 0, max: 10000, default: 100 },
      { name: "solids_pct", label: "% твёрдого", type: "float", unit: "%", min: 0, max: 100, default: 100 },
      { name: "f80_mm", label: "F80", type: "float", unit: "мм", min: 0.001, max: 1000, default: 150 },
    ],
  },

  // ===== Crushers =====
  {
    type: "jaw_crusher",
    category: "size_reduction",
    label: "Щековая дробилка",
    description: "Первичное дробление, CSS 50-400мм",
    icon: "🔨",
    color: CATEGORY_COLORS.size_reduction,
    ports: [
      { id: "feed", name: "Питание", direction: "input", portType: "solid", required: true },
      { id: "product", name: "Продукт", direction: "output", portType: "solid", required: true },
    ],
    parameters: [
      { name: "css", label: "CSS", type: "float", unit: "мм", min: 50, max: 400, default: 150 },
      { name: "reduction_ratio", label: "Степень дробления", type: "float", min: 3, max: 8, default: 6 },
      { name: "capacity_tph", label: "Производительность", type: "float", unit: "т/ч", min: 50, max: 2000, default: 500 },
    ],
  },
  {
    type: "cone_crusher",
    category: "size_reduction",
    label: "Конусная дробилка",
    description: "Вторичное/третичное дробление, CSS 10-100мм",
    icon: "⚙️",
    color: CATEGORY_COLORS.size_reduction,
    ports: [
      { id: "feed", name: "Питание", direction: "input", portType: "solid", required: true },
      { id: "product", name: "Продукт", direction: "output", portType: "solid", required: true },
    ],
    parameters: [
      { name: "css", label: "CSS", type: "float", unit: "мм", min: 10, max: 100, default: 25 },
      { name: "reduction_ratio", label: "Степень дробления", type: "float", min: 3, max: 8, default: 5 },
      { name: "capacity_tph", label: "Производительность", type: "float", unit: "т/ч", min: 50, max: 1500, default: 400 },
    ],
  },

  // ===== Mills =====
  {
    type: "sag_mill",
    category: "size_reduction",
    label: "SAG мельница",
    description: "Полусамоизмельчение с Bond моделью",
    icon: "🔄",
    color: CATEGORY_COLORS.size_reduction,
    ports: [
      { id: "feed", name: "Питание", direction: "input", portType: "slurry", required: true },
      { id: "product", name: "Продукт", direction: "output", portType: "slurry", required: true },
    ],
    parameters: [
      { name: "diameter_m", label: "Диаметр", type: "float", unit: "м", min: 4, max: 14, default: 10 },
      { name: "length_m", label: "Длина", type: "float", unit: "м", min: 2, max: 8, default: 5 },
      { name: "speed_pct", label: "Скорость", type: "float", unit: "% крит.", min: 50, max: 90, default: 75 },
      { name: "ball_charge_pct", label: "Шаровая загрузка", type: "float", unit: "%", min: 0, max: 20, default: 10 },
      { name: "power_kw", label: "Мощность", type: "float", unit: "кВт", min: 1000, max: 30000, default: 15000 },
    ],
  },
  {
    type: "ball_mill",
    category: "size_reduction",
    label: "Шаровая мельница",
    description: "Тонкое измельчение с Bond моделью",
    icon: "⚫",
    color: CATEGORY_COLORS.size_reduction,
    ports: [
      { id: "feed", name: "Питание", direction: "input", portType: "slurry", required: true },
      { id: "product", name: "Продукт", direction: "output", portType: "slurry", required: true },
    ],
    parameters: [
      { name: "diameter_m", label: "Диаметр", type: "float", unit: "м", min: 2, max: 8, default: 5 },
      { name: "length_m", label: "Длина", type: "float", unit: "м", min: 4, max: 14, default: 8 },
      { name: "speed_pct", label: "Скорость", type: "float", unit: "% крит.", min: 60, max: 85, default: 75 },
      { name: "ball_charge_pct", label: "Шаровая загрузка", type: "float", unit: "%", min: 25, max: 45, default: 35 },
      { name: "power_kw", label: "Мощность", type: "float", unit: "кВт", min: 500, max: 15000, default: 5000 },
    ],
  },

  // ===== Classification =====
  {
    type: "hydrocyclone",
    category: "classification",
    label: "Гидроциклон",
    description: "Классификация по крупности",
    icon: "🌀",
    color: CATEGORY_COLORS.classification,
    ports: [
      { id: "feed", name: "Питание", direction: "input", portType: "slurry", required: true },
      { id: "overflow", name: "Слив", direction: "output", portType: "slurry", required: true },
      { id: "underflow", name: "Пески", direction: "output", portType: "slurry", required: true },
    ],
    parameters: [
      { name: "d50_um", label: "d50", type: "float", unit: "мкм", min: 20, max: 500, default: 75 },
      { name: "sharpness", label: "Резкость", type: "float", min: 1, max: 5, default: 2.5 },
      { name: "pressure_kpa", label: "Давление", type: "float", unit: "кПа", min: 50, max: 200, default: 100 },
      { name: "num_cyclones", label: "Кол-во циклонов", type: "int", min: 1, max: 20, default: 4 },
    ],
  },
  {
    type: "vib_screen",
    category: "classification",
    label: "Вибрационный грохот",
    description: "Сухое грохочение",
    icon: "📊",
    color: CATEGORY_COLORS.classification,
    ports: [
      { id: "feed", name: "Питание", direction: "input", portType: "solid", required: true },
      { id: "oversize", name: "Надрешётный", direction: "output", portType: "solid", required: true },
      { id: "undersize", name: "Подрешётный", direction: "output", portType: "solid", required: true },
    ],
    parameters: [
      { name: "aperture_mm", label: "Размер ячейки", type: "float", unit: "мм", min: 0.5, max: 150, default: 25 },
      { name: "efficiency", label: "Эффективность", type: "float", unit: "%", min: 50, max: 99, default: 90 },
      { name: "area_m2", label: "Площадь", type: "float", unit: "м²", min: 1, max: 50, default: 10 },
    ],
  },
  {
    type: "banana_screen",
    category: "classification",
    label: "Банановый грохот",
    description: "Многозонный грохот переменного угла",
    icon: "🍌",
    color: CATEGORY_COLORS.classification,
    ports: [
      { id: "feed", name: "Питание", direction: "input", portType: "slurry", required: true },
      { id: "oversize", name: "Надрешётный", direction: "output", portType: "slurry", required: true },
      { id: "undersize", name: "Подрешётный", direction: "output", portType: "slurry", required: true },
    ],
    parameters: [
      { name: "aperture_mm", label: "Размер ячейки", type: "float", unit: "мм", min: 0.3, max: 50, default: 6 },
      { name: "num_panels", label: "Кол-во панелей", type: "int", min: 3, max: 7, default: 5 },
      { name: "area_m2", label: "Площадь", type: "float", unit: "м²", min: 5, max: 40, default: 20 },
    ],
  },

  // ===== Product =====
  {
    type: "product",
    category: "product",
    label: "Продукт",
    description: "Конечный поток",
    icon: "📤",
    color: CATEGORY_COLORS.product,
    ports: [
      { id: "in", name: "Вход", direction: "input", portType: "slurry", required: true },
    ],
    parameters: [],
  },
];

/**
 * Получить конфигурацию по типу оборудования
 */
export function getEquipmentConfig(type: string): EquipmentConfig | undefined {
  return EQUIPMENT_CONFIGS.find((c) => c.type === type);
}

/**
 * Получить оборудование по категории
 */
export function getEquipmentByCategory(category: NodeCategory): EquipmentConfig[] {
  return EQUIPMENT_CONFIGS.filter((c) => c.category === category);
}

/**
 * Все категории с названиями
 */
export const CATEGORY_LABELS: Record<NodeCategory, string> = {
  feed: "Питание",
  size_reduction: "Измельчение",
  classification: "Классификация",
  auxiliary: "Вспомогательное",
  product: "Продукт",
};
