import uuid

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
    assert scenario["is_baseline"] is False

    resp = client.get(f"/api/calc-scenarios/{scenario_id}")
    assert resp.status_code == 200
    fetched = resp.json()
    assert fetched["id"] == scenario_id
    assert fetched["default_input_json"]["target_p80_microns"] == payload["default_input_json"]["target_p80_microns"]
    assert fetched["is_baseline"] is False

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
    assert body["scenario_id"] == scenario_id
    assert body["status"] == "success"
    assert body["error_message"] is None
    assert body["input_json"]["feed_tph"] == scenario_payload["default_input_json"]["feed_tph"]
    assert body["input_json"]["target_p80_microns"] == scenario_payload["default_input_json"]["target_p80_microns"]
    assert body["result_json"]["throughput_tph"] == scenario_payload["default_input_json"]["feed_tph"]
    assert "specific_energy_kwh_per_t" in body["result_json"]
    assert "p80_out_microns" in body["result_json"]

    list_resp = client.get(
        f"/api/calc-runs/by-flowsheet-version/{flowsheet_version_id}",
        params={"scenario_id": scenario_id},
    )
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["total"] == 1
    assert len(list_body["items"]) == 1
    assert list_body["items"][0]["scenario_id"] == scenario_id


def test_get_latest_calc_run_by_scenario(client: TestClient):
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

    first_resp = client.post(f"/api/calc/flowsheet-run/by-scenario/{scenario_id}")
    assert first_resp.status_code in (200, 201)

    second_resp = client.post(f"/api/calc/flowsheet-run/by-scenario/{scenario_id}")
    assert second_resp.status_code in (200, 201)
    latest_run_id = second_resp.json()["id"]

    latest_resp = client.get(f"/api/calc-runs/latest/by-scenario/{scenario_id}")
    assert latest_resp.status_code == 200
    latest_body = latest_resp.json()
    assert latest_body["scenario_id"] == scenario_id
    assert latest_body["id"] == latest_run_id

    latest_success_resp = client.get(
        f"/api/calc-runs/latest/by-scenario/{scenario_id}", params={"status": "success"}
    )
    assert latest_success_resp.status_code == 200
    assert latest_success_resp.json()["id"] == latest_run_id


def test_get_latest_calc_run_by_scenario_not_found(client: TestClient):
    random_scenario_id = uuid.uuid4()
    resp = client.get(f"/api/calc-runs/latest/by-scenario/{random_scenario_id}")
    assert resp.status_code == 404


def test_flowsheet_version_overview_with_scenarios_and_latest_runs(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    scenario_payloads = [
        {
            "flowsheet_version_id": flowsheet_version_id,
            "name": "Scenario A",
            "default_input_json": {"feed_tph": 100, "target_p80_microns": 130},
        },
        {
            "flowsheet_version_id": flowsheet_version_id,
            "name": "Scenario B",
            "default_input_json": {"feed_tph": 200, "target_p80_microns": 160},
        },
    ]
    scenario_ids = []
    for payload in scenario_payloads:
        resp = client.post("/api/calc-scenarios", json=payload)
        assert resp.status_code == 201
        scenario_ids.append(resp.json()["id"])

    scenario_id_1, scenario_id_2 = scenario_ids

    first_run_resp = client.post(f"/api/calc/flowsheet-run/by-scenario/{scenario_id_1}")
    assert first_run_resp.status_code in (200, 201)
    second_run_resp = client.post(f"/api/calc/flowsheet-run/by-scenario/{scenario_id_1}")
    assert second_run_resp.status_code in (200, 201)
    latest_run_scenario_1_id = second_run_resp.json()["id"]

    scenario_2_run_resp = client.post(f"/api/calc/flowsheet-run/by-scenario/{scenario_id_2}")
    assert scenario_2_run_resp.status_code in (200, 201)
    scenario_2_run_id = scenario_2_run_resp.json()["id"]

    overview_resp = client.get(f"/api/flowsheet-versions/{flowsheet_version_id}/overview")
    assert overview_resp.status_code == 200
    overview_body = overview_resp.json()

    assert overview_body["flowsheet_version"]["id"] == flowsheet_version_id
    assert len(overview_body["scenarios"]) == 2

    scenario_map = {item["scenario"]["id"]: item for item in overview_body["scenarios"]}
    assert set(scenario_map.keys()) == set(scenario_ids)

    assert scenario_map[scenario_id_1]["scenario"]["flowsheet_version_id"] == flowsheet_version_id
    assert scenario_map[scenario_id_1]["latest_run"]["id"] == latest_run_scenario_1_id
    assert scenario_map[scenario_id_1]["latest_run"]["scenario_id"] == scenario_id_1

    assert scenario_map[scenario_id_2]["scenario"]["flowsheet_version_id"] == flowsheet_version_id
    assert scenario_map[scenario_id_2]["latest_run"]["id"] == scenario_2_run_id
    assert scenario_map[scenario_id_2]["latest_run"]["scenario_id"] == scenario_id_2


def test_clone_flowsheet_version_with_scenarios(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    original_version_id = create_flowsheet_version(client, flowsheet_id)

    scenario_payloads = [
        {
            "flowsheet_version_id": original_version_id,
            "name": "Original Scenario 1",
            "default_input_json": {"feed_tph": 111, "target_p80_microns": 150},
        },
        {
            "flowsheet_version_id": original_version_id,
            "name": "Original Scenario 2",
            "default_input_json": {"feed_tph": 222, "target_p80_microns": 175},
        },
    ]
    original_scenario_ids = []
    for payload in scenario_payloads:
        resp = client.post("/api/calc-scenarios", json=payload)
        assert resp.status_code == 201
        original_scenario_ids.append(resp.json()["id"])

    # Add calc runs to source version to ensure they are not copied
    resp_run_1 = client.post(f"/api/calc/flowsheet-run/by-scenario/{original_scenario_ids[0]}")
    assert resp_run_1.status_code in (200, 201)
    resp_run_2 = client.post(f"/api/calc/flowsheet-run/by-scenario/{original_scenario_ids[0]}")
    assert resp_run_2.status_code in (200, 201)

    clone_payload = {"new_version_name": "Cloned version 1", "clone_scenarios": True}
    clone_resp = client.post(f"/api/flowsheet-versions/{original_version_id}/clone", json=clone_payload)
    assert clone_resp.status_code == 201
    clone_body = clone_resp.json()

    cloned_version = clone_body["flowsheet_version"]
    cloned_scenarios = clone_body["scenarios"]

    assert cloned_version["id"] != original_version_id
    assert cloned_version["flowsheet_id"] == flowsheet_id
    assert cloned_version["version_label"] == clone_payload["new_version_name"]
    assert len(cloned_scenarios) == len(scenario_payloads)

    cloned_by_name = {s["name"]: s for s in cloned_scenarios}
    for payload in scenario_payloads:
        scenario = cloned_by_name[payload["name"]]
        assert scenario["flowsheet_version_id"] == cloned_version["id"]
        assert scenario["default_input_json"]["feed_tph"] == payload["default_input_json"]["feed_tph"]
        assert scenario["default_input_json"]["target_p80_microns"] == payload["default_input_json"]["target_p80_microns"]
        assert scenario["is_baseline"] is False

    scenarios_list_resp = client.get(f"/api/calc-scenarios/by-flowsheet-version/{cloned_version['id']}")
    assert scenarios_list_resp.status_code == 200
    scenarios_list_body = scenarios_list_resp.json()
    assert scenarios_list_body["total"] == len(scenario_payloads)

    runs_list_resp = client.get(f"/api/calc-runs/by-flowsheet-version/{cloned_version['id']}")
    assert runs_list_resp.status_code == 200
    runs_list_body = runs_list_resp.json()
    assert runs_list_body["total"] == 0
    assert runs_list_body["items"] == []


def test_clone_flowsheet_version_without_scenarios(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    original_version_id = create_flowsheet_version(client, flowsheet_id)

    payload = {
        "flowsheet_version_id": original_version_id,
        "name": "Scenario to skip",
        "default_input_json": {"feed_tph": 300, "target_p80_microns": 190},
    }
    resp = client.post("/api/calc-scenarios", json=payload)
    assert resp.status_code == 201

    clone_payload = {"new_version_name": "Cloned no scenarios", "clone_scenarios": False}
    clone_resp = client.post(f"/api/flowsheet-versions/{original_version_id}/clone", json=clone_payload)
    assert clone_resp.status_code == 201
    clone_body = clone_resp.json()

    cloned_version = clone_body["flowsheet_version"]
    cloned_scenarios = clone_body["scenarios"]

    assert cloned_version["id"] != original_version_id
    assert cloned_version["flowsheet_id"] == flowsheet_id
    assert cloned_version["version_label"] == clone_payload["new_version_name"]
    assert cloned_scenarios == []

    scenarios_list_resp = client.get(f"/api/calc-scenarios/by-flowsheet-version/{cloned_version['id']}")
    assert scenarios_list_resp.status_code == 200
    scenarios_list_body = scenarios_list_resp.json()
    assert scenarios_list_body["total"] == 0


def test_set_baseline_scenario_for_flowsheet_version(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    payloads = [
        {
            "flowsheet_version_id": flowsheet_version_id,
            "name": "Scenario Baseline 1",
            "default_input_json": {"feed_tph": 120, "target_p80_microns": 150},
        },
        {
            "flowsheet_version_id": flowsheet_version_id,
            "name": "Scenario Baseline 2",
            "default_input_json": {"feed_tph": 140, "target_p80_microns": 160},
        },
    ]
    scenario_ids = []
    for payload in payloads:
        resp = client.post("/api/calc-scenarios", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["is_baseline"] is False
        scenario_ids.append(body["id"])

    first_id, second_id = scenario_ids

    set_resp = client.post(f"/api/calc-scenarios/{first_id}/set-baseline")
    assert set_resp.status_code == 200
    assert set_resp.json()["is_baseline"] is True

    other_resp = client.get(f"/api/calc-scenarios/{second_id}")
    assert other_resp.status_code == 200
    assert other_resp.json()["is_baseline"] is False

    second_set_resp = client.post(f"/api/calc-scenarios/{second_id}/set-baseline")
    assert second_set_resp.status_code == 200
    assert second_set_resp.json()["is_baseline"] is True

    first_after_resp = client.get(f"/api/calc-scenarios/{first_id}")
    assert first_after_resp.status_code == 200
    assert first_after_resp.json()["is_baseline"] is False

    overview_resp = client.get(f"/api/flowsheet-versions/{flowsheet_version_id}/overview")
    assert overview_resp.status_code == 200
    overview_body = overview_resp.json()
    baselines = [item for item in overview_body["scenarios"] if item["scenario"]["is_baseline"]]
    assert len(baselines) == 1
    assert baselines[0]["scenario"]["id"] == second_id


def test_unset_baseline_scenario(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    payload = {
        "flowsheet_version_id": flowsheet_version_id,
        "name": "Scenario Baseline",
        "default_input_json": {"feed_tph": 180, "target_p80_microns": 200},
    }
    resp = client.post("/api/calc-scenarios", json=payload)
    assert resp.status_code == 201
    scenario_id = resp.json()["id"]

    set_resp = client.post(f"/api/calc-scenarios/{scenario_id}/set-baseline")
    assert set_resp.status_code == 200
    assert set_resp.json()["is_baseline"] is True

    unset_resp = client.post(f"/api/calc-scenarios/{scenario_id}/unset-baseline")
    assert unset_resp.status_code == 200
    assert unset_resp.json()["is_baseline"] is False

    overview_resp = client.get(f"/api/flowsheet-versions/{flowsheet_version_id}/overview")
    assert overview_resp.status_code == 200
    overview_body = overview_resp.json()
    baselines = [item for item in overview_body["scenarios"] if item["scenario"]["is_baseline"]]
    assert len(baselines) == 0
