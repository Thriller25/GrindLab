import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal

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
    assert attach_resp.status_code in (200, 201)

    detail_resp = client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail_body = detail_resp.json()
    assert detail_body["owner_user_id"] == user_id
    assert detail_body["flowsheet_versions"]
    first_link = detail_body["flowsheet_versions"][0]
    assert first_link["flowsheet_version_id"] == flowsheet_version_id
    assert first_link["flowsheet_name"] == "Test Flowsheet"
    assert first_link["flowsheet_version_label"] == "v1"
    assert first_link["model_name"] == "grind_mvp_v1"
    assert first_link["plant_id"] == plant_id
    assert first_link["id"] is not None


def test_attach_and_detach_flowsheet_version(client: TestClient):
    user_id, token = _register_and_token(client, "cycle@example.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    project_resp = client.post(
        "/api/projects",
        json={"name": "Cycle", "description": None},
        headers=headers,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    first_attach = client.post(
        f"/api/projects/{project_id}/flowsheet-versions/{flowsheet_version_id}",
        headers=headers,
    )
    assert first_attach.status_code in (200, 201)
    second_attach = client.post(
        f"/api/projects/{project_id}/flowsheet-versions/{flowsheet_version_id}",
        headers=headers,
    )
    assert second_attach.status_code in (200, 201)

    detail_resp = client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert len(detail_resp.json()["flowsheet_versions"]) == 1

    delete_resp = client.delete(
        f"/api/projects/{project_id}/flowsheet-versions/{flowsheet_version_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204
    delete_again = client.delete(
        f"/api/projects/{project_id}/flowsheet-versions/{flowsheet_version_id}",
        headers=headers,
    )
    assert delete_again.status_code == 204

    detail_after = client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_after.status_code == 200
    assert detail_after.json()["flowsheet_versions"] == []


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
    assert resp.status_code in (401, 404)


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
    assert attach_resp.status_code in (200, 201)

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


def test_list_grind_mvp_runs_by_project_and_flowsheet_version(client: TestClient):
    user_id, token = _register_and_token(client, "list-runs@example.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    version_a = create_flowsheet_version(client, flowsheet_id)
    version_b = create_flowsheet_version(client, flowsheet_id)

    project_resp = client.post(
        "/api/projects",
        json={"name": "Runs project", "description": None, "plant_id": plant_id},
        headers=headers,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    # create runs for version_a
    payload = {
        "model_version": "grind_mvp_v1",
        "plant_id": plant_id,
        "flowsheet_version_id": version_a,
        "project_id": project_id,
        "scenario_name": "S1",
        "feed": {"tonnage_tph": 500.0, "p80_mm": 12.0, "density_t_per_m3": 2.7},
        "mill": {
            "type": "SAG",
            "power_installed_kw": 8000.0,
            "power_draw_kw": 7200.0,
            "ball_charge_percent": 12.0,
            "speed_percent_critical": 75.0,
        },
        "classifier": {
            "type": "cyclone",
            "cut_size_p80_mm": 0.18,
            "circulating_load_percent": 250.0,
        },
        "options": {"use_baseline_run_id": None},
    }
    resp1 = client.post("/api/calc/grind-mvp-runs", json=payload, headers=headers)
    assert resp1.status_code == 200
    resp2 = client.post("/api/calc/grind-mvp-runs", json=payload, headers=headers)
    assert resp2.status_code == 200

    # another run with different version should not appear
    payload_other = dict(payload, flowsheet_version_id=version_b)
    other_resp = client.post("/api/calc/grind-mvp-runs", json=payload_other, headers=headers)
    assert other_resp.status_code == 200

    list_resp = client.get(
        f"/api/projects/{project_id}/flowsheet-versions/{version_a}/grind-mvp-runs",
        headers=headers,
    )
    assert list_resp.status_code == 200
    runs = list_resp.json()
    assert len(runs) == 2
    ids = [r["id"] for r in runs]
    # newest first
    assert ids[0] == resp2.json()["calc_run_id"]
    assert runs[0]["project_id"] == project_id
    assert str(runs[0]["flowsheet_version_id"]) == str(version_a)


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
    assert attach_resp.status_code in (200, 201)

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


def _make_calc_run(
    flowsheet_version_id: int,
    project_id: int | None,
    throughput: float,
    p80_mm: float,
    specific_energy: float,
    circulating_load: float,
    is_baseline: bool = False,
) -> str:
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    run = models.CalcRun(
        id=run_id,
        flowsheet_version_id=flowsheet_version_id,
        project_id=project_id,
        scenario_name="demo",
        status="success",
        started_at=now,
        finished_at=now,
        baseline_run_id=run_id if is_baseline else None,
        input_json={
            "model_version": "grind_mvp_v1",
            "plant_id": 1,
            "flowsheet_version_id": flowsheet_version_id,
            "scenario_name": "demo",
        },
        result_json={
            "model_version": "grind_mvp_v1",
            "kpi": {
                "throughput_tph": throughput,
                "product_p80_mm": p80_mm,
                "specific_energy_kwh_per_t": specific_energy,
                "circulating_load_percent": circulating_load,
                "mill_utilization_percent": 90.0,
            },
        },
    )
    with SessionLocal() as db:
        db.add(run)
        db.commit()
    return run_id


def test_project_detail_flowsheet_summaries_with_best_and_diff(client: TestClient):
    user_id, token = _register_and_token(client, "summary-best@example.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    project_resp = client.post(
        "/api/projects",
        json={"name": "Summary Project", "description": None, "plant_id": plant_id},
        headers=headers,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    attach_resp = client.post(
        f"/api/projects/{project_id}/flowsheet-versions/{flowsheet_version_id}",
        headers=headers,
    )
    assert attach_resp.status_code in (200, 201)

    baseline_id = _make_calc_run(
        flowsheet_version_id=int(flowsheet_version_id),
        project_id=None,
        throughput=500.0,
        p80_mm=0.2,
        specific_energy=13.0,
        circulating_load=250.0,
        is_baseline=True,
    )
    worse_id = _make_calc_run(
        flowsheet_version_id=int(flowsheet_version_id),
        project_id=int(project_id),
        throughput=510.0,
        p80_mm=0.19,
        specific_energy=13.5,
        circulating_load=260.0,
    )
    best_id = _make_calc_run(
        flowsheet_version_id=int(flowsheet_version_id),
        project_id=int(project_id),
        throughput=520.0,
        p80_mm=0.18,
        specific_energy=12.0,
        circulating_load=255.0,
    )

    detail_resp = client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    summaries = body.get("flowsheet_summaries", [])
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["baseline_run"]["id"] == baseline_id
    assert summary["best_project_run"]["id"] == best_id

    diff = summary["diff_vs_baseline"]
    assert diff is not None
    assert diff["throughput_tph_delta"] == 20.0
    assert diff["specific_energy_kwhpt_delta"] == -1.0


def test_project_detail_flowsheet_summaries_without_project_runs(client: TestClient):
    user_id, token = _register_and_token(client, "summary-empty-runs@example.com", "secret123")
    headers = {"Authorization": f"Bearer {token}"}

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    project_resp = client.post(
        "/api/projects",
        json={"name": "Summary No Runs", "description": None, "plant_id": plant_id},
        headers=headers,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    attach_resp = client.post(
        f"/api/projects/{project_id}/flowsheet-versions/{flowsheet_version_id}",
        headers=headers,
    )
    assert attach_resp.status_code in (200, 201)

    baseline_id = _make_calc_run(
        flowsheet_version_id=int(flowsheet_version_id),
        project_id=None,
        throughput=480.0,
        p80_mm=0.21,
        specific_energy=13.8,
        circulating_load=245.0,
        is_baseline=True,
    )

    detail_resp = client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_resp.status_code == 200
    summary = detail_resp.json()["flowsheet_summaries"][0]
    assert summary["baseline_run"]["id"] == baseline_id
    assert summary["best_project_run"] is None
    assert summary["diff_vs_baseline"] is None
    assert summary["has_runs"] is False
