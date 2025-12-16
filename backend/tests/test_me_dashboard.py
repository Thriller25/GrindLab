from fastapi.testclient import TestClient

from .test_grind_mvp_calc import _build_payload


def test_me_dashboard(client: TestClient):
    # register and login
    email = "dash@example.com"
    password = "secret123"
    reg_resp = client.post(
        "/api/auth/register",
        json={"email": email, "full_name": "Dash User", "password": password},
    )
    assert reg_resp.status_code in (200, 201)
    token_resp = client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = _build_payload(plant_id=1, flowsheet_version_id=1)
    run_resp = client.post("/api/calc/grind-mvp-runs", json=payload, headers=headers)
    assert run_resp.status_code == 200
    run_id = run_resp.json()["calc_run_id"]

    update_resp = client.put(
        f"/api/calc/grind-mvp-runs/{run_id}/comment", json={"comment": "Dashboard comment"}, headers=headers
    )
    assert update_resp.status_code == 200

    resp = client.get("/api/me/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "user" in body
    assert "summary" in body
    assert "recent_calc_runs" in body
    assert "recent_comments" in body
    assert "projects" in body
    assert "member_projects" in body
    assert body["user"]["email"] == email
    summary = body["summary"]
    assert isinstance(summary["calc_runs_total"], (int, float))
    assert isinstance(summary["scenarios_total"], (int, float))
    assert isinstance(summary["comments_total"], (int, float))
    assert isinstance(summary["projects_total"], (int, float))
    assert summary["comments_total"] == 1
