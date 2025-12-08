from fastapi.testclient import TestClient


def create_plant(client: TestClient) -> str:
    payload = {"name": "Test Plant", "code": "TP-001", "company": "TestCo", "is_active": True}
    resp = client.post("/api/plants/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def create_flowsheet(client: TestClient, plant_id: str) -> str:
    payload = {"plant_id": plant_id, "name": "Test Flowsheet", "description": "desc", "status": "DRAFT"}
    resp = client.post("/api/flowsheets/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def create_flowsheet_version(client: TestClient, flowsheet_id: str) -> str:
    payload = {
        "flowsheet_id": flowsheet_id,
        "version_label": "v1",
        "status": "DRAFT",
        "is_active": True,
        "comment": "first",
    }
    resp = client.post("/api/flowsheet-versions/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def create_unit(client: TestClient, flowsheet_version_id: str) -> str:
    payload = {
        "flowsheet_version_id": flowsheet_version_id,
        "name": "Unit A",
        "unit_type": "CRUSHER",
        "is_active": True,
    }
    resp = client.post("/api/units/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]
