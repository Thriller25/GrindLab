"""
Тесты для Import Parsers (F3.1).

Проверяют:
- Парсинг CSV (simple, meta, retained, tyler, multi)
- Парсинг JSON (psd, material)
- Автоопределение формата
- Обработку ошибок и валидацию
"""

from pathlib import Path

import pytest
from app.schemas.contracts import (
    ImportFormat,
    ImportResult,
    MultiImportResult,
    import_psd,
    parse_csv_multi,
    parse_csv_retained,
    parse_csv_simple,
    parse_csv_tyler,
    parse_json_material,
    parse_json_psd,
    tyler_mesh_to_mm,
)

# Путь к тестовым данным
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"


# ==================== CSV Simple Tests ====================


class TestCSVSimple:
    """Тесты для простого CSV формата."""

    def test_parse_simple_csv(self):
        """Парсинг простого CSV."""
        content = """size_mm,cum_passing
6.35,100.0
4.75,92.5
3.35,85.0
2.36,75.2
1.7,65.8
1.18,55.2
0.85,45.0
0.6,35.5
"""
        result = parse_csv_simple(content)

        assert result.success
        assert result.psd is not None
        assert len(result.psd.points) == 8
        assert result.format_detected == ImportFormat.CSV_SIMPLE

    def test_parse_csv_with_metadata(self):
        """Парсинг CSV с метаданными."""
        content = """# Material: Test Ore
# Source: Lab Analysis
# SG: 2.85
# Moisture: 4.5%
size_mm,cum_passing
6.35,100.0
4.75,92.5
3.35,85.0
2.36,75.2
1.7,65.8
"""
        result = parse_csv_simple(content)

        assert result.success
        assert result.metadata is not None
        assert result.metadata.name == "Test Ore"
        assert result.metadata.source == "Lab Analysis"
        assert result.metadata.specific_gravity == 2.85
        assert result.metadata.moisture_pct == 4.5
        assert result.format_detected == ImportFormat.CSV_META

    def test_parse_from_file(self):
        """Парсинг из реального файла."""
        file_path = TEST_DATA_DIR / "ore_feed_simple.csv"
        if not file_path.exists():
            pytest.skip("Test data file not found")

        content = file_path.read_text()
        result = parse_csv_simple(content)

        assert result.success
        assert result.psd is not None
        assert len(result.psd.points) >= 20  # Должно быть много точек

    def test_parse_file_with_meta(self):
        """Парсинг файла с метаданными."""
        file_path = TEST_DATA_DIR / "ore_feed_with_meta.csv"
        if not file_path.exists():
            pytest.skip("Test data file not found")

        content = file_path.read_text()
        result = parse_csv_simple(content)

        assert result.success
        assert result.metadata.name == "SAG Mill Feed - Primary Crusher Product"
        assert result.metadata.specific_gravity == 2.85

    def test_missing_column(self):
        """Ошибка при отсутствии колонки."""
        content = """size,value
6.35,100.0
4.75,92.5
"""
        result = parse_csv_simple(content)

        assert not result.success
        assert any("size_mm" in e.lower() or "not found" in e.lower() for e in result.errors)

    def test_too_few_points(self):
        """Ошибка при недостаточном количестве точек."""
        content = """size_mm,cum_passing
6.35,100.0
4.75,92.5
3.35,85.0
"""
        result = parse_csv_simple(content)

        assert not result.success
        assert any("at least 4" in e.lower() for e in result.errors)


# ==================== CSV Retained Tests ====================


class TestCSVRetained:
    """Тесты для CSV с retained формата."""

    def test_parse_retained(self):
        """Парсинг retained формата."""
        content = """size_mm,retained_pct,cum_retained_pct
6.0,0.0,0.0
4.75,5.0,5.0
3.35,10.0,15.0
2.36,15.0,30.0
1.7,20.0,50.0
1.18,15.0,65.0
0.85,10.0,75.0
0.6,10.0,85.0
0.425,8.0,93.0
0.3,7.0,100.0
"""
        result = parse_csv_retained(content)

        assert result.success
        assert result.psd is not None
        # cum_passing = 100 - cum_retained
        # После сортировки: последняя точка (size=6.0) имеет cum_retained=0 → cum_passing=100
        # Первая точка (size=0.3) имеет cum_retained=100 → cum_passing=0
        assert result.psd.points[-1].cum_passing == pytest.approx(100.0, abs=0.1)
        assert result.psd.points[0].cum_passing == pytest.approx(0.0, abs=0.1)

    def test_parse_from_file(self):
        """Парсинг retained из файла."""
        file_path = TEST_DATA_DIR / "sieve_analysis_retained.csv"
        if not file_path.exists():
            pytest.skip("Test data file not found")

        content = file_path.read_text()
        result = parse_csv_retained(content)

        assert result.success
        assert result.format_detected == ImportFormat.CSV_RETAINED


# ==================== CSV Tyler Tests ====================


class TestCSVTyler:
    """Тесты для CSV с Tyler mesh."""

    def test_parse_tyler(self):
        """Парсинг Tyler mesh формата."""
        content = """mesh,cum_passing
4,100.0
6,95.0
8,88.0
10,78.0
14,65.0
20,52.0
"""
        result = parse_csv_tyler(content)

        assert result.success
        assert result.psd is not None
        # Mesh 4 = 4.75 мм
        assert any(abs(p.size_mm - 4.75) < 0.01 for p in result.psd.points)

    def test_tyler_mesh_conversion(self):
        """Проверка конвертации Tyler mesh."""
        assert tyler_mesh_to_mm(4) == 4.75
        assert tyler_mesh_to_mm(200) == 0.075
        assert tyler_mesh_to_mm(325) == 0.045
        assert tyler_mesh_to_mm(9999) is None  # Неизвестный mesh

    def test_parse_from_file(self):
        """Парсинг Tyler из файла."""
        file_path = TEST_DATA_DIR / "psd_tyler_mesh.csv"
        if not file_path.exists():
            pytest.skip("Test data file not found")

        content = file_path.read_text()
        result = parse_csv_tyler(content)

        assert result.success


# ==================== CSV Multi Tests ====================


class TestCSVMulti:
    """Тесты для multi-sample CSV."""

    def test_parse_multi(self):
        """Парсинг multi-sample формата."""
        content = """sample_id,sample_name,size_mm,cum_passing
S1,Sample 1,6.0,100.0
S1,Sample 1,4.0,90.0
S1,Sample 1,2.0,75.0
S1,Sample 1,1.0,55.0
S1,Sample 1,0.5,35.0
S2,Sample 2,6.0,100.0
S2,Sample 2,4.0,85.0
S2,Sample 2,2.0,65.0
S2,Sample 2,1.0,45.0
S2,Sample 2,0.5,25.0
"""
        result = parse_csv_multi(content)

        assert isinstance(result, MultiImportResult)
        assert result.success
        assert len(result.results) == 2

        # Проверяем каждый sample
        sample_ids = {r.metadata.sample_id for r in result.results}
        assert "S1" in sample_ids
        assert "S2" in sample_ids

    def test_parse_from_file(self):
        """Парсинг multi из файла."""
        file_path = TEST_DATA_DIR / "ball_mill_products.csv"
        if not file_path.exists():
            pytest.skip("Test data file not found")

        content = file_path.read_text()
        result = parse_csv_multi(content)

        assert isinstance(result, MultiImportResult)
        assert result.success
        assert len(result.results) == 3  # 3 samples в файле


# ==================== JSON Tests ====================


class TestJSONPSD:
    """Тесты для JSON PSD формата."""

    def test_parse_json_psd(self):
        """Парсинг JSON PSD."""
        content = """{
    "name": "Test PSD",
    "interpolation": "log_linear",
    "points": [
        {"size_mm": 6.0, "cum_passing": 100.0},
        {"size_mm": 4.0, "cum_passing": 85.0},
        {"size_mm": 2.0, "cum_passing": 65.0},
        {"size_mm": 1.0, "cum_passing": 45.0},
        {"size_mm": 0.5, "cum_passing": 25.0}
    ]
}"""
        result = parse_json_psd(content)

        assert result.success
        assert result.psd is not None
        assert len(result.psd.points) == 5
        assert result.metadata.name == "Test PSD"

    def test_parse_from_file(self):
        """Парсинг JSON из файла."""
        file_path = TEST_DATA_DIR / "psd_only.json"
        if not file_path.exists():
            pytest.skip("Test data file not found")

        content = file_path.read_text()
        result = parse_json_psd(content)

        assert result.success

    def test_invalid_json(self):
        """Ошибка при невалидном JSON."""
        content = "{ invalid json }"
        result = parse_json_psd(content)

        assert not result.success
        assert any("invalid json" in e.lower() for e in result.errors)


class TestJSONMaterial:
    """Тесты для полного Material JSON."""

    def test_parse_material(self):
        """Парсинг полного Material."""
        content = """{
    "name": "Test Material",
    "source": {
        "location": "Test Location",
        "sample_id": "TST-001",
        "sample_date": "2024-01-15"
    },
    "properties": {
        "specific_gravity": 2.85,
        "moisture_pct": 4.5,
        "bond_work_index_kwh_t": 14.2
    },
    "psd": {
        "interpolation": "log_linear",
        "points": [
            {"size_mm": 6.0, "cum_passing": 100.0},
            {"size_mm": 4.0, "cum_passing": 85.0},
            {"size_mm": 2.0, "cum_passing": 65.0},
            {"size_mm": 1.0, "cum_passing": 45.0},
            {"size_mm": 0.5, "cum_passing": 25.0}
        ]
    }
}"""
        result = parse_json_material(content)

        assert result.success
        assert result.psd is not None
        assert result.metadata.name == "Test Material"
        assert result.metadata.specific_gravity == 2.85
        assert result.metadata.sample_id == "TST-001"

    def test_parse_from_file(self):
        """Парсинг Material из файла."""
        file_path = TEST_DATA_DIR / "material_full.json"
        if not file_path.exists():
            pytest.skip("Test data file not found")

        content = file_path.read_text()
        result = parse_json_material(content)

        assert result.success
        assert result.metadata.name == "SAG Mill Feed - Oxide Zone"


# ==================== Auto-detection Tests ====================


class TestAutoDetection:
    """Тесты автоопределения формата."""

    def test_detect_csv_simple(self):
        """Автоопределение простого CSV."""
        content = """size_mm,cum_passing
6.0,100.0
4.0,85.0
2.0,65.0
1.0,45.0
0.5,25.0
"""
        result = import_psd(content)

        assert isinstance(result, ImportResult)
        assert result.success
        assert result.format_detected == ImportFormat.CSV_SIMPLE

    def test_detect_json(self):
        """Автоопределение JSON."""
        content = """{
    "points": [
        {"size_mm": 6.0, "cum_passing": 100.0},
        {"size_mm": 4.0, "cum_passing": 85.0},
        {"size_mm": 2.0, "cum_passing": 65.0},
        {"size_mm": 1.0, "cum_passing": 45.0},
        {"size_mm": 0.5, "cum_passing": 25.0}
    ]
}"""
        result = import_psd(content)

        assert isinstance(result, ImportResult)
        assert result.success
        assert result.format_detected == ImportFormat.JSON_PSD

    def test_detect_by_filename(self):
        """Определение формата по имени файла."""
        csv_content = """size_mm,cum_passing
6.0,100.0
4.0,85.0
2.0,65.0
1.0,45.0
0.5,25.0
"""
        result = import_psd(csv_content, filename="test.csv")

        assert isinstance(result, ImportResult)
        assert result.success

    def test_detect_multi_csv(self):
        """Автоопределение multi-sample CSV."""
        content = """sample_id,size_mm,cum_passing
S1,6.0,100.0
S1,4.0,85.0
S1,2.0,65.0
S1,1.0,45.0
S1,0.5,25.0
"""
        result = import_psd(content)

        assert isinstance(result, MultiImportResult)


# ==================== Validation Tests ====================


class TestValidation:
    """Тесты валидации данных."""

    def test_invalid_values_warning(self):
        """Предупреждение при невалидных значениях."""
        content = """size_mm,cum_passing
6.0,105.0
4.0,85.0
2.0,65.0
1.0,45.0
0.5,25.0
"""
        result = parse_csv_simple(content)

        # Должен успешно парсить, но с предупреждением
        assert result.success
        assert len(result.warnings) > 0

    def test_negative_size_error(self):
        """Ошибка при отрицательном размере."""
        content = """size_mm,cum_passing
6.0,100.0
-4.0,85.0
2.0,65.0
1.0,45.0
0.5,25.0
"""
        result = parse_csv_simple(content)

        # Точка с отрицательным размером пропускается
        assert len(result.errors) > 0

    def test_parse_invalid_files(self):
        """Проверка обработки невалидных файлов."""
        # Bad values
        file_path = TEST_DATA_DIR / "invalid_psd_bad_values.csv"
        if file_path.exists():
            content = file_path.read_text()
            result = parse_csv_simple(content)
            # Должен иметь warnings о значениях вне диапазона
            assert len(result.warnings) > 0 or len(result.errors) > 0

        # Too few points
        file_path = TEST_DATA_DIR / "invalid_psd_too_few_points.csv"
        if file_path.exists():
            content = file_path.read_text()
            result = parse_csv_simple(content)
            assert not result.success

        # Wrong columns
        file_path = TEST_DATA_DIR / "invalid_psd_wrong_columns.csv"
        if file_path.exists():
            content = file_path.read_text()
            result = parse_csv_simple(content)
            assert not result.success


# ==================== PSD Quality Tests ====================


class TestPSDQuality:
    """Тесты качества импортированного PSD."""

    def test_psd_properties(self):
        """Проверка свойств импортированного PSD."""
        content = """size_mm,cum_passing
6.0,100.0
4.0,90.0
2.0,75.0
1.0,50.0
0.5,25.0
0.25,10.0
"""
        result = parse_csv_simple(content)

        assert result.success
        psd = result.psd

        # Проверяем P-values
        p50 = psd.get_pxx(50)
        assert 0.9 < p50 < 1.1  # P50 около 1.0 мм

        p80 = psd.p80
        assert 1.5 < p80 < 3.0  # P80 между 1.5 и 3.0 мм

    def test_sorted_points(self):
        """Точки должны быть отсортированы."""
        content = """size_mm,cum_passing
1.0,50.0
6.0,100.0
0.5,25.0
2.0,75.0
"""
        result = parse_csv_simple(content)

        assert result.success
        sizes = [p.size_mm for p in result.psd.points]
        assert sizes == sorted(sizes)
