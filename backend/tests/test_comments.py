import uuid

from fastapi.testclient import TestClient

from .utils import create_flowsheet, create_flowsheet_version, create_plant


def _create_run(client: TestClient, flowsheet_version_id: str) -> str:
    resp = client.post(
        "/api/calc/flowsheet-run",
        json={
            "flowsheet_version_id": flowsheet_version_id,
            "scenario_name": "Run for comments",
            "input_json": {"feed_tph": 100, "target_p80_microns": 150},
        },
    )
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


def _create_scenario(client: TestClient, flowsheet_version_id: str) -> str:
    resp = client.post(
        "/api/calc-scenarios",
        json={
            "flowsheet_version_id": flowsheet_version_id,
            "name": "Scenario for comments",
            "default_input_json": {"feed_tph": 120, "target_p80_microns": 160},
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_comment_for_calc_run(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)
    run_id = _create_run(client, flowsheet_version_id)

    payload = {"author": "Tester", "text": "Baseline run looks good"}
    resp = client.post(f"/api/comments/calc-runs/{run_id}", json=payload)
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["entity_type"] == "calc_run"
    assert body["entity_id"] == run_id
    assert body["author"] == payload["author"]
    assert body["text"] == payload["text"]
    assert body["id"]
    assert body["created_at"]

    list_resp = client.get(f"/api/comments/calc-runs/{run_id}")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["total"] >= 1
    assert any(item["id"] == body["id"] for item in list_body["items"])


def test_create_comment_for_scenario(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)
    scenario_id = _create_scenario(client, flowsheet_version_id)

    payload = {"author": "Analyst", "text": "Scenario discussion"}
    resp = client.post(f"/api/comments/calc-scenarios/{scenario_id}", json=payload)
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["entity_type"] == "scenario"
    assert body["entity_id"] == scenario_id
    assert body["author"] == payload["author"]
    assert body["text"] == payload["text"]

    list_resp = client.get(f"/api/comments/calc-scenarios/{scenario_id}")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["total"] >= 1
    assert any(item["id"] == body["id"] for item in list_body["items"])


def test_create_comment_invalid_entity(client: TestClient):
    payload = {
        "entity_type": "calc_run",
        "entity_id": str(uuid.uuid4()),
        "author": "Ghost",
        "text": "Invalid run",
    }
    resp = client.post("/api/comments", json=payload)
    assert resp.status_code == 404
