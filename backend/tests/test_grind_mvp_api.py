from fastapi.testclient import TestClient

from app.schemas.grind_mvp import GrindMvpResult
from .utils import create_flowsheet, create_flowsheet_version, create_plant
from .test_grind_mvp_calc import _auth_headers, _build_payload


def test_grind_mvp_api_returns_200(client: TestClient):
    """
    Integration check for POST /api/calc/grind-mvp-runs with valid payload.
    Ensures no internal calculation error is raised.
    """
    headers = _auth_headers(client, "grind-api@example.com")
    # For grind MVP we allow integer ids from UI; no need to pre-create entities here.
    payload = _build_payload(plant_id=1, flowsheet_version_id=1)
    resp = client.post("/api/calc/grind-mvp-runs", json=payload, headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "calc_run_id" in body
    assert "result" in body
    GrindMvpResult.model_validate(body["result"])


def test_update_grind_mvp_run_comment(client: TestClient):
    headers = _auth_headers(client, "grind-comment@example.com")
    payload = _build_payload(plant_id=1, flowsheet_version_id=1)

    create_resp = client.post("/api/calc/grind-mvp-runs", json=payload, headers=headers)
    assert create_resp.status_code == 200
    run_id = create_resp.json()["calc_run_id"]

    new_comment = "Повышена производительность, проверяем энергоёмкость"
    update_resp = client.put(
        f"/api/calc/grind-mvp-runs/{run_id}/comment", json={"comment": new_comment}, headers=headers
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated.get("comment") == new_comment

    detail_resp = client.get(f"/api/calc/grind-mvp-runs/{run_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json().get("comment") == new_comment
