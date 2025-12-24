"""
Тесты для Materials Import API (F3.1).

Проверяют:
- GET /api/materials/import/formats
- POST /api/materials/import/psd/preview
- POST /api/materials/import/psd
- POST /api/materials/import/psd/validate
"""

from pathlib import Path

import pytest
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Путь к тестовым данным
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"


# ==================== Formats Endpoint Tests ====================


class TestFormatsEndpoint:
    """Тесты для GET /api/materials/import/formats."""

    def test_get_formats(self):
        """Получение списка форматов."""
        response = client.get("/api/materials/import/formats")

        assert response.status_code == 200
        data = response.json()

        assert "formats" in data
        assert len(data["formats"]) >= 5

        # Проверяем структуру
        fmt = data["formats"][0]
        assert "format" in fmt
        assert "name" in fmt
        assert "description" in fmt
        assert "extensions" in fmt
        assert "example" in fmt

    def test_formats_include_csv_simple(self):
        """Список включает CSV Simple."""
        response = client.get("/api/materials/import/formats")
        data = response.json()

        formats = {f["format"] for f in data["formats"]}
        assert "csv_simple" in formats

    def test_formats_include_json(self):
        """Список включает JSON форматы."""
        response = client.get("/api/materials/import/formats")
        data = response.json()

        formats = {f["format"] for f in data["formats"]}
        assert "json_psd" in formats
        assert "json_material" in formats


# ==================== Preview Endpoint Tests ====================


class TestPreviewEndpoint:
    """Тесты для POST /api/materials/import/psd/preview."""

    def test_preview_csv_simple(self):
        """Предпросмотр простого CSV."""
        csv_content = """size_mm,cum_passing
6.35,100.0
4.75,92.5
3.35,85.0
2.36,75.2
1.7,65.8
1.18,55.2
0.85,45.0
0.6,35.5
"""
        response = client.post(
            "/api/materials/import/psd/preview",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["format_detected"] == "csv_simple"
        assert data["psd"] is not None
        assert len(data["psd"]["points"]) == 8

    def test_preview_from_file(self):
        """Предпросмотр из реального файла."""
        file_path = TEST_DATA_DIR / "ore_feed_simple.csv"
        if not file_path.exists():
            pytest.skip("Test data file not found")

        with open(file_path, "rb") as f:
            response = client.post(
                "/api/materials/import/psd/preview",
                files={"file": ("ore_feed_simple.csv", f, "text/csv")},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["psd"] is not None

    def test_preview_json(self):
        """Предпросмотр JSON файла."""
        json_content = """{
    "points": [
        {"size_mm": 6.0, "cum_passing": 100.0},
        {"size_mm": 4.0, "cum_passing": 85.0},
        {"size_mm": 2.0, "cum_passing": 65.0},
        {"size_mm": 1.0, "cum_passing": 45.0},
        {"size_mm": 0.5, "cum_passing": 25.0}
    ]
}"""
        response = client.post(
            "/api/materials/import/psd/preview",
            files={"file": ("test.json", json_content, "application/json")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["format_detected"] == "json_psd"

    def test_preview_multi_sample(self):
        """Предпросмотр multi-sample файла."""
        csv_content = """sample_id,sample_name,size_mm,cum_passing
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
        response = client.post(
            "/api/materials/import/psd/preview",
            files={"file": ("multi.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["count"] == 2
        assert len(data["results"]) == 2

    def test_preview_with_format_hint(self):
        """Предпросмотр с указанием формата."""
        csv_content = """size_mm,cum_passing
6.0,100.0
4.0,85.0
2.0,65.0
1.0,45.0
0.5,25.0
"""
        response = client.post(
            "/api/materials/import/psd/preview",
            files={"file": ("test.csv", csv_content, "text/csv")},
            data={"format_hint": "csv_simple"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True

    def test_preview_invalid_format_hint(self):
        """Ошибка при неверном формате."""
        csv_content = "size_mm,cum_passing\n6.0,100.0"
        response = client.post(
            "/api/materials/import/psd/preview",
            files={"file": ("test.csv", csv_content, "text/csv")},
            data={"format_hint": "unknown_format"},
        )

        assert response.status_code == 400

    def test_preview_invalid_file(self):
        """Предпросмотр невалидного файла."""
        csv_content = """size,value
6.0,100.0
4.0,85.0
"""
        response = client.post(
            "/api/materials/import/psd/preview",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert len(data["errors"]) > 0


# ==================== Import Endpoint Tests ====================


class TestImportEndpoint:
    """Тесты для POST /api/materials/import/psd."""

    def test_import_csv(self):
        """Импорт CSV файла."""
        csv_content = """size_mm,cum_passing
6.0,100.0
4.0,85.0
2.0,65.0
1.0,45.0
0.5,25.0
"""
        response = client.post(
            "/api/materials/import/psd",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["psd"] is not None
        assert data["psd"]["p80"] is not None

    def test_import_with_name(self):
        """Импорт с переопределением имени."""
        csv_content = """# Material: Original Name
size_mm,cum_passing
6.0,100.0
4.0,85.0
2.0,65.0
1.0,45.0
0.5,25.0
"""
        response = client.post(
            "/api/materials/import/psd",
            files={"file": ("test.csv", csv_content, "text/csv")},
            data={"name": "Custom Name"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["metadata"]["name"] == "Custom Name"

    def test_import_invalid_returns_422(self):
        """Невалидный файл возвращает 422."""
        csv_content = """size,value
6.0,100.0
"""
        response = client.post(
            "/api/materials/import/psd",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 422


# ==================== Validate Endpoint Tests ====================


class TestValidateEndpoint:
    """Тесты для POST /api/materials/import/psd/validate."""

    def test_validate_valid_file(self):
        """Валидация корректного файла."""
        csv_content = """size_mm,cum_passing
6.0,100.0
4.0,85.0
2.0,65.0
1.0,45.0
0.5,25.0
"""
        response = client.post(
            "/api/materials/import/psd/validate",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert data["format_detected"] == "csv_simple"
        assert len(data["errors"]) == 0
        assert data["stats"] is not None
        assert data["stats"]["points_count"] == 5

    def test_validate_invalid_file(self):
        """Валидация невалидного файла."""
        csv_content = """size_mm,cum_passing
6.0,100.0
4.0,85.0
"""
        response = client.post(
            "/api/materials/import/psd/validate",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_validate_returns_stats(self):
        """Валидация возвращает статистику."""
        csv_content = """size_mm,cum_passing
6.0,100.0
4.0,90.0
2.0,70.0
1.0,50.0
0.5,30.0
0.25,15.0
"""
        response = client.post(
            "/api/materials/import/psd/validate",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert data["stats"]["points_count"] == 6
        assert data["stats"]["p50"] is not None
        assert data["stats"]["p80"] is not None
        assert data["stats"]["size_range_mm"][0] < data["stats"]["size_range_mm"][1]

    def test_validate_multi_sample(self):
        """Валидация multi-sample файла."""
        csv_content = """sample_id,size_mm,cum_passing
S1,6.0,100.0
S1,4.0,90.0
S1,2.0,75.0
S1,1.0,55.0
S1,0.5,35.0
S2,6.0,100.0
S2,4.0,85.0
S2,2.0,65.0
S2,1.0,45.0
S2,0.5,25.0
"""
        response = client.post(
            "/api/materials/import/psd/validate",
            files={"file": ("multi.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert data["stats"]["sample_count"] == 2


# ==================== Integration Tests ====================


class TestIntegration:
    """Интеграционные тесты с реальными файлами."""

    def test_import_all_test_files(self):
        """Импорт всех тестовых файлов."""
        if not TEST_DATA_DIR.exists():
            pytest.skip("Test data directory not found")

        test_files = [
            "ore_feed_simple.csv",
            "ore_feed_with_meta.csv",
            "psd_tyler_mesh.csv",
            "sieve_analysis_retained.csv",
            "psd_only.json",
            "material_full.json",
        ]

        for filename in test_files:
            file_path = TEST_DATA_DIR / filename
            if not file_path.exists():
                continue

            with open(file_path, "rb") as f:
                response = client.post(
                    "/api/materials/import/psd/preview",
                    files={"file": (filename, f, "application/octet-stream")},
                )

            assert response.status_code == 200, f"Failed for {filename}"
            data = response.json()

            # Для multi-sample проверяем по-другому
            if "count" in data:
                assert data["success"] is True, f"Failed for {filename}: {data.get('errors')}"
            else:
                assert data["success"] is True, f"Failed for {filename}: {data.get('errors')}"

    def test_import_ball_mill_products(self):
        """Импорт multi-sample файла ball_mill_products.csv."""
        file_path = TEST_DATA_DIR / "ball_mill_products.csv"
        if not file_path.exists():
            pytest.skip("Test data file not found")

        with open(file_path, "rb") as f:
            response = client.post(
                "/api/materials/import/psd/preview",
                files={"file": ("ball_mill_products.csv", f, "text/csv")},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["count"] == 3  # 3 samples в файле
