import uuid

from fastapi.testclient import TestClient

from .utils import create_flowsheet, create_flowsheet_version, create_plant


def _create_runs(client: TestClient, flowsheet_version_id: str, count: int = 2) -> list[str]:
    run_ids: list[str] = []
    for i in range(count):
        resp = client.post(
            "/api/calc/flowsheet-run",
            json={
                "flowsheet_version_id": flowsheet_version_id,
                "scenario_name": f"Scenario {i}",
                "input_json": {"feed_tph": 100 + i * 10, "target_p80_microns": 140 + i * 5},
            },
        )
        assert resp.status_code in (200, 201)
        run_ids.append(resp.json()["id"])
    return run_ids


def test_create_and_get_calc_comparison(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    run_ids = _create_runs(client, flowsheet_version_id, count=3)[:2]

    payload = {
        "flowsheet_version_id": flowsheet_version_id,
        "name": "Energy vs baseline",
        "description": "Test comparison",
        "run_ids": run_ids,
    }
    create_resp = client.post("/api/calc-comparisons", json=payload)
    assert create_resp.status_code in (200, 201)
    created = create_resp.json()
    comparison_id = created["id"]
    assert created["name"] == payload["name"]
    assert created["flowsheet_version_id"] == flowsheet_version_id
    assert set(created["run_ids"]) == set(run_ids)

    detail_resp = client.get(f"/api/calc-comparisons/{comparison_id}")
    assert detail_resp.status_code == 200
    detail_body = detail_resp.json()
    assert detail_body["comparison"]["name"] == payload["name"]
    assert detail_body["runs"]["total"] == len(run_ids)
    returned_ids = {item["id"] for item in detail_body["runs"]["items"]}
    assert returned_ids == set(run_ids)


def test_calc_comparisons_list_by_flowsheet_version(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    run_ids = _create_runs(client, flowsheet_version_id, count=2)

    for idx in range(2):
        resp = client.post(
            "/api/calc-comparisons",
            json={
                "flowsheet_version_id": flowsheet_version_id,
                "name": f"Comparison {idx}",
                "description": None,
                "run_ids": run_ids,
            },
        )
        assert resp.status_code in (200, 201)

    list_resp = client.get(f"/api/calc-comparisons/by-flowsheet-version/{flowsheet_version_id}")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    names = {item["name"] for item in body["items"]}
    assert names == {"Comparison 0", "Comparison 1"}


def test_calc_comparison_invalid_run_ids(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    version_1 = create_flowsheet_version(client, flowsheet_id)
    version_2 = create_flowsheet_version(client, flowsheet_id)

    run_id = _create_runs(client, version_1, count=1)[0]

    payload = {
        "flowsheet_version_id": version_2,
        "name": "Invalid comparison",
        "run_ids": [run_id],
    }
    resp = client.post("/api/calc-comparisons", json=payload)
    assert resp.status_code == 400
    assert "does not belong to flowsheet version" in resp.json()["detail"]
