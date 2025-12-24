"""
Materials Import Router — API для импорта материалов из файлов.

F3.1: Импорт Material из файла

Эндпоинты:
- POST /api/materials/import/psd — импорт PSD из файла
- POST /api/materials/import/psd/preview — предпросмотр импорта
- GET /api/materials/import/formats — список поддерживаемых форматов
"""

from typing import List, Optional

from app.schemas.contracts import (
    ImportFormat,
    ImportMetadata,
    ImportResult,
    MultiImportResult,
    import_psd,
)
from app.schemas.contracts.psd import PSD
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/materials/import", tags=["materials", "import"])


# ==================== Response Models ====================


class PSDPointResponse(BaseModel):
    """Точка PSD для ответа API."""

    size_mm: float
    cum_passing: float


class PSDResponse(BaseModel):
    """PSD для ответа API."""

    points: List[PSDPointResponse]
    interpolation: str
    source: Optional[str] = None
    p50: Optional[float] = None
    p80: Optional[float] = None


class ImportMetadataResponse(BaseModel):
    """Метаданные импорта для ответа API."""

    name: Optional[str] = None
    source: Optional[str] = None
    sample_id: Optional[str] = None
    sample_date: Optional[str] = None
    specific_gravity: Optional[float] = None
    moisture_pct: Optional[float] = None
    bond_wi: Optional[float] = None
    abrasion_index: Optional[float] = None


class ImportPreviewResponse(BaseModel):
    """Предпросмотр импорта."""

    success: bool
    format_detected: Optional[str] = None
    psd: Optional[PSDResponse] = None
    metadata: Optional[ImportMetadataResponse] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class MultiImportPreviewResponse(BaseModel):
    """Предпросмотр мульти-импорта."""

    success: bool
    count: int = 0
    results: List[ImportPreviewResponse] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class FormatInfo(BaseModel):
    """Информация о формате импорта."""

    format: str
    name: str
    description: str
    extensions: List[str]
    example: str


class FormatsResponse(BaseModel):
    """Список поддерживаемых форматов."""

    formats: List[FormatInfo]


# ==================== Helper Functions ====================


def psd_to_response(psd: PSD) -> PSDResponse:
    """Конвертирует PSD в response модель."""
    return PSDResponse(
        points=[PSDPointResponse(size_mm=p.size_mm, cum_passing=p.cum_passing) for p in psd.points],
        interpolation=psd.interpolation.value,
        source=psd.source,
        p50=psd.get_pxx(50),
        p80=psd.p80,
    )


def metadata_to_response(meta: ImportMetadata) -> ImportMetadataResponse:
    """Конвертирует ImportMetadata в response модель."""
    return ImportMetadataResponse(
        name=meta.name,
        source=meta.source,
        sample_id=meta.sample_id,
        sample_date=meta.sample_date,
        specific_gravity=meta.specific_gravity,
        moisture_pct=meta.moisture_pct,
        bond_wi=meta.bond_wi,
        abrasion_index=meta.abrasion_index,
    )


def result_to_preview(result: ImportResult) -> ImportPreviewResponse:
    """Конвертирует ImportResult в preview response."""
    return ImportPreviewResponse(
        success=result.success,
        format_detected=result.format_detected.value if result.format_detected else None,
        psd=psd_to_response(result.psd) if result.psd else None,
        metadata=metadata_to_response(result.metadata) if result.metadata else None,
        errors=result.errors,
        warnings=result.warnings,
    )


# ==================== Endpoints ====================


@router.get("/formats", response_model=FormatsResponse)
def get_supported_formats():
    """
    Получить список поддерживаемых форматов импорта.

    Возвращает информацию о каждом формате: название, описание,
    расширения файлов и пример содержимого.
    """
    formats = [
        FormatInfo(
            format=ImportFormat.CSV_SIMPLE.value,
            name="CSV Simple",
            description="Простой CSV с двумя колонками: size_mm и cum_passing",
            extensions=[".csv", ".txt"],
            example="size_mm,cum_passing\n6.35,100.0\n4.75,92.5\n...",
        ),
        FormatInfo(
            format=ImportFormat.CSV_META.value,
            name="CSV with Metadata",
            description="CSV с метаданными в комментариях (# Material: ..., # SG: ...)",
            extensions=[".csv", ".txt"],
            example="# Material: SAG Mill Feed\n# SG: 2.85\nsize_mm,cum_passing\n...",
        ),
        FormatInfo(
            format=ImportFormat.CSV_RETAINED.value,
            name="CSV Retained",
            description="CSV с retained_pct вместо cum_passing",
            extensions=[".csv", ".txt"],
            example="size_mm,retained_pct\n6.0,0.0\n4.75,5.0\n...",
        ),
        FormatInfo(
            format=ImportFormat.CSV_TYLER.value,
            name="CSV Tyler Mesh",
            description="CSV с Tyler mesh номерами (конвертируются в мм)",
            extensions=[".csv", ".txt"],
            example="mesh,cum_passing\n4,100.0\n6,95.0\n...",
        ),
        FormatInfo(
            format=ImportFormat.CSV_MULTI.value,
            name="CSV Multi-Sample",
            description="CSV с несколькими samples (sample_id, size_mm, cum_passing)",
            extensions=[".csv", ".txt"],
            example="sample_id,sample_name,size_mm,cum_passing\nS1,Sample 1,6.0,100.0\n...",
        ),
        FormatInfo(
            format=ImportFormat.JSON_PSD.value,
            name="JSON PSD",
            description="JSON только с PSD данными",
            extensions=[".json"],
            example='{"points": [{"size_mm": 6.0, "cum_passing": 100.0}, ...]}',
        ),
        FormatInfo(
            format=ImportFormat.JSON_MATERIAL.value,
            name="JSON Material",
            description="Полный JSON Material с PSD, свойствами и метаданными",
            extensions=[".json"],
            example='{"name": "...", "psd": {...}, "properties": {...}}',
        ),
    ]

    return FormatsResponse(formats=formats)


@router.post("/psd/preview", response_model=ImportPreviewResponse | MultiImportPreviewResponse)
async def preview_psd_import(
    file: UploadFile = File(..., description="Файл для импорта (CSV или JSON)"),
    format_hint: Optional[str] = Form(None, description="Подсказка формата (опционально)"),
):
    """
    Предпросмотр импорта PSD из файла.

    Парсит файл и возвращает результат без сохранения в базу.
    Используйте для проверки данных перед фактическим импортом.

    **Поддерживаемые форматы:**
    - CSV: simple, with metadata, retained, tyler mesh, multi-sample
    - JSON: psd-only, full material

    **Параметры:**
    - **file**: Файл для импорта
    - **format_hint**: Опциональная подсказка формата (csv_simple, json_psd, etc.)
    """
    # Читаем содержимое файла
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File encoding error. Please use UTF-8 encoded files.",
        )

    # Парсим format_hint
    fmt_hint = None
    if format_hint:
        try:
            fmt_hint = ImportFormat(format_hint)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown format: {format_hint}. Use GET /formats to see available formats.",
            )

    # Импортируем
    result = import_psd(content_str, format_hint=fmt_hint, filename=file.filename)

    # Возвращаем результат
    if isinstance(result, MultiImportResult):
        return MultiImportPreviewResponse(
            success=result.success,
            count=len(result.results),
            results=[result_to_preview(r) for r in result.results],
            errors=result.errors,
        )
    else:
        return result_to_preview(result)


@router.post("/psd", response_model=ImportPreviewResponse | MultiImportPreviewResponse)
async def import_psd_file(
    file: UploadFile = File(..., description="Файл для импорта (CSV или JSON)"),
    format_hint: Optional[str] = Form(None, description="Подсказка формата (опционально)"),
    name: Optional[str] = Form(None, description="Имя материала (переопределяет из файла)"),
):
    """
    Импорт PSD из файла.

    Парсит файл и возвращает PSD данные. В будущих версиях
    будет сохранять в базу данных.

    **Поддерживаемые форматы:**
    - CSV: simple, with metadata, retained, tyler mesh, multi-sample
    - JSON: psd-only, full material

    **Параметры:**
    - **file**: Файл для импорта
    - **format_hint**: Опциональная подсказка формата
    - **name**: Имя материала (опционально, переопределяет из файла)
    """
    # Читаем содержимое файла
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File encoding error. Please use UTF-8 encoded files.",
        )

    # Парсим format_hint
    fmt_hint = None
    if format_hint:
        try:
            fmt_hint = ImportFormat(format_hint)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown format: {format_hint}",
            )

    # Импортируем
    result = import_psd(content_str, format_hint=fmt_hint, filename=file.filename)

    # Проверяем успешность
    if isinstance(result, MultiImportResult):
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Import failed", "errors": result.errors},
            )
        # Переопределяем имя если задано
        if name:
            for r in result.results:
                if r.metadata:
                    r.metadata.name = name
        return MultiImportPreviewResponse(
            success=result.success,
            count=len(result.results),
            results=[result_to_preview(r) for r in result.results],
            errors=result.errors,
        )
    else:
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Import failed", "errors": result.errors},
            )
        # Переопределяем имя если задано
        if name and result.metadata:
            result.metadata.name = name
        return result_to_preview(result)


@router.post("/psd/validate")
async def validate_psd_file(
    file: UploadFile = File(..., description="Файл для валидации"),
):
    """
    Валидация файла PSD без импорта.

    Проверяет формат, структуру и значения данных.
    Возвращает список ошибок и предупреждений.

    **Возвращает:**
    - valid: bool — файл валиден
    - format_detected: str — определённый формат
    - errors: list — критические ошибки
    - warnings: list — предупреждения
    - stats: dict — статистика (количество точек, диапазон размеров, etc.)
    """
    # Читаем содержимое файла
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "valid": False,
            "format_detected": None,
            "errors": ["File encoding error. Please use UTF-8 encoded files."],
            "warnings": [],
            "stats": None,
        }

    # Импортируем для валидации
    result = import_psd(content_str, filename=file.filename)

    if isinstance(result, MultiImportResult):
        all_errors = result.errors + [e for r in result.results for e in r.errors]
        all_warnings = [w for r in result.results for w in r.warnings]

        stats = None
        if result.success and result.results:
            stats = {
                "sample_count": len(result.results),
                "samples": [
                    {
                        "name": r.metadata.name if r.metadata else None,
                        "points_count": len(r.psd.points) if r.psd else 0,
                        "size_range_mm": (
                            [r.psd.points[0].size_mm, r.psd.points[-1].size_mm] if r.psd else None
                        ),
                        "p80": r.psd.p80 if r.psd else None,
                    }
                    for r in result.results
                    if r.success
                ],
            }

        return {
            "valid": result.success,
            "format_detected": ImportFormat.CSV_MULTI.value,
            "errors": all_errors,
            "warnings": all_warnings,
            "stats": stats,
        }
    else:
        stats = None
        if result.success and result.psd:
            stats = {
                "points_count": len(result.psd.points),
                "size_range_mm": [result.psd.points[0].size_mm, result.psd.points[-1].size_mm],
                "p50": result.psd.get_pxx(50),
                "p80": result.psd.p80,
            }

        return {
            "valid": result.success,
            "format_detected": result.format_detected.value if result.format_detected else None,
            "errors": result.errors,
            "warnings": result.warnings,
            "stats": stats,
        }
