# Data Contracts — F0.2

Версионируемые JSON-схемы для обмена данными между модулями GrindLab.

## Обзор

Data Contracts определяют стандартные структуры данных для:
- **PSD** — гранулометрический состав (Particle Size Distribution)
- **Material** — материал в технологическом потоке
- **Stream** — поток между узлами схемы
- **KPI** — ключевые показатели эффективности
- **Blast** — взрывной блок (партия руды)

## Расположение

```
backend/app/schemas/contracts/
├── __init__.py      # Экспорт всех контрактов
├── psd.py           # PSD, PSDPoint, PSDQuantiles
├── material.py      # Material, MaterialQuality
├── stream.py        # Stream, StreamType
├── kpi.py           # KPI, KPICollection
└── blast.py         # Blast, BlastBlock
```

## Использование

```python
from app.schemas.contracts import (
    PSD,
    Material,
    MaterialPhase,
    MaterialQuality,
    Stream,
    StreamType,
    KPI,
    KPICollection,
    throughput_kpi,
    Blast,
)
```

---

## PSD (Particle Size Distribution)

Гранулометрический состав — центральный контракт для представления распределения частиц по размерам.

### Создание PSD

```python
# Из списка точек
psd = PSD(
    points=[
        PSDPoint(size_mm=0.075, cum_passing=15.0),
        PSDPoint(size_mm=0.150, cum_passing=35.0),
        PSDPoint(size_mm=0.300, cum_passing=55.0),
        PSDPoint(size_mm=0.600, cum_passing=75.0),
        PSDPoint(size_mm=1.180, cum_passing=90.0),
    ]
)

# Из двух списков (удобно для импорта)
psd = PSD.from_cumulative(
    sizes_mm=[0.075, 0.150, 0.300, 0.600, 1.180],
    cum_passing=[15, 35, 55, 75, 90]
)
```

### Квантили (P-значения)

```python
# P80 — размер, через который проходит 80% материала
p80 = psd.p80          # Свойство
p80 = psd.get_pxx(80)  # Метод

# Все стандартные квантили
quantiles = psd.compute_quantiles()
# PSDQuantiles(p10=..., p20=..., p50=..., p80=..., p90=..., p95=..., p100=...)
```

### Интерполяция

Поддерживаются методы:
- `LINEAR` — линейная интерполяция
- `LOG_LINEAR` — логарифмическая по размеру (по умолчанию, стандарт для PSD)
- `SPLINE` — сплайн (требует scipy)

```python
psd = PSD(
    points=[...],
    interpolation=PSDInterpolation.LOG_LINEAR
)
```

---

## Material

Материал в технологическом потоке с полным набором характеристик.

### Создание материала

```python
# Сухой материал
material = Material(
    name="SAG Feed",
    phase=MaterialPhase.SOLID,
    solids_tph=1500.0,
)

# Пульпа с явной водой
slurry = Material(
    name="Ball Mill Discharge",
    phase=MaterialPhase.SLURRY,
    solids_tph=1000.0,
    water_tph=500.0,  # Ж:Т = 0.5
)

# Пульпа через % твёрдого
slurry = Material(
    phase=MaterialPhase.SLURRY,
    solids_tph=1000.0,
    solids_percent=66.7,  # Вода вычисляется автоматически
)
```

### Качество материала

```python
quality = MaterialQuality(
    chemistry={"Cu": 0.5, "Fe": 15.0, "S": 2.0},
    bond_work_index_kwh_t=14.5,
    sg=2.7,
    moisture_percent=3.0,
)

material = Material(
    solids_tph=1500.0,
    quality=quality,
    psd=psd,
)
```

### Методы

```python
# Добавить PSD (immutable)
material_with_psd = material.with_psd(psd)

# Смешать два материала
blended = material.blend_with(other_material, other_fraction=0.3)

# Вычисляемые свойства
material.total_tph         # solids + water
material.water_solids_ratio  # Ж:Т
material.p80_mm            # P80 из PSD
```

---

## Stream

Поток между двумя узлами технологической схемы.

```python
stream = Stream(
    name="SAG Discharge",
    stream_type=StreamType.SLURRY,
    source_node_id=sag_mill_id,
    source_port="out",
    target_node_id=screen_id,
    target_port="in",
    material=material,
)

# Свойства потока
stream.solids_tph
stream.total_tph
stream.p80_mm

# Обновление материала (immutable)
calculated_stream = stream.with_material(new_material)
```

### Типы потоков

```python
class StreamType(str, Enum):
    SOLIDS = "solids"      # Сухой материал
    SLURRY = "slurry"      # Пульпа
    WATER = "water"        # Вода
    OVERFLOW = "overflow"  # Слив классификатора
    UNDERFLOW = "underflow"  # Пески
    FEED = "feed"
    PRODUCT = "product"
    RECYCLE = "recycle"    # Циркулирующая нагрузка
```

---

## KPI

Ключевые показатели эффективности с поддержкой статусов и сравнения.

### Создание KPI

```python
# Явное создание
kpi = KPI(
    key="specific_energy",
    name="Удельный расход энергии",
    value=12.5,
    unit="kWh/t",
    kpi_type=KPIType.ENERGY,
    target_value=11.0,
    target_max=13.0,
)

# Хелперы для стандартных KPI
from app.schemas.contracts import (
    throughput_kpi,
    specific_energy_kpi,
    p80_kpi,
    circulating_load_kpi,
)

kpi = throughput_kpi(1500.0, target_value=1400.0)
```

### Статусы

```python
kpi.status  # KPIStatus.OK / WARNING / CRITICAL / UNKNOWN

# Автоматический расчёт:
# - CRITICAL: value < target_min или value > target_max
# - WARNING: отклонение от target_value > warning_threshold_percent
# - OK: в пределах
# - UNKNOWN: нет целевых значений
```

### Сравнение с базовой линией

```python
kpi = kpi.with_baseline(baseline_value=10.0)
kpi.delta_from_baseline  # Абсолютная разница
kpi.delta_percent        # Процентное изменение
```

### Коллекция KPI

```python
collection = KPICollection(
    source_id=calc_run_id,
    kpis=[
        throughput_kpi(1500),
        specific_energy_kpi(12.5),
        p80_kpi(0.075),
    ]
)

# Доступ по ключу
collection["throughput"]  # 1500.0
collection.get("throughput")  # Полный KPI объект

# Фильтрация
collection.filter_by_type(KPIType.ENERGY)
collection.filter_by_status(KPIStatus.WARNING)

# Проверки
collection.has_critical
collection.has_warnings

# Сравнение с baseline
compared = current_collection.compare_with(baseline_collection)
```

---

## Blast

Взрывной блок — партия руды с прослеживаемостью от карьера.

```python
blast = Blast(
    blast_id="BL-2024-001",
    name="Zone A, 2024-01-15",
    total_tonnage_t=50000.0,
    psd=psd,
    quality=MaterialQuality(
        chemistry={"Cu": 0.55, "Fe": 14.0},
        bond_work_index_kwh_t=14.2,
        sg=2.75,
    ),
    status=BlastStatus.BLASTED,
)
```

### Прослеживаемость

```python
# Потребление тоннажа
blast = blast.consume(10000.0)  # Остаток: 40000 т
# Статус автоматически → PROCESSING

# Полное потребление
blast = blast.consume(50000.0)
# Статус → COMPLETED
```

### Блендинг

```python
merged = blast1.merge_with(blast2)
# Объединённый тоннаж
# Средневзвешенное качество
# metadata с информацией об источниках
```

### Конвертация в Material

```python
# Для использования в расчёте
material = blast.to_material(rate_tph=1500.0)
# material.source_blast_id = "BL-2024-001"
```

---

## Версионирование

Каждый контракт содержит поле `contract_version`:

```python
psd.contract_version      # "1.0"
material.contract_version # "1.0"
kpi.contract_version      # "1.0"
blast.contract_version    # "1.0"
```

При изменении структуры контракта версия увеличивается, что позволяет обрабатывать данные разных версий.

---

## Тесты

```bash
# Запуск тестов Data Contracts
cd backend
pytest tests/test_data_contracts.py -v

# 45 тестов покрывают все контракты
```

---

## Связь с другими модулями

| Контракт | Используется в |
|----------|----------------|
| PSD | Material, Blast, GrindMvpResult |
| Material | Stream, Node inputs/outputs |
| Stream | Flowsheet topology |
| KPI | CalcRun results, Dashboard |
| Blast | Ore tracking, Feed planning |

---

## Будущие расширения

- **F3.1** Materials Import — загрузка PSD и Material из файлов
- **F4.2** Node Library — Node использует Stream для входов/выходов
- **F5.1** Solver — оперирует Material и Stream для расчётов
- **F10.x** INKA Integration — Blast.source = BlastSource.INKA
