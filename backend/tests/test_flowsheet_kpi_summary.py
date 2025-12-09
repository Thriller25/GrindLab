from fastapi.testclient import TestClient
from pytest import approx

from .utils import create_flowsheet, create_flowsheet_version, create_plant


def test_flowsheet_version_kpi_summary(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    scenario_payloads = [
        {
            "flowsheet_version_id": flowsheet_version_id,
            "name": "Baseline",
            "default_input_json": {"feed_tph": 100, "target_p80_microns": 150},
        },
        {
            "flowsheet_version_id": flowsheet_version_id,
            "name": "High throughput",
            "default_input_json": {"feed_tph": 130, "target_p80_microns": 140},
        },
    ]
    scenario_ids = []
    for payload in scenario_payloads:
        resp = client.post("/api/calc-scenarios", json=payload)
        assert resp.status_code == 201
        scenario_ids.append(resp.json()["id"])

    runs_values_all = []
    per_scenario_values: dict[str, list[float]] = {sid: [] for sid in scenario_ids}

    for sid, feed_tph in zip(scenario_ids, [100, 120]):
        for offset in [0, 10]:
            resp = client.post(
                f"/api/calc/flowsheet-run/by-scenario/{sid}",
                json={"input_json": {"feed_tph": feed_tph + offset, "target_p80_microns": 150 - offset}},
            )
            assert resp.status_code in (200, 201)
            result = resp.json()["result_json"]
            runs_values_all.append(result["throughput_tph"])
            per_scenario_values[sid].append(result["throughput_tph"])

    resp = client.get(f"/api/flowsheet-versions/{flowsheet_version_id}/kpi-summary")
    assert resp.status_code == 200
    body = resp.json()

    assert body["flowsheet_version_id"] == flowsheet_version_id
    assert body["totals"]["count_runs"] == 4
    assert body["totals"]["throughput_tph_min"] == min(runs_values_all)
    assert body["totals"]["throughput_tph_max"] == max(runs_values_all)
    assert body["totals"]["throughput_tph_avg"] == approx(sum(runs_values_all) / len(runs_values_all))

    assert len(body["by_scenario"]) == 2
    by_id = {item["scenario_id"]: item for item in body["by_scenario"]}
    for sid in scenario_ids:
        scen = by_id[sid]
        values = per_scenario_values[sid]
        assert scen["kpi"]["count_runs"] == len(values)
        assert scen["kpi"]["throughput_tph_min"] == min(values)
        assert scen["kpi"]["throughput_tph_max"] == max(values)
        assert scen["kpi"]["throughput_tph_avg"] == approx(sum(values) / len(values))


def test_flowsheet_version_kpi_summary_no_runs(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    resp = client.get(f"/api/flowsheet-versions/{flowsheet_version_id}/kpi-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["flowsheet_version_id"] == flowsheet_version_id
    assert body["totals"]["count_runs"] == 0
    assert body["by_scenario"] == []
