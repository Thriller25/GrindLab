import time
import uuid

from fastapi.testclient import TestClient

from .utils import (
    create_flowsheet,
    create_flowsheet_version,
    create_plant,
    create_project,
    link_project_to_version,
)


def _register_and_token(client: TestClient, email: str, password: str = "secret") -> str:
    resp = client.post("/api/auth/register", json={"email": email, "full_name": "User", "password": password})
    assert resp.status_code in (200, 201)
    token_resp = client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_resp.status_code == 200
    return token_resp.json()["access_token"]


def _auth_headers(client: TestClient, email: str) -> dict:
    token = _register_and_token(client, email)
    return {"Authorization": f"Bearer {token}"}


def _create_run(client: TestClient, flowsheet_version_id: str, project_id: int, scenario_id: str | None = None) -> str:
    resp = client.post(
        "/api/calc/flowsheet-run",
        json={
            "flowsheet_version_id": flowsheet_version_id,
            "project_id": project_id,
            "scenario_id": scenario_id,
            "scenario_name": "Run for comments",
            "input_json": {"feed_tph": 100, "target_p80_microns": 150},
        },
    )
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


def _create_scenario(client: TestClient, flowsheet_version_id: str, project_id: int) -> str:
    resp = client.post(
        "/api/calc-scenarios",
        json={
            "flowsheet_version_id": flowsheet_version_id,
            "project_id": project_id,
            "name": "Scenario for comments",
            "default_input_json": {"feed_tph": 120, "target_p80_microns": 160},
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _setup_project_resources(client: TestClient, headers: dict) -> tuple[int, str, str]:
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)
    project_id = create_project(client, plant_id, headers=headers)
    link_project_to_version(client, project_id, flowsheet_version_id, headers=headers)
    scenario_id = _create_scenario(client, flowsheet_version_id, project_id)
    run_id = _create_run(client, flowsheet_version_id, project_id, scenario_id)
    return project_id, scenario_id, run_id


def test_create_comment_for_scenario(client: TestClient):
    headers = _auth_headers(client, "scenario-author@example.com")
    project_id, scenario_id, _ = _setup_project_resources(client, headers)

    payload = {"scenario_id": scenario_id, "text": "  Scenario discussion "}
    resp = client.post(f"/api/projects/{project_id}/comments", json=payload, headers=headers)
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["project_id"] == project_id
    assert body["scenario_id"] == scenario_id
    assert body["calc_run_id"] is None
    assert body["target_type"] == "scenario"
    assert body["author"] == "scenario-author@example.com"
    assert body["text"] == "Scenario discussion"

    list_resp = client.get(f"/api/scenarios/{scenario_id}/comments", headers=headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["id"] == body["id"]


def test_create_comment_for_run(client: TestClient):
    headers = _auth_headers(client, "run-author@example.com")
    project_id, scenario_id, run_id = _setup_project_resources(client, headers)

    resp = client.post(
        f"/api/projects/{project_id}/comments",
        json={"calc_run_id": run_id, "text": "Run comment"},
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["project_id"] == project_id
    assert body["calc_run_id"] == run_id
    assert body["scenario_id"] is None
    assert body["target_type"] == "calc_run"
    assert body["author"] == "run-author@example.com"

    list_resp = client.get(f"/api/calc-runs/{run_id}/comments", headers=headers)
    assert list_resp.status_code == 200
    assert any(item["id"] == body["id"] for item in list_resp.json()["items"])


def test_reject_multiple_targets(client: TestClient):
    headers = _auth_headers(client, "multi@example.com")
    project_id, scenario_id, run_id = _setup_project_resources(client, headers)

    resp = client.post(
        f"/api/projects/{project_id}/comments",
        json={"scenario_id": scenario_id, "calc_run_id": run_id, "text": "Invalid"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_reject_empty_text(client: TestClient):
    headers = _auth_headers(client, "empty@example.com")
    project_id, scenario_id, _ = _setup_project_resources(client, headers)

    resp = client.post(
        f"/api/projects/{project_id}/comments",
        json={"scenario_id": scenario_id, "text": "   "},
        headers=headers,
    )
    assert resp.status_code == 422


def test_comments_sorted_desc(client: TestClient):
    headers = _auth_headers(client, "sorter@example.com")
    project_id, scenario_id, _ = _setup_project_resources(client, headers)

    first_resp = client.post(
        f"/api/projects/{project_id}/comments",
        json={"scenario_id": scenario_id, "text": "Первый"},
        headers=headers,
    )
    assert first_resp.status_code in (200, 201)
    time.sleep(0.01)
    second_resp = client.post(
        f"/api/projects/{project_id}/comments",
        json={"scenario_id": scenario_id, "text": "Второй"},
        headers=headers,
    )
    assert second_resp.status_code in (200, 201)

    list_resp = client.get(f"/api/scenarios/{scenario_id}/comments?limit=2", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert items[0]["text"] == "Второй"
    assert items[1]["text"] == "Первый"


def test_comment_write_requires_auth_and_membership(client: TestClient):
    owner_headers = _auth_headers(client, "owner@example.com")
    project_id, scenario_id, _ = _setup_project_resources(client, owner_headers)

    unauth_resp = client.post(
        f"/api/projects/{project_id}/comments",
        json={"scenario_id": scenario_id, "text": "No token"},
    )
    assert unauth_resp.status_code == 401

    other_headers = _auth_headers(client, "stranger@example.com")
    forbidden_resp = client.post(
        f"/api/projects/{project_id}/comments",
        json={"scenario_id": scenario_id, "text": "Denied"},
        headers=other_headers,
    )
    assert forbidden_resp.status_code == 403
