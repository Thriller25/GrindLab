import uuid

from fastapi.testclient import TestClient


def _create_plant(client: TestClient) -> str:
    payload = {"name": "Test Plant", "code": "TP-001", "company": "TestCo", "is_active": True}
    resp = client.post("/api/plants/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_flowsheet(client: TestClient, plant_id: str) -> str:
    payload = {"plant_id": plant_id, "name": "Test Flowsheet", "description": "desc", "status": "DRAFT"}
    resp = client.post("/api/flowsheets/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_flowsheet_version(client: TestClient, flowsheet_id: str) -> str:
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


def test_calc_run_happy_path(client: TestClient):
    plant_id = _create_plant(client)
    flowsheet_id = _create_flowsheet(client, plant_id)
    flowsheet_version_id = _create_flowsheet_version(client, flowsheet_id)

    calc_payload = {
        "flowsheet_version_id": flowsheet_version_id,
        "scenario_name": "Baseline",
        "comment": "Run 1",
        "input_json": {"feed_tph": 100, "target_p80_microns": 150},
    }
    resp = client.post("/api/calc/flowsheet-run", json=calc_payload)
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["flowsheet_version_id"] == flowsheet_version_id
    assert body["status"] == "success"
    assert body["error_message"] is None
    assert body["result_json"]
    assert body["started_at"] is not None
    assert body["finished_at"] is not None


def test_calc_run_not_found_flowsheet_version(client: TestClient):
    missing_id = "11111111-1111-1111-1111-111111111111"
    resp = client.post(
        "/api/calc/flowsheet-run",
        json={
            "flowsheet_version_id": missing_id,
            "input_json": {"feed_tph": 100, "target_p80_microns": 150},
        },
    )
    assert resp.status_code == 404
    assert missing_id in resp.json()["detail"]


def test_calc_run_invalid_input_json(client: TestClient):
    plant_id = _create_plant(client)
    flowsheet_id = _create_flowsheet(client, plant_id)
    flowsheet_version_id = _create_flowsheet_version(client, flowsheet_id)

    resp = client.post(
        "/api/calc/flowsheet-run",
        json={
            "flowsheet_version_id": flowsheet_version_id,
            "input_json": {"feed_tph": 100},
        },
    )
    assert resp.status_code == 400
    assert "input_json" in resp.json()["detail"]


def test_get_calc_runs_list(client: TestClient):
    plant_id = _create_plant(client)
    flowsheet_id = _create_flowsheet(client, plant_id)
    flowsheet_version_id = _create_flowsheet_version(client, flowsheet_id)

    # Create two runs
    for scenario in ["Baseline", "Alt"]:
        resp = client.post(
            "/api/calc/flowsheet-run",
            json={
                "flowsheet_version_id": flowsheet_version_id,
                "scenario_name": scenario,
                "input_json": {"feed_tph": 120, "target_p80_microns": 160},
            },
        )
        assert resp.status_code in (200, 201)

    resp = client.get(f"/api/calc-runs/by-flowsheet-version/{flowsheet_version_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2
    assert any(item.get("scenario_name") for item in body["items"])
