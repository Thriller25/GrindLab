"""
Material Import Parsers — парсеры для импорта материалов из различных форматов.

F3.1: Импорт Material из файла

Поддерживаемые форматы:
- CSV (простой, с метаданными, multi-sample)
- JSON (Material контракт, только PSD)
- Excel (TODO)

Версия: 1.0
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .psd import PSD, PSDInterpolation, PSDPoint

# ==================== Типы и константы ====================


class ImportFormat(str, Enum):
    """Форматы импорта."""

    CSV_SIMPLE = "csv_simple"  # size_mm,cum_passing
    CSV_META = "csv_meta"  # С комментариями-метаданными
    CSV_MULTI = "csv_multi"  # Несколько samples в одном файле
    CSV_RETAINED = "csv_retained"  # retained_pct вместо cum_passing
    CSV_TYLER = "csv_tyler"  # Tyler mesh
    JSON_MATERIAL = "json_material"  # Полный Material
    JSON_PSD = "json_psd"  # Только PSD
    EXCEL = "excel"  # Excel файл (TODO)


@dataclass
class ImportMetadata:
    """Метаданные, извлечённые из файла."""

    name: Optional[str] = None
    source: Optional[str] = None
    sample_id: Optional[str] = None
    sample_date: Optional[str] = None
    specific_gravity: Optional[float] = None
    moisture_pct: Optional[float] = None
    bond_wi: Optional[float] = None
    abrasion_index: Optional[float] = None
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class ImportResult:
    """Результат импорта."""

    success: bool
    psd: Optional[PSD] = None
    metadata: Optional[ImportMetadata] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    format_detected: Optional[ImportFormat] = None


@dataclass
class MultiImportResult:
    """Результат импорта нескольких материалов."""

    success: bool
    results: List[ImportResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ==================== Утилиты парсинга ====================

# Маппинг Tyler mesh → размер в мм
TYLER_MESH_TO_MM: Dict[int, float] = {
    3: 6.680,
    4: 4.750,
    5: 4.000,
    6: 3.350,
    7: 2.800,
    8: 2.360,
    9: 2.000,
    10: 1.700,
    12: 1.400,
    14: 1.180,
    16: 1.000,
    20: 0.850,
    24: 0.710,
    28: 0.600,
    32: 0.500,
    35: 0.425,
    42: 0.355,
    48: 0.300,
    60: 0.250,
    65: 0.212,
    80: 0.180,
    100: 0.150,
    115: 0.125,
    150: 0.106,
    170: 0.090,
    200: 0.075,
    250: 0.063,
    270: 0.053,
    325: 0.045,
    400: 0.038,
}


def tyler_mesh_to_mm(mesh: int) -> Optional[float]:
    """Конвертирует Tyler mesh в мм."""
    return TYLER_MESH_TO_MM.get(mesh)


def parse_metadata_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Парсит строку метаданных формата '# Key: Value'.

    Returns:
        (key, value) или (None, None) если не метаданные
    """
    line = line.strip()
    if not line.startswith("#"):
        return None, None

    line = line[1:].strip()  # Убираем #

    if ":" not in line:
        return None, None

    key, value = line.split(":", 1)
    return key.strip().lower().replace(" ", "_"), value.strip()


def normalize_column_name(name: str) -> str:
    """Нормализует имя колонки."""
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def detect_csv_format(
    headers: List[str], first_rows: List[List[str]], has_meta: bool
) -> ImportFormat:
    """Определяет формат CSV по заголовкам и данным."""
    norm_headers = [normalize_column_name(h) for h in headers]

    # Проверяем наличие sample_id (multi-sample)
    if "sample_id" in norm_headers or "sample_name" in norm_headers:
        return ImportFormat.CSV_MULTI

    # Проверяем Tyler mesh
    if "mesh" in norm_headers:
        return ImportFormat.CSV_TYLER

    # Проверяем retained
    if "retained_pct" in norm_headers or "retained" in norm_headers:
        return ImportFormat.CSV_RETAINED

    # С метаданными или простой
    if has_meta:
        return ImportFormat.CSV_META

    return ImportFormat.CSV_SIMPLE


# ==================== Парсеры CSV ====================


def parse_csv_simple(
    content: str,
    size_col: str = "size_mm",
    passing_col: str = "cum_passing",
) -> ImportResult:
    """
    Парсит простой CSV с двумя колонками: size_mm, cum_passing.

    Args:
        content: Содержимое CSV файла
        size_col: Имя колонки с размером
        passing_col: Имя колонки с cum_passing

    Returns:
        ImportResult
    """
    errors: List[str] = []
    warnings: List[str] = []
    metadata = ImportMetadata()

    # Разделяем на строки метаданных и данных
    lines = content.strip().split("\n")
    data_lines = []
    meta_lines = []

    for line in lines:
        if line.strip().startswith("#"):
            meta_lines.append(line)
        elif line.strip():
            data_lines.append(line)

    # Парсим метаданные
    for line in meta_lines:
        key, value = parse_metadata_line(line)
        if key and value:
            if key == "material" or key == "name":
                metadata.name = value
            elif key == "source":
                metadata.source = value
            elif key == "sample_id":
                metadata.sample_id = value
            elif key == "date":
                metadata.sample_date = value
            elif key == "specific_gravity" or key == "sg":
                try:
                    metadata.specific_gravity = float(value)
                except ValueError:
                    warnings.append(f"Invalid specific gravity: {value}")
            elif key == "moisture":
                try:
                    metadata.moisture_pct = float(value.replace("%", ""))
                except ValueError:
                    warnings.append(f"Invalid moisture: {value}")
            elif key == "bond_work_index" or key == "bond_wi":
                try:
                    metadata.bond_wi = float(value.split()[0])
                except ValueError:
                    warnings.append(f"Invalid Bond WI: {value}")
            elif key == "abrasion_index":
                try:
                    metadata.abrasion_index = float(value)
                except ValueError:
                    warnings.append(f"Invalid abrasion index: {value}")
            else:
                metadata.extra[key] = value

    if not data_lines:
        return ImportResult(
            success=False,
            errors=["No data rows found"],
            format_detected=ImportFormat.CSV_SIMPLE,
        )

    # Парсим CSV
    reader = csv.DictReader(data_lines)

    # Нормализуем имена колонок
    if reader.fieldnames is None:
        return ImportResult(
            success=False,
            errors=["No headers found"],
            format_detected=ImportFormat.CSV_SIMPLE,
        )

    field_map = {normalize_column_name(f): f for f in reader.fieldnames}

    # Находим нужные колонки
    size_field = field_map.get(normalize_column_name(size_col))
    passing_field = field_map.get(normalize_column_name(passing_col))

    if not size_field:
        return ImportResult(
            success=False,
            errors=[f"Column '{size_col}' not found. Available: {list(field_map.keys())}"],
            format_detected=ImportFormat.CSV_SIMPLE,
        )

    if not passing_field:
        return ImportResult(
            success=False,
            errors=[f"Column '{passing_col}' not found. Available: {list(field_map.keys())}"],
            format_detected=ImportFormat.CSV_SIMPLE,
        )

    # Парсим точки
    points: List[PSDPoint] = []
    for i, row in enumerate(reader, start=2):  # Начинаем с 2 (после заголовка)
        try:
            size = float(row[size_field])
            passing = float(row[passing_field])

            # Валидация
            if size <= 0:
                errors.append(f"Row {i}: size must be positive, got {size}")
                continue
            if passing < 0 or passing > 100:
                warnings.append(f"Row {i}: cum_passing {passing} out of range [0, 100]")
                passing = max(0, min(100, passing))

            points.append(PSDPoint(size_mm=size, cum_passing=passing))

        except (ValueError, KeyError) as e:
            errors.append(f"Row {i}: {e}")

    if len(points) < 4:
        return ImportResult(
            success=False,
            errors=errors + [f"Need at least 4 points, got {len(points)}"],
            warnings=warnings,
            format_detected=ImportFormat.CSV_META if meta_lines else ImportFormat.CSV_SIMPLE,
        )

    # Сортируем по размеру
    points.sort(key=lambda p: p.size_mm)

    # Создаём PSD
    try:
        psd = PSD(
            points=points,
            interpolation=PSDInterpolation.LOG_LINEAR,
            source=metadata.name or "CSV import",
        )
    except Exception as e:
        return ImportResult(
            success=False,
            errors=errors + [f"Failed to create PSD: {e}"],
            warnings=warnings,
            format_detected=ImportFormat.CSV_META if meta_lines else ImportFormat.CSV_SIMPLE,
        )

    return ImportResult(
        success=True,
        psd=psd,
        metadata=metadata,
        errors=errors,
        warnings=warnings,
        format_detected=ImportFormat.CSV_META if meta_lines else ImportFormat.CSV_SIMPLE,
    )


def parse_csv_retained(content: str) -> ImportResult:
    """
    Парсит CSV с retained_pct (конвертирует в cum_passing).

    Формат: size_mm, retained_pct[, cum_retained_pct]
    """
    errors: List[str] = []
    warnings: List[str] = []

    lines = content.strip().split("\n")
    data_lines = [line for line in lines if not line.strip().startswith("#") and line.strip()]

    if not data_lines:
        return ImportResult(
            success=False,
            errors=["No data rows found"],
            format_detected=ImportFormat.CSV_RETAINED,
        )

    reader = csv.DictReader(data_lines)

    if reader.fieldnames is None:
        return ImportResult(
            success=False,
            errors=["No headers found"],
            format_detected=ImportFormat.CSV_RETAINED,
        )

    field_map = {normalize_column_name(f): f for f in reader.fieldnames}

    size_field = field_map.get("size_mm")
    retained_field = field_map.get("retained_pct") or field_map.get("retained")
    cum_retained_field = field_map.get("cum_retained_pct") or field_map.get("cum_retained")

    if not size_field:
        return ImportResult(
            success=False,
            errors=["Column 'size_mm' not found"],
            format_detected=ImportFormat.CSV_RETAINED,
        )

    if not retained_field and not cum_retained_field:
        return ImportResult(
            success=False,
            errors=["Column 'retained_pct' or 'cum_retained_pct' not found"],
            format_detected=ImportFormat.CSV_RETAINED,
        )

    # Парсим данные
    sizes: List[float] = []
    cum_retained: List[float] = []

    for i, row in enumerate(reader, start=2):
        try:
            size = float(row[size_field])

            if cum_retained_field:
                cr = float(row[cum_retained_field])
            else:
                # Накапливаем retained
                ret = float(row[retained_field])
                cr = sum(cum_retained) + ret if cum_retained else ret

            sizes.append(size)
            cum_retained.append(cr)

        except (ValueError, KeyError) as e:
            errors.append(f"Row {i}: {e}")

    if len(sizes) < 4:
        return ImportResult(
            success=False,
            errors=errors + [f"Need at least 4 points, got {len(sizes)}"],
            format_detected=ImportFormat.CSV_RETAINED,
        )

    # Конвертируем cum_retained → cum_passing
    # cum_passing = 100 - cum_retained
    points = [PSDPoint(size_mm=s, cum_passing=100.0 - cr) for s, cr in zip(sizes, cum_retained)]
    points.sort(key=lambda p: p.size_mm)

    try:
        psd = PSD(
            points=points,
            interpolation=PSDInterpolation.LOG_LINEAR,
            source="CSV retained import",
        )
    except Exception as e:
        return ImportResult(
            success=False,
            errors=errors + [f"Failed to create PSD: {e}"],
            format_detected=ImportFormat.CSV_RETAINED,
        )

    return ImportResult(
        success=True,
        psd=psd,
        metadata=ImportMetadata(),
        errors=errors,
        warnings=warnings,
        format_detected=ImportFormat.CSV_RETAINED,
    )


def parse_csv_tyler(content: str) -> ImportResult:
    """
    Парсит CSV с Tyler mesh (конвертирует в мм).

    Формат: mesh, cum_passing[, size_mm]
    """
    errors: List[str] = []
    warnings: List[str] = []

    lines = content.strip().split("\n")
    data_lines = [line for line in lines if not line.strip().startswith("#") and line.strip()]

    if not data_lines:
        return ImportResult(
            success=False,
            errors=["No data rows found"],
            format_detected=ImportFormat.CSV_TYLER,
        )

    reader = csv.DictReader(data_lines)

    if reader.fieldnames is None:
        return ImportResult(
            success=False,
            errors=["No headers found"],
            format_detected=ImportFormat.CSV_TYLER,
        )

    field_map = {normalize_column_name(f): f for f in reader.fieldnames}

    mesh_field = field_map.get("mesh")
    passing_field = field_map.get("cum_passing") or field_map.get("passing")
    size_field = field_map.get("size_mm")  # Опционально

    if not mesh_field:
        return ImportResult(
            success=False,
            errors=["Column 'mesh' not found"],
            format_detected=ImportFormat.CSV_TYLER,
        )

    if not passing_field:
        return ImportResult(
            success=False,
            errors=["Column 'cum_passing' not found"],
            format_detected=ImportFormat.CSV_TYLER,
        )

    points: List[PSDPoint] = []
    for i, row in enumerate(reader, start=2):
        try:
            mesh = int(row[mesh_field])
            passing = float(row[passing_field])

            # Получаем размер в мм
            if size_field and row.get(size_field):
                size = float(row[size_field])
            else:
                size = tyler_mesh_to_mm(mesh)
                if size is None:
                    warnings.append(f"Row {i}: Unknown Tyler mesh {mesh}, skipping")
                    continue

            points.append(PSDPoint(size_mm=size, cum_passing=passing))

        except (ValueError, KeyError) as e:
            errors.append(f"Row {i}: {e}")

    if len(points) < 4:
        return ImportResult(
            success=False,
            errors=errors + [f"Need at least 4 points, got {len(points)}"],
            format_detected=ImportFormat.CSV_TYLER,
        )

    points.sort(key=lambda p: p.size_mm)

    try:
        psd = PSD(
            points=points,
            interpolation=PSDInterpolation.LOG_LINEAR,
            source="CSV Tyler mesh import",
        )
    except Exception as e:
        return ImportResult(
            success=False,
            errors=errors + [f"Failed to create PSD: {e}"],
            format_detected=ImportFormat.CSV_TYLER,
        )

    return ImportResult(
        success=True,
        psd=psd,
        metadata=ImportMetadata(),
        errors=errors,
        warnings=warnings,
        format_detected=ImportFormat.CSV_TYLER,
    )


def parse_csv_multi(content: str) -> MultiImportResult:
    """
    Парсит CSV с несколькими samples.

    Формат: sample_id, sample_name, size_mm, cum_passing
    """
    errors: List[str] = []
    results: List[ImportResult] = []

    lines = content.strip().split("\n")
    data_lines = [line for line in lines if not line.strip().startswith("#") and line.strip()]

    if not data_lines:
        return MultiImportResult(
            success=False,
            errors=["No data rows found"],
        )

    reader = csv.DictReader(data_lines)

    if reader.fieldnames is None:
        return MultiImportResult(
            success=False,
            errors=["No headers found"],
        )

    field_map = {normalize_column_name(f): f for f in reader.fieldnames}

    sample_id_field = field_map.get("sample_id")
    sample_name_field = field_map.get("sample_name")
    size_field = field_map.get("size_mm")
    passing_field = field_map.get("cum_passing")

    if not size_field or not passing_field:
        return MultiImportResult(
            success=False,
            errors=["Required columns 'size_mm' and 'cum_passing' not found"],
        )

    # Группируем по sample_id
    samples: Dict[str, List[Tuple[float, float]]] = {}
    sample_names: Dict[str, str] = {}

    for i, row in enumerate(reader, start=2):
        try:
            sample_id = (
                row.get(sample_id_field, f"sample_{i}") if sample_id_field else f"sample_{i}"
            )
            sample_name = row.get(sample_name_field, sample_id) if sample_name_field else sample_id
            size = float(row[size_field])
            passing = float(row[passing_field])

            if sample_id not in samples:
                samples[sample_id] = []
                sample_names[sample_id] = sample_name

            samples[sample_id].append((size, passing))

        except (ValueError, KeyError) as e:
            errors.append(f"Row {i}: {e}")

    # Создаём PSD для каждого sample
    for sample_id, data in samples.items():
        if len(data) < 4:
            results.append(
                ImportResult(
                    success=False,
                    errors=[f"Sample {sample_id}: need at least 4 points, got {len(data)}"],
                    format_detected=ImportFormat.CSV_MULTI,
                )
            )
            continue

        points = [PSDPoint(size_mm=s, cum_passing=p) for s, p in data]
        points.sort(key=lambda p: p.size_mm)

        try:
            psd = PSD(
                points=points,
                interpolation=PSDInterpolation.LOG_LINEAR,
                source=f"CSV multi import: {sample_names[sample_id]}",
            )
            results.append(
                ImportResult(
                    success=True,
                    psd=psd,
                    metadata=ImportMetadata(
                        name=sample_names[sample_id],
                        sample_id=sample_id,
                    ),
                    format_detected=ImportFormat.CSV_MULTI,
                )
            )
        except Exception as e:
            results.append(
                ImportResult(
                    success=False,
                    errors=[f"Sample {sample_id}: {e}"],
                    format_detected=ImportFormat.CSV_MULTI,
                )
            )

    return MultiImportResult(
        success=all(r.success for r in results) and len(results) > 0,
        results=results,
        errors=errors,
    )


# ==================== Парсеры JSON ====================


def parse_json_psd(content: str) -> ImportResult:
    """
    Парсит JSON с PSD данными.

    Формат:
    {
        "name": "...",
        "interpolation": "log_linear",
        "points": [{"size_mm": ..., "cum_passing": ...}, ...]
    }
    """
    errors: List[str] = []
    warnings: List[str] = []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return ImportResult(
            success=False,
            errors=[f"Invalid JSON: {e}"],
            format_detected=ImportFormat.JSON_PSD,
        )

    # Извлекаем points
    points_data = data.get("points", [])

    if not points_data:
        return ImportResult(
            success=False,
            errors=["No 'points' array found"],
            format_detected=ImportFormat.JSON_PSD,
        )

    points: List[PSDPoint] = []
    for i, pt in enumerate(points_data):
        try:
            size = float(pt.get("size_mm", pt.get("size", 0)))
            passing = float(pt.get("cum_passing", pt.get("passing", 0)))

            if size <= 0:
                errors.append(f"Point {i}: invalid size {size}")
                continue

            points.append(PSDPoint(size_mm=size, cum_passing=passing))
        except (TypeError, ValueError) as e:
            errors.append(f"Point {i}: {e}")

    if len(points) < 4:
        return ImportResult(
            success=False,
            errors=errors + [f"Need at least 4 points, got {len(points)}"],
            format_detected=ImportFormat.JSON_PSD,
        )

    points.sort(key=lambda p: p.size_mm)

    # Определяем интерполяцию
    interp_str = data.get("interpolation", "log_linear")
    try:
        interpolation = PSDInterpolation(interp_str)
    except ValueError:
        warnings.append(f"Unknown interpolation '{interp_str}', using log_linear")
        interpolation = PSDInterpolation.LOG_LINEAR

    try:
        psd = PSD(
            points=points,
            interpolation=interpolation,
            source=data.get("source", data.get("name", "JSON import")),
        )
    except Exception as e:
        return ImportResult(
            success=False,
            errors=errors + [f"Failed to create PSD: {e}"],
            format_detected=ImportFormat.JSON_PSD,
        )

    metadata = ImportMetadata(
        name=data.get("name"),
        source=data.get("source"),
    )

    return ImportResult(
        success=True,
        psd=psd,
        metadata=metadata,
        errors=errors,
        warnings=warnings,
        format_detected=ImportFormat.JSON_PSD,
    )


def parse_json_material(content: str) -> ImportResult:
    """
    Парсит полный Material JSON.

    Формат соответствует Material контракту из data_contracts.
    """
    errors: List[str] = []
    warnings: List[str] = []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return ImportResult(
            success=False,
            errors=[f"Invalid JSON: {e}"],
            format_detected=ImportFormat.JSON_MATERIAL,
        )

    # Извлекаем PSD
    psd_data = data.get("psd")
    if not psd_data:
        return ImportResult(
            success=False,
            errors=["No 'psd' object found"],
            format_detected=ImportFormat.JSON_MATERIAL,
        )

    # Парсим PSD
    psd_result = parse_json_psd(json.dumps(psd_data))
    if not psd_result.success:
        return ImportResult(
            success=False,
            errors=psd_result.errors,
            warnings=psd_result.warnings,
            format_detected=ImportFormat.JSON_MATERIAL,
        )

    # Извлекаем метаданные
    source_data = data.get("source", {})
    props_data = data.get("properties", {})

    metadata = ImportMetadata(
        name=data.get("name"),
        source=source_data.get("location"),
        sample_id=source_data.get("sample_id"),
        sample_date=source_data.get("sample_date"),
        specific_gravity=props_data.get("specific_gravity"),
        moisture_pct=props_data.get("moisture_pct"),
        bond_wi=props_data.get("bond_work_index_kwh_t"),
        abrasion_index=props_data.get("abrasion_index"),
    )

    return ImportResult(
        success=True,
        psd=psd_result.psd,
        metadata=metadata,
        errors=errors,
        warnings=warnings + psd_result.warnings,
        format_detected=ImportFormat.JSON_MATERIAL,
    )


# ==================== Главная функция импорта ====================


def import_psd(
    content: Union[str, bytes],
    format_hint: Optional[ImportFormat] = None,
    filename: Optional[str] = None,
) -> Union[ImportResult, MultiImportResult]:
    """
    Универсальная функция импорта PSD.

    Автоматически определяет формат по содержимому или подсказке.

    Args:
        content: Содержимое файла (строка или bytes)
        format_hint: Подсказка формата (опционально)
        filename: Имя файла для определения формата (опционально)

    Returns:
        ImportResult или MultiImportResult для multi-sample файлов
    """
    # Конвертируем bytes в str
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    content = content.strip()

    # Определяем формат
    if format_hint:
        fmt = format_hint
    elif filename:
        ext = Path(filename).suffix.lower()
        if ext == ".json":
            # Определяем тип JSON
            try:
                data = json.loads(content)
                if "psd" in data and "properties" in data:
                    fmt = ImportFormat.JSON_MATERIAL
                else:
                    fmt = ImportFormat.JSON_PSD
            except json.JSONDecodeError:
                return ImportResult(
                    success=False,
                    errors=["Invalid JSON file"],
                )
        elif ext in (".csv", ".txt"):
            # Определяем тип CSV
            fmt = _detect_csv_format_from_content(content)
        elif ext in (".xlsx", ".xls"):
            return ImportResult(
                success=False,
                errors=["Excel format not yet supported"],
                format_detected=ImportFormat.EXCEL,
            )
        else:
            return ImportResult(
                success=False,
                errors=[f"Unknown file extension: {ext}"],
            )
    else:
        # Автоопределение по содержимому
        if content.startswith("{") or content.startswith("["):
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "psd" in data:
                    fmt = ImportFormat.JSON_MATERIAL
                else:
                    fmt = ImportFormat.JSON_PSD
            except json.JSONDecodeError:
                return ImportResult(
                    success=False,
                    errors=["Content looks like JSON but is invalid"],
                )
        else:
            fmt = _detect_csv_format_from_content(content)

    # Вызываем соответствующий парсер
    if fmt == ImportFormat.CSV_SIMPLE or fmt == ImportFormat.CSV_META:
        return parse_csv_simple(content)
    elif fmt == ImportFormat.CSV_RETAINED:
        return parse_csv_retained(content)
    elif fmt == ImportFormat.CSV_TYLER:
        return parse_csv_tyler(content)
    elif fmt == ImportFormat.CSV_MULTI:
        return parse_csv_multi(content)
    elif fmt == ImportFormat.JSON_PSD:
        return parse_json_psd(content)
    elif fmt == ImportFormat.JSON_MATERIAL:
        return parse_json_material(content)
    else:
        return ImportResult(
            success=False,
            errors=[f"Unsupported format: {fmt}"],
        )


def _detect_csv_format_from_content(content: str) -> ImportFormat:
    """Определяет формат CSV по содержимому."""
    lines = content.strip().split("\n")

    has_meta = any(line.strip().startswith("#") for line in lines)
    data_lines = [line for line in lines if not line.strip().startswith("#") and line.strip()]

    if not data_lines:
        return ImportFormat.CSV_SIMPLE

    # Парсим заголовок
    headers = data_lines[0].split(",")
    norm_headers = [normalize_column_name(h) for h in headers]

    if "sample_id" in norm_headers or "sample_name" in norm_headers:
        return ImportFormat.CSV_MULTI
    if "mesh" in norm_headers:
        return ImportFormat.CSV_TYLER
    if (
        "retained_pct" in norm_headers
        or "retained" in norm_headers
        or "cum_retained_pct" in norm_headers
    ):
        return ImportFormat.CSV_RETAINED
    if has_meta:
        return ImportFormat.CSV_META

    return ImportFormat.CSV_SIMPLE


# ==================== Экспорт ====================

__all__ = [
    # Types
    "ImportFormat",
    "ImportMetadata",
    "ImportResult",
    "MultiImportResult",
    # Parsers
    "parse_csv_simple",
    "parse_csv_retained",
    "parse_csv_tyler",
    "parse_csv_multi",
    "parse_json_psd",
    "parse_json_material",
    # Main function
    "import_psd",
    # Utils
    "tyler_mesh_to_mm",
    "TYLER_MESH_TO_MM",
]
