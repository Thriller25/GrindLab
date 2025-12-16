from fastapi.testclient import TestClient


def test_me_dashboard_anonymous(client: TestClient):
    resp = client.get("/api/me/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"]
    assert body["summary"]["calc_runs_total"] == 0
    assert body["summary"]["projects_total"] == 0
    assert body["projects"] == []
    assert body["member_projects"] == []
