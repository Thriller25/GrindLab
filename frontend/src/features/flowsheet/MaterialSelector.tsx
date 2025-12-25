/**
 * MaterialSelector — Dropdown для выбора материала на feed узле.
 *
 * F4.4: Назначение Material на feed
 */

import { useEffect, useState, useCallback } from "react";
import type { MaterialSummary } from "./types";

const API_BASE = "http://localhost:8000/api";

interface MaterialSelectorProps {
  /** Текущий выбранный материал ID */
  selectedMaterialId?: string;
  /** Callback при выборе материала */
  onSelect: (material: MaterialSummary | null) => void;
  /** Отключить селектор */
  disabled?: boolean;
}

/**
 * Компонент выбора материала
 */
export function MaterialSelector({
  selectedMaterialId,
  onSelect,
  disabled = false,
}: MaterialSelectorProps) {
  const [materials, setMaterials] = useState<MaterialSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  // Загрузка списка материалов
  useEffect(() => {
    const fetchMaterials = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(`${API_BASE}/materials`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        setMaterials(data.items || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load materials");
        setMaterials([]);
      } finally {
        setLoading(false);
      }
    };

    fetchMaterials();
  }, []);

  // Получить выбранный материал
  const selectedMaterial = materials.find((m) => m.id === selectedMaterialId);

  // Обработчик выбора
  const handleSelect = useCallback(
    (material: MaterialSummary | null) => {
      onSelect(material);
      setIsOpen(false);
    },
    [onSelect],
  );

  // Стили
  const containerStyle: React.CSSProperties = {
    position: "relative",
    width: "100%",
    minWidth: 160,
  };

  const buttonStyle: React.CSSProperties = {
    width: "100%",
    padding: "6px 10px",
    border: "1px solid #d1d5db",
    borderRadius: 6,
    background: disabled ? "#f3f4f6" : "#ffffff",
    cursor: disabled ? "not-allowed" : "pointer",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    fontSize: 12,
    color: selectedMaterial ? "#111827" : "#9ca3af",
  };

  const dropdownStyle: React.CSSProperties = {
    position: "absolute",
    top: "100%",
    left: 0,
    right: 0,
    marginTop: 4,
    background: "#ffffff",
    border: "1px solid #d1d5db",
    borderRadius: 6,
    boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
    zIndex: 1000,
    maxHeight: 200,
    overflowY: "auto",
  };

  const optionStyle = (isSelected: boolean): React.CSSProperties => ({
    padding: "8px 10px",
    cursor: "pointer",
    background: isSelected ? "#eff6ff" : "transparent",
    borderBottom: "1px solid #f3f4f6",
    transition: "background 0.15s",
  });

  if (loading) {
    return (
      <div style={containerStyle}>
        <div style={{ ...buttonStyle, color: "#9ca3af" }}>
          <span>Загрузка...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={containerStyle}>
        <div style={{ ...buttonStyle, borderColor: "#fca5a5", color: "#dc2626" }}>
          <span>Ошибка: {error}</span>
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <button
        type="button"
        style={buttonStyle}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
      >
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {selectedMaterial ? selectedMaterial.name : "Выберите материал..."}
        </span>
        <span style={{ marginLeft: 8, color: "#9ca3af" }}>{isOpen ? "▲" : "▼"}</span>
      </button>

      {isOpen && (
        <div style={dropdownStyle}>
          {/* Опция "Нет материала" */}
          <div
            style={optionStyle(!selectedMaterialId)}
            onClick={() => handleSelect(null)}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#f9fafb")}
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = !selectedMaterialId ? "#eff6ff" : "transparent")
            }
          >
            <div style={{ color: "#9ca3af", fontStyle: "italic" }}>— Без материала —</div>
          </div>

          {/* Список материалов */}
          {materials.map((mat) => (
            <div
              key={mat.id}
              style={optionStyle(mat.id === selectedMaterialId)}
              onClick={() => handleSelect(mat)}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f9fafb")}
              onMouseLeave={(e) =>
                (e.currentTarget.style.background =
                  mat.id === selectedMaterialId ? "#eff6ff" : "transparent")
              }
            >
              <div style={{ fontWeight: 500, color: "#111827" }}>{mat.name}</div>
              <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>
                {mat.source && <span>{mat.source}</span>}
                {mat.p80_mm && <span> • P80: {mat.p80_mm}мм</span>}
                {mat.solids_tph && <span> • {mat.solids_tph} т/ч</span>}
              </div>
            </div>
          ))}

          {materials.length === 0 && (
            <div style={{ padding: "12px 10px", color: "#9ca3af", textAlign: "center" }}>
              Нет доступных материалов
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default MaterialSelector;
