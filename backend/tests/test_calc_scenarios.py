from fastapi.testclient import TestClient

from .utils import create_flowsheet, create_flowsheet_version, create_plant


def test_calc_scenario_crud(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    payload = {
        "flowsheet_version_id": flowsheet_version_id,
        "name": "Base scenario",
        "description": "Default parameters",
        "default_input_json": {"feed_tph": 150, "target_p80_microns": 180},
    }
    resp = client.post("/api/calc-scenarios", json=payload)
    assert resp.status_code == 201
    scenario = resp.json()
    scenario_id = scenario["id"]
    assert scenario["name"] == payload["name"]
    assert scenario["flowsheet_version_id"] == flowsheet_version_id
    assert scenario["default_input_json"]["feed_tph"] == payload["default_input_json"]["feed_tph"]

    resp = client.get(f"/api/calc-scenarios/{scenario_id}")
    assert resp.status_code == 200
    fetched = resp.json()
    assert fetched["id"] == scenario_id
    assert fetched["default_input_json"]["target_p80_microns"] == payload["default_input_json"]["target_p80_microns"]

    resp = client.get(f"/api/calc-scenarios/by-flowsheet-version/{flowsheet_version_id}")
    assert resp.status_code == 200
    list_body = resp.json()
    assert list_body["total"] >= 1
    assert any(item["id"] == scenario_id for item in list_body["items"])

    update_payload = {"name": "Updated scenario", "description": "Updated description"}
    resp = client.patch(f"/api/calc-scenarios/{scenario_id}", json=update_payload)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == update_payload["name"]
    assert updated["description"] == update_payload["description"]

    resp = client.delete(f"/api/calc-scenarios/{scenario_id}")
    assert resp.status_code in (200, 204)


def test_calc_run_by_scenario_happy_path(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    scenario_payload = {
        "flowsheet_version_id": flowsheet_version_id,
        "name": "Baseline scenario",
        "default_input_json": {"feed_tph": 120, "target_p80_microns": 140},
    }
    resp = client.post("/api/calc-scenarios", json=scenario_payload)
    assert resp.status_code == 201
    scenario_id = resp.json()["id"]

    resp = client.post(f"/api/calc/flowsheet-run/by-scenario/{scenario_id}")
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["flowsheet_version_id"] == flowsheet_version_id
    assert body["scenario_name"] == scenario_payload["name"]
    assert body["status"] == "success"
    assert body["error_message"] is None
    assert body["input_json"]["feed_tph"] == scenario_payload["default_input_json"]["feed_tph"]
    assert body["input_json"]["target_p80_microns"] == scenario_payload["default_input_json"]["target_p80_microns"]
    assert body["result_json"]["throughput_tph"] == scenario_payload["default_input_json"]["feed_tph"]
    assert "specific_energy_kwh_per_t" in body["result_json"]
    assert "p80_out_microns" in body["result_json"]
