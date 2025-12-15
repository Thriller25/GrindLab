import uuid

from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.schemas.grind_mvp import GrindMvpResult
from .utils import create_flowsheet, create_flowsheet_version, create_plant


def _auth_headers(client: TestClient, email: str) -> dict:
    password = "secret123"
    reg_resp = client.post(
        "/api/auth/register",
        json={"email": email, "full_name": "User", "password": password},
    )
    assert reg_resp.status_code in (200, 201)
    token_resp = client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _build_payload(plant_id: str, flowsheet_version_id: str):
    return {
        "model_version": "grind_mvp_v1",
        "plant_id": plant_id,
        "flowsheet_version_id": flowsheet_version_id,
        "scenario_name": "Base case",
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


def test_grind_mvp_run_happy_path(client: TestClient):
    headers = _auth_headers(client, "grind-happy@example.com")
    plant_id = 1
    flowsheet_version_id = 1

    payload = _build_payload(plant_id, flowsheet_version_id)
    resp = client.post("/api/calc/grind-mvp-runs", json=payload, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "calc_run_id" in body
    result = body.get("result")
    assert result is not None
    GrindMvpResult.model_validate(result)  # validation

    kpi = result.get("kpi")
    assert kpi is not None
    assert isinstance(kpi.get("throughput_tph"), (int, float))
    assert isinstance(kpi.get("product_p80_mm"), (int, float))
    assert isinstance(kpi.get("specific_energy_kwh_per_t"), (int, float))
    assert isinstance(kpi.get("circulating_load_percent"), (int, float))
    assert isinstance(kpi.get("mill_utilization_percent"), (int, float))

    size_dist = result.get("size_distribution")
    assert size_dist is not None
    assert "feed" in size_dist and "product" in size_dist

    run_id = uuid.UUID(body["calc_run_id"])
    with SessionLocal() as session:
        run = session.get(models.CalcRun, run_id)
        assert run is not None
        assert run.input_json["model_version"] == "grind_mvp_v1"
        assert run.result_json["model_version"] == "grind_mvp_v1"


def test_grind_mvp_validation_errors(client: TestClient):
    headers = _auth_headers(client, "grind-invalid@example.com")
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    payload_missing = _build_payload(plant_id, flowsheet_version_id)
    payload_missing.pop("feed")
    resp_missing = client.post("/api/calc/grind-mvp-runs", json=payload_missing, headers=headers)
    assert resp_missing.status_code == 422

    payload_negative = _build_payload(plant_id, flowsheet_version_id)
    payload_negative["feed"]["tonnage_tph"] = -100.0
    resp_negative = client.post("/api/calc/grind-mvp-runs", json=payload_negative, headers=headers)
    assert resp_negative.status_code == 422


def test_list_grind_mvp_runs(client: TestClient):
    headers = _auth_headers(client, "grind-list@example.com")

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)
    payload = _build_payload(plant_id, flowsheet_version_id)

    resp = client.post("/api/calc/grind-mvp-runs", json=payload, headers=headers)
    assert resp.status_code == 200
    run_id = resp.json()["calc_run_id"]

    resp_list = client.get("/api/calc/grind-mvp-runs?limit=10", headers=headers)
    assert resp_list.status_code == 200
    runs = resp_list.json()
    assert len(runs) >= 1
    assert any(run["id"] == run_id for run in runs)
    assert all(run["model_version"] == "grind_mvp_v1" for run in runs)
    assert "throughput_tph" in runs[0]


def test_get_grind_mvp_run_detail(client: TestClient):
    headers = _auth_headers(client, "grind-detail@example.com")

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)
    payload = _build_payload(plant_id, flowsheet_version_id)

    resp = client.post("/api/calc/grind-mvp-runs", json=payload, headers=headers)
    assert resp.status_code == 200
    run_id = resp.json()["calc_run_id"]

    resp_detail = client.get(f"/api/calc/grind-mvp-runs/{run_id}", headers=headers)
    assert resp_detail.status_code == 200
    body = resp_detail.json()
    assert body["id"] == run_id
    assert "input" in body
    assert body["input"]["feed"]["tonnage_tph"] == payload["feed"]["tonnage_tph"]
    assert body["result"]["kpi"]["throughput_tph"] > 0


def test_grind_mvp_baseline_comparison(client: TestClient):
    headers = _auth_headers(client, "grind-baseline@example.com")

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    base_payload = _build_payload(plant_id, flowsheet_version_id)
    resp_base = client.post("/api/calc/grind-mvp-runs", json=base_payload, headers=headers)
    assert resp_base.status_code == 200
    baseline_run_id = resp_base.json()["calc_run_id"]
    base_throughput = resp_base.json()["result"]["kpi"]["throughput_tph"]

    new_payload = _build_payload(plant_id, flowsheet_version_id)
    new_payload["feed"]["tonnage_tph"] = base_payload["feed"]["tonnage_tph"] * 1.1
    new_payload["options"]["use_baseline_run_id"] = baseline_run_id

    resp_new = client.post("/api/calc/grind-mvp-runs", json=new_payload, headers=headers)
    assert resp_new.status_code == 200
    body = resp_new.json()
    comparison = body["result"]["baseline_comparison"]
    assert comparison is not None
    assert comparison["baseline_run_id"] == baseline_run_id
    assert comparison["throughput_delta_tph"] is not None
    assert comparison["throughput_delta_tph"] > 0
    assert body["result"]["kpi"]["throughput_tph"] > base_throughput
