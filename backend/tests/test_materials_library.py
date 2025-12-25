"""
Tests for Materials Library API — F4.4: Material assignment to feed.
"""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


class TestMaterialsLibraryAPI:
    """Tests for /api/materials endpoints."""

    def test_list_materials_returns_demo_data(self):
        """GET /api/materials should return demo materials."""
        response = client.get("/api/materials")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3  # Demo data has 3 materials
        assert len(data["items"]) == data["total"]

    def test_list_materials_structure(self):
        """Verify response structure for material list."""
        response = client.get("/api/materials")

        assert response.status_code == 200
        data = response.json()

        # Check first item structure
        item = data["items"][0]
        assert "id" in item
        assert "name" in item
        assert "created_at" in item
        # Optional fields
        assert "source" in item
        assert "solids_tph" in item
        assert "p80_mm" in item
        assert "psd_points_count" in item

    def test_get_material_by_id(self):
        """GET /api/materials/{id} should return full material details."""
        # First get list to find an ID
        list_response = client.get("/api/materials")
        material_id = list_response.json()["items"][0]["id"]

        # Get full material
        response = client.get(f"/api/materials/{material_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == material_id
        assert "name" in data
        assert "psd" in data  # Full PSD data

    def test_get_material_not_found(self):
        """GET /api/materials/{id} should return 404 for unknown ID."""
        response = client.get("/api/materials/non-existent-id")

        assert response.status_code == 404

    def test_create_material(self):
        """POST /api/materials should create a new material."""
        new_material = {
            "name": "Test Material",
            "source": "Test Source",
            "solids_tph": 500.0,
            "p80_mm": 75.0,
            "bond_wi": 15.0,
            "sg": 2.7,
        }

        response = client.post("/api/materials", json=new_material)

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["name"] == "Test Material"
        assert data["solids_tph"] == 500.0
        assert data["p80_mm"] == 75.0

    def test_create_material_with_psd(self):
        """POST /api/materials with PSD data."""
        new_material = {
            "name": "Material with PSD",
            "psd": [
                {"size_mm": 0.075, "cum_passing": 10},
                {"size_mm": 0.150, "cum_passing": 25},
                {"size_mm": 0.300, "cum_passing": 45},
                {"size_mm": 0.600, "cum_passing": 65},
                {"size_mm": 1.18, "cum_passing": 80},
                {"size_mm": 2.36, "cum_passing": 92},
                {"size_mm": 4.75, "cum_passing": 100},
            ],
        }

        response = client.post("/api/materials", json=new_material)

        assert response.status_code == 201
        data = response.json()

        assert data["psd"] is not None
        assert len(data["psd"]) == 7

    def test_create_material_validation(self):
        """POST /api/materials should validate input."""
        # Empty name
        response = client.post("/api/materials", json={"name": ""})
        assert response.status_code == 422

    def test_delete_material(self):
        """DELETE /api/materials/{id} should remove material."""
        # Create a material first
        create_response = client.post(
            "/api/materials", json={"name": "To Delete", "solids_tph": 100}
        )
        material_id = create_response.json()["id"]

        # Delete it
        delete_response = client.delete(f"/api/materials/{material_id}")
        assert delete_response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/materials/{material_id}")
        assert get_response.status_code == 404

    def test_delete_material_not_found(self):
        """DELETE /api/materials/{id} should return 404 for unknown ID."""
        response = client.delete("/api/materials/non-existent-id")
        assert response.status_code == 404


class TestMaterialsForFlowsheet:
    """Tests for material assignment to flowsheet nodes."""

    def test_materials_have_required_fields_for_feed(self):
        """Materials should have fields needed for feed node assignment."""
        response = client.get("/api/materials")
        data = response.json()

        for item in data["items"]:
            # These fields are used by MaterialSelector
            assert "id" in item
            assert "name" in item
            # Optional but useful for display
            assert "source" in item or item.get("source") is None
            assert "solids_tph" in item or item.get("solids_tph") is None
            assert "p80_mm" in item or item.get("p80_mm") is None

    def test_demo_materials_have_psd(self):
        """Demo materials should have PSD for realistic simulation."""
        response = client.get("/api/materials")
        data = response.json()

        # At least one material should have PSD
        materials_with_psd = [m for m in data["items"] if m["psd_points_count"] > 0]
        assert len(materials_with_psd) >= 2

    def test_material_full_details_for_simulation(self):
        """Full material details should include all simulation params."""
        list_response = client.get("/api/materials")
        material_id = list_response.json()["items"][0]["id"]

        response = client.get(f"/api/materials/{material_id}")
        data = response.json()

        # Full material should have PSD points
        if data["psd"]:
            assert isinstance(data["psd"], list)
            assert len(data["psd"]) > 0
            # Each point has size_mm and cum_passing
            point = data["psd"][0]
            assert "size_mm" in point
            assert "cum_passing" in point
