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


def test_me_dashboard_empty(client: TestClient):
    email = "dash-empty@ex.com"
    _, token = _register_and_token(client, email, "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/auth/me/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == email
    assert body["projects"] == []
    assert body["member_projects"] == []
    assert body["recent_calc_runs"] == []
    assert body["recent_comments"] == []
    assert body["summary"]["calc_runs_total"] == 0
    assert body["summary"]["comments_total"] == 0


def test_me_dashboard_with_data(client: TestClient):
    email = "dash-data@ex.com"
    _, token = _register_and_token(client, email, "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    project_resp = client.post(
        "/api/projects",
        json={"name": "My project", "description": "desc"},
        headers=headers,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    attach_resp = client.post(
        f"/api/projects/{project_id}/flowsheet-versions/{flowsheet_version_id}",
        headers=headers,
    )
    assert attach_resp.status_code == 201

    scenario_resp = client.post(
        "/api/calc-scenarios",
        json={
            "flowsheet_version_id": flowsheet_version_id,
            "name": "Dash scenario",
            "default_input_json": {"feed_tph": 100, "target_p80_microns": 150},
        },
    )
    assert scenario_resp.status_code == 201
    scenario_id = scenario_resp.json()["id"]

    run_resp = client.post(f"/api/calc/flowsheet-run/by-scenario/{scenario_id}", headers=headers)
    assert run_resp.status_code in (200, 201)
    run_id = run_resp.json()["id"]

    comment_resp1 = client.post(
        f"/api/calc-scenarios/{scenario_id}/comments/me",
        json={"text": "scenario note"},
        headers=headers,
    )
    assert comment_resp1.status_code in (200, 201)
    comment_resp2 = client.post(
        f"/api/calc-runs/{run_id}/comments/me",
        json={"text": "run note"},
        headers=headers,
    )
    assert comment_resp2.status_code in (200, 201)

    resp = client.get("/api/auth/me/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["projects"]) >= 1
    assert len(body["recent_calc_runs"]) >= 1
    assert len(body["recent_comments"]) >= 1
    assert body["summary"]["calc_runs_total"] >= len(body["recent_calc_runs"])
    assert body["summary"]["comments_total"] >= len(body["recent_comments"])


def test_me_dashboard_member_projects(client: TestClient):
    owner_id, owner_token = _register_and_token(client, "dash-owner@ex.com", "secret123")
    member_id, member_token = _register_and_token(client, "dash-member@ex.com", "secret123")
    headers_owner = {"Authorization": f"Bearer {owner_token}"}
    headers_member = {"Authorization": f"Bearer {member_token}"}
    assert owner_id != member_id

    project_resp = client.post(
        "/api/projects",
        json={"name": "Member project", "description": None},
        headers=headers_owner,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    add_resp = client.post(
        f"/api/projects/{project_id}/members",
        json={"email": "dash-member@ex.com", "role": "editor"},
        headers=headers_owner,
    )
    assert add_resp.status_code == 201

    resp_member = client.get("/api/auth/me/dashboard", headers=headers_member)
    assert resp_member.status_code == 200
    body = resp_member.json()
    assert any(p["id"] == project_id for p in body["member_projects"])


def test_me_dashboard_unauthorized(client: TestClient):
    resp = client.get("/api/auth/me/dashboard")
    assert resp.status_code == 401
