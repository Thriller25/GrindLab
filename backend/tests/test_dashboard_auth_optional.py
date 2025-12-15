from app.core.settings import settings


def test_dashboard_without_token_when_auth_disabled(client):
    original = settings.auth_enabled
    settings.auth_enabled = False
    try:
        resp = client.get("/api/me/dashboard")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user"]["email"] in ("anonymous@grindlab.local", "anon", "Anonymous")
        assert body["summary"]["calc_runs_total"] == 0
        assert body["projects"] == []
    finally:
        settings.auth_enabled = original
