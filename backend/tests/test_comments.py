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


def _register_and_token(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/auth/register", json={"email": email, "full_name": "User", "password": password})
    assert resp.status_code in (200, 201)
    token_resp = client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_resp.status_code == 200
    return token_resp.json()["access_token"]


def test_add_comment_to_run_as_authenticated_user(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)
    run_id = _create_run(client, flowsheet_version_id)

    email = "commenter@example.com"
    access_token = _register_and_token(client, email, "secret")

    resp = client.post(
        f"/api/calc-runs/{run_id}/comments/me",
        json={"text": "My note"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["entity_type"] == "calc_run"
    assert body["entity_id"] == run_id
    assert body["author"] == email
    assert body["text"] == "My note"


def test_add_comment_to_run_me_unauthorized(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)
    run_id = _create_run(client, flowsheet_version_id)

    resp = client.post(
        f"/api/calc-runs/{run_id}/comments/me",
        json={"text": "My note"},
    )
    assert resp.status_code == 401


def test_add_comment_to_scenario_as_authenticated_user(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)
    scenario_id = _create_scenario(client, flowsheet_version_id)

    email = "scenario@example.com"
    access_token = _register_and_token(client, email, "secret")

    resp = client.post(
        f"/api/calc-scenarios/{scenario_id}/comments/me",
        json={"text": "Scenario note"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["entity_type"] == "scenario"
    assert body["entity_id"] == scenario_id
    assert body["author"] == email
    assert body["text"] == "Scenario note"


def test_add_comment_to_scenario_me_unauthorized(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)
    scenario_id = _create_scenario(client, flowsheet_version_id)

    resp = client.post(
        f"/api/calc-scenarios/{scenario_id}/comments/me",
        json={"text": "Scenario note"},
    )
    assert resp.status_code == 401
