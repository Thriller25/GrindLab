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


def test_create_and_list_my_projects(client: TestClient):
    user_id, token = _register_and_token(client, "proj@example.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(2):
        resp = client.post(
            "/api/projects",
            json={"name": f"Project {i+1}", "description": "Test project"},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["owner_user_id"] == user_id

    list_resp = client.get("/api/projects/my", headers=headers)
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["total"] >= 2
    assert all(item["owner_user_id"] == user_id for item in list_body["items"])


def test_attach_flowsheet_version_and_get_detail(client: TestClient):
    user_id, token = _register_and_token(client, "detail@example.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    project_resp = client.post(
        "/api/projects",
        json={"name": "Detail Project", "description": "desc"},
        headers=headers,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    attach_resp = client.post(
        f"/api/projects/{project_id}/flowsheet-versions/{flowsheet_version_id}",
        headers=headers,
    )
    assert attach_resp.status_code == 201

    detail_resp = client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail_body = detail_resp.json()
    assert detail_body["owner_user_id"] == user_id
    version_ids = [v["id"] for v in detail_body["flowsheet_versions"]]
    assert flowsheet_version_id in version_ids


def test_attach_flowsheet_version_for_foreign_project_forbidden(client: TestClient):
    user1_id, token1 = _register_and_token(client, "owner@example.com", "secret123")
    user2_id, token2 = _register_and_token(client, "other@example.com", "secret123")
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}
    assert user1_id != user2_id

    project_resp = client.post(
        "/api/projects",
        json={"name": "Owner project", "description": None},
        headers=headers1,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    attach_resp = client.post(
        f"/api/projects/{project_id}/flowsheet-versions/{flowsheet_version_id}",
        headers=headers2,
    )
    assert attach_resp.status_code == 403


def test_get_project_detail_unauthorized(client: TestClient):
    resp = client.get("/api/projects/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401


def test_project_summary_empty(client: TestClient):
    user_id, token = _register_and_token(client, "summary-empty@example.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    project_resp = client.post(
        "/api/projects",
        json={"name": "Empty", "description": None},
        headers=headers,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]
    assert project_resp.json()["owner_user_id"] == user_id

    summary_resp = client.get(f"/api/projects/{project_id}/summary", headers=headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["flowsheet_versions_total"] == 0
    assert summary["scenarios_total"] == 0
    assert summary["calc_runs_total"] == 0
    assert summary["comments_total"] == 0
    assert summary["calc_runs_by_status"] == {}
    assert summary["last_activity_at"] is None


def test_project_summary_with_activity(client: TestClient):
    user_id, token = _register_and_token(client, "summary-active@example.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    project_resp = client.post(
        "/api/projects",
        json={"name": "Active", "description": "desc"},
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
            "name": "Scenario A",
            "default_input_json": {"feed_tph": 100, "target_p80_microns": 150},
            "is_baseline": False,
        },
    )
    assert scenario_resp.status_code == 201
    scenario_id = scenario_resp.json()["id"]

    run_resp = client.post(f"/api/calc/flowsheet-run/by-scenario/{scenario_id}")
    assert run_resp.status_code in (200, 201)
    run_id = run_resp.json()["id"]

    comment_resp1 = client.post(
        f"/api/calc-scenarios/{scenario_id}/comments/me",
        json={"text": "Scenario comment"},
        headers=headers,
    )
    assert comment_resp1.status_code in (200, 201)
    comment_resp2 = client.post(
        f"/api/calc-runs/{run_id}/comments/me",
        json={"text": "Run comment"},
        headers=headers,
    )
    assert comment_resp2.status_code in (200, 201)

    summary_resp = client.get(f"/api/projects/{project_id}/summary", headers=headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["flowsheet_versions_total"] == 1
    assert summary["scenarios_total"] >= 1
    assert summary["calc_runs_total"] >= 1
    assert summary["comments_total"] >= 2
    assert summary["calc_runs_by_status"].get("success", 0) >= 1
    assert summary["last_activity_at"] is not None


def test_project_summary_forbidden_and_unauthorized(client: TestClient):
    user1_id, token1 = _register_and_token(client, "sum-owner@example.com", "secret123")
    user2_id, token2 = _register_and_token(client, "sum-other@example.com", "secret123")
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}
    assert user1_id != user2_id

    project_resp = client.post(
        "/api/projects",
        json={"name": "Owner", "description": None},
        headers=headers1,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    forbidden_resp = client.get(f"/api/projects/{project_id}/summary", headers=headers2)
    assert forbidden_resp.status_code == 403

    unauthorized_resp = client.get(f"/api/projects/{project_id}/summary")
    assert unauthorized_resp.status_code == 401


def test_add_member_and_access_as_member(client: TestClient):
    owner_id, owner_token = _register_and_token(client, "owner_member@example.com", "secret123")
    member_id, member_token = _register_and_token(client, "member@example.com", "secret123")
    headers_owner = {"Authorization": f"Bearer {owner_token}"}
    headers_member = {"Authorization": f"Bearer {member_token}"}
    assert owner_id != member_id

    project_resp = client.post(
        "/api/projects",
        json={"name": "With member", "description": None},
        headers=headers_owner,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    add_resp = client.post(
        f"/api/projects/{project_id}/members",
        json={"email": "member@example.com", "role": "editor"},
        headers=headers_owner,
    )
    assert add_resp.status_code == 201
    add_body = add_resp.json()
    assert add_body["user"]["email"] == "member@example.com"
    assert add_body["role"] == "editor"

    detail_member = client.get(f"/api/projects/{project_id}", headers=headers_member)
    assert detail_member.status_code == 200

    summary_member = client.get(f"/api/projects/{project_id}/summary", headers=headers_member)
    assert summary_member.status_code == 200


def test_non_owner_cannot_add_member(client: TestClient):
    owner_id, owner_token = _register_and_token(client, "owner_only@example.com", "secret123")
    other_id, other_token = _register_and_token(client, "stranger@example.com", "secret123")
    headers_owner = {"Authorization": f"Bearer {owner_token}"}
    headers_other = {"Authorization": f"Bearer {other_token}"}
    assert owner_id != other_id

    project_resp = client.post(
        "/api/projects",
        json={"name": "No add", "description": None},
        headers=headers_owner,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    add_resp = client.post(
        f"/api/projects/{project_id}/members",
        json={"email": "owner_only@example.com", "role": "editor"},
        headers=headers_other,
    )
    assert add_resp.status_code == 403


def test_list_members(client: TestClient):
    owner_id, owner_token = _register_and_token(client, "owner_list@example.com", "secret123")
    member_id, member_token = _register_and_token(client, "member_list@example.com", "secret123")
    headers_owner = {"Authorization": f"Bearer {owner_token}"}
    headers_member = {"Authorization": f"Bearer {member_token}"}
    assert owner_id != member_id

    project_resp = client.post(
        "/api/projects",
        json={"name": "List members", "description": None},
        headers=headers_owner,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    add_resp = client.post(
        f"/api/projects/{project_id}/members",
        json={"email": "member_list@example.com", "role": "editor"},
        headers=headers_owner,
    )
    assert add_resp.status_code == 201

    list_resp = client.get(f"/api/projects/{project_id}/members", headers=headers_owner)
    assert list_resp.status_code == 200
    members = list_resp.json()
    assert any(m["user"]["email"] == "member_list@example.com" for m in members)

    list_resp_member = client.get(f"/api/projects/{project_id}/members", headers=headers_member)
    assert list_resp_member.status_code == 200


def test_remove_member(client: TestClient):
    owner_id, owner_token = _register_and_token(client, "owner_remove@example.com", "secret123")
    member_id, member_token = _register_and_token(client, "member_remove@example.com", "secret123")
    headers_owner = {"Authorization": f"Bearer {owner_token}"}
    headers_member = {"Authorization": f"Bearer {member_token}"}
    assert owner_id != member_id

    project_resp = client.post(
        "/api/projects",
        json={"name": "Remove member", "description": None},
        headers=headers_owner,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    add_resp = client.post(
        f"/api/projects/{project_id}/members",
        json={"email": "member_remove@example.com", "role": "editor"},
        headers=headers_owner,
    )
    assert add_resp.status_code == 201

    delete_resp = client.delete(f"/api/projects/{project_id}/members/{member_id}", headers=headers_owner)
    assert delete_resp.status_code == 204

    list_resp = client.get(f"/api/projects/{project_id}/members", headers=headers_owner)
    assert list_resp.status_code == 200
    assert all(m["user"]["email"] != "member_remove@example.com" for m in list_resp.json())

    forbidden_detail = client.get(f"/api/projects/{project_id}", headers=headers_member)
    assert forbidden_detail.status_code == 403


def test_project_dashboard_empty(client: TestClient):
    user_id, token = _register_and_token(client, "dash-empty@example.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    project_resp = client.post(
        "/api/projects",
        json={"name": "Dash Empty", "description": None},
        headers=headers,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    resp = client.get(f"/api/projects/{project_id}/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["project"]["id"] == project_id
    assert body["flowsheet_versions"] == []
    assert body["scenarios"] == []
    assert body["recent_calc_runs"] == []
    assert body["recent_comments"] == []
    assert body["summary"]["flowsheet_versions_total"] == 0
    assert body["summary"]["calc_runs_total"] == 0
    assert body["summary"]["comments_total"] == 0
    assert body["summary"]["last_activity_at"] is None


def test_project_dashboard_with_data(client: TestClient):
    user_id, token = _register_and_token(client, "dash-data@example.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    project_resp = client.post(
        "/api/projects",
        json={"name": "Dash Data", "description": "desc"},
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
            "name": "Dash Scenario",
            "default_input_json": {"feed_tph": 120, "target_p80_microns": 160},
        },
    )
    assert scenario_resp.status_code == 201
    scenario_id = scenario_resp.json()["id"]

    run_resp = client.post(f"/api/calc/flowsheet-run/by-scenario/{scenario_id}")
    assert run_resp.status_code in (200, 201)
    run_id = run_resp.json()["id"]

    comment_resp1 = client.post(
        f"/api/calc-scenarios/{scenario_id}/comments/me",
        json={"text": "Scenario dash comment"},
        headers=headers,
    )
    assert comment_resp1.status_code in (200, 201)
    comment_resp2 = client.post(
        f"/api/calc-runs/{run_id}/comments/me",
        json={"text": "Run dash comment"},
        headers=headers,
    )
    assert comment_resp2.status_code in (200, 201)

    resp = client.get(f"/api/projects/{project_id}/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["flowsheet_versions"]) >= 1
    assert len(body["scenarios"]) >= 1
    assert len(body["recent_calc_runs"]) >= 1
    assert len(body["recent_comments"]) >= 1
    assert body["summary"]["flowsheet_versions_total"] >= len(body["flowsheet_versions"])
    assert body["summary"]["calc_runs_total"] >= len(body["recent_calc_runs"])
    assert body["summary"]["comments_total"] >= len(body["recent_comments"])


def test_project_dashboard_access_for_member(client: TestClient):
    owner_id, owner_token = _register_and_token(client, "dash-owner@example.com", "secret123")
    member_id, member_token = _register_and_token(client, "dash-member@example.com", "secret123")
    other_id, other_token = _register_and_token(client, "dash-other@example.com", "secret123")
    headers_owner = {"Authorization": f"Bearer {owner_token}"}
    headers_member = {"Authorization": f"Bearer {member_token}"}
    headers_other = {"Authorization": f"Bearer {other_token}"}

    project_resp = client.post(
        "/api/projects",
        json={"name": "Dash Access", "description": None},
        headers=headers_owner,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    add_resp = client.post(
        f"/api/projects/{project_id}/members",
        json={"email": "dash-member@example.com", "role": "editor"},
        headers=headers_owner,
    )
    assert add_resp.status_code == 201

    resp_owner = client.get(f"/api/projects/{project_id}/dashboard", headers=headers_owner)
    assert resp_owner.status_code == 200

    resp_member = client.get(f"/api/projects/{project_id}/dashboard", headers=headers_member)
    assert resp_member.status_code == 200

    resp_other = client.get(f"/api/projects/{project_id}/dashboard", headers=headers_other)
    assert resp_other.status_code == 403


def test_project_dashboard_unauthorized(client: TestClient):
    resp = client.get("/api/projects/00000000-0000-0000-0000-000000000000/dashboard")
    assert resp.status_code == 401
