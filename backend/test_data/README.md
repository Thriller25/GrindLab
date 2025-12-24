# Test Data for Material Import

Тестовые данные для проверки импорта материалов.

## Структура

### CSV Files

| Файл | Описание |
|------|----------|
| `ore_feed_simple.csv` | Простой формат: размер, cum_passing |
| `ore_feed_with_meta.csv` | С метаданными в заголовке |
| `ball_mill_products.csv` | Несколько материалов в одном файле |
| `sieve_analysis_retained.csv` | Формат "задержано на сите" |
| `psd_tyler_mesh.csv` | Размеры в Tyler mesh |

### Excel Files (TODO)

| Файл | Описание |
|------|----------|
| `lab_report_template.xlsx` | Типичный лабораторный отчёт |
| `multi_sample_report.xlsx` | Несколько проб на разных листах |

### JSON Files

| Файл | Описание |
|------|----------|
| `material_full.json` | Полный Material контракт |
| `psd_only.json` | Только PSD данные |

## Форматы данных

### Simple CSV (ore_feed_simple.csv)
```csv
size_mm,cum_passing
25.4,100.0
19.0,95.2
...
```

### CSV with Metadata (ore_feed_with_meta.csv)
```csv
# Material: SAG Mill Feed
# Source: Primary Crusher Product
# Date: 2024-01-15
# SG: 2.85
# Moisture: 4.5%
size_mm,cum_passing
...
```

### Retained Format (sieve_analysis_retained.csv)
```csv
size_mm,retained_pct
25.4,0.0
19.0,4.8
...
```

### Tyler Mesh Format (psd_tyler_mesh.csv)
```csv
mesh,cum_passing
4,100.0
6,95.2
...
```

## Реалистичные данные

Данные основаны на типичных характеристиках:
- **SAG Mill Feed**: P80 = 100-150 мм, F80 = 150-200 мм
- **Ball Mill Feed**: P80 = 2-4 мм
- **Cyclone Overflow**: P80 = 75-150 μm
- **Flotation Feed**: P80 = 50-100 μm
