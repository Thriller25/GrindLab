import uuid

from fastapi.testclient import TestClient

from .utils import create_flowsheet, create_flowsheet_version, create_plant


def _register_and_token(client: TestClient, email: str, password: str) -> tuple[str, str]:
    reg_resp = client.post("/api/auth/register", json={"email": email, "full_name": "User", "password": password})
    assert reg_resp.status_code in (200, 201)
    user_id = reg_resp.json()["id"]
    token_resp = client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_resp.status_code == 200
    return user_id, token_resp.json()["access_token"]


def _setup_entities(client: TestClient, headers: dict) -> tuple[str, str, str]:
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    project_resp = client.post("/api/projects", json={"name": "Fav project", "description": None}, headers=headers)
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    attach_resp = client.post(
        f"/api/projects/{project_id}/flowsheet-versions/{flowsheet_version_id}",
        headers=headers,
    )
    assert attach_resp.status_code in (200, 201)

    scenario_resp = client.post(
        "/api/calc-scenarios",
        json={
            "flowsheet_version_id": flowsheet_version_id,
            "project_id": project_id,
            "name": "Fav scenario",
            "default_input_json": {"feed_tph": 120, "target_p80_microns": 140},
        },
        headers=headers,
    )
    assert scenario_resp.status_code == 201
    scenario_id = scenario_resp.json()["id"]

    run_resp = client.post(f"/api/calc/flowsheet-run/by-scenario/{scenario_id}", headers=headers)
    assert run_resp.status_code in (200, 201)
    run_id = run_resp.json()["id"]

    return project_id, scenario_id, run_id


def test_add_and_list_favorites(client: TestClient):
    _, token = _register_and_token(client, "fav-list@ex.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}
    project_id, scenario_id, run_id = _setup_entities(client, headers)

    for entity_type, entity_id in (
        ("project", project_id),
        ("scenario", scenario_id),
        ("calc_run", run_id),
    ):
        resp = client.post("/api/auth/me/favorites", json={"entity_type": entity_type, "entity_id": entity_id}, headers=headers)
        assert resp.status_code in (200, 201)

    list_resp = client.get("/api/auth/me/favorites", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    types = {item["entity_type"] for item in items}
    assert {"project", "scenario", "calc_run"}.issubset(types)


def test_add_favorite_invalid_type_or_missing_entity(client: TestClient):
    _, token = _register_and_token(client, "fav-invalid@ex.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/auth/me/favorites",
        json={"entity_type": "unknown", "entity_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp.status_code == 400

    resp_missing = client.post(
        "/api/auth/me/favorites",
        json={"entity_type": "project", "entity_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp_missing.status_code == 404


def test_remove_favorite(client: TestClient):
    _, token = _register_and_token(client, "fav-remove@ex.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}
    project_id, _, _ = _setup_entities(client, headers)

    add_resp = client.post(
        "/api/auth/me/favorites",
        json={"entity_type": "project", "entity_id": project_id},
        headers=headers,
    )
    assert add_resp.status_code in (200, 201)
    favorite_id = add_resp.json()["id"]

    del_resp = client.delete(f"/api/auth/me/favorites/{favorite_id}", headers=headers)
    assert del_resp.status_code == 204

    del_resp_again = client.delete(f"/api/auth/me/favorites/{favorite_id}", headers=headers)
    assert del_resp_again.status_code == 404

    list_resp = client.get("/api/auth/me/favorites", headers=headers)
    assert list_resp.status_code == 200
    assert all(item["id"] != favorite_id for item in list_resp.json())


def test_me_dashboard_contains_favorites(client: TestClient):
    _, token = _register_and_token(client, "fav-dash@ex.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}
    project_id, scenario_id, run_id = _setup_entities(client, headers)

    for entity_type, entity_id in (
        ("project", project_id),
        ("scenario", scenario_id),
        ("calc_run", run_id),
    ):
        resp = client.post("/api/auth/me/favorites", json={"entity_type": entity_type, "entity_id": entity_id}, headers=headers)
        assert resp.status_code in (200, 201)

    dash_resp = client.get("/api/auth/me/dashboard", headers=headers)
    assert dash_resp.status_code == 200
    body = dash_resp.json()
    assert any(p["id"] == project_id for p in body["favorites"]["projects"])
    assert any(s["id"] == scenario_id for s in body["favorites"]["scenarios"])
    assert any(r["id"] == run_id for r in body["favorites"]["calc_runs"])


def test_favorites_unauthorized(client: TestClient):
    resp_list = client.get("/api/auth/me/favorites")
    assert resp_list.status_code == 401

    resp_add = client.post("/api/auth/me/favorites", json={"entity_type": "project", "entity_id": str(uuid.uuid4())})
    assert resp_add.status_code == 401

    resp_del = client.delete(f"/api/auth/me/favorites/{uuid.uuid4()}")
    assert resp_del.status_code == 401
