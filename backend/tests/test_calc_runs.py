import uuid

from fastapi.testclient import TestClient
from pytest import approx

from .utils import create_flowsheet, create_flowsheet_version, create_plant


def _register_and_token(
    client: TestClient, email: str, password: str = "secret123"
) -> tuple[str, str]:
    client.post(
        "/api/auth/register", json={"email": email, "password": password, "full_name": "Test User"}
    )
    token_resp = client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
    )
    assert token_resp.status_code == 200
    return email, token_resp.json()["access_token"]


def test_calc_run_happy_path(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    calc_payload = {
        "flowsheet_version_id": flowsheet_version_id,
        "scenario_name": "Baseline",
        "comment": "Run 1",
        "input_json": {"feed_tph": 100, "target_p80_microns": 150},
    }
    resp = client.post("/api/calc/flowsheet-run", json=calc_payload)
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["flowsheet_version_id"] == flowsheet_version_id
    assert body["scenario_id"] is None
    assert body["status"] == "success"
    assert body["error_message"] is None
    assert body["input_json"]["feed_tph"] == 100
    assert body["input_json"]["target_p80_microns"] == 150
    assert body["result_json"]["throughput_tph"] == 100
    assert body["result_json"]["p80_out_microns"] == 150
    assert "specific_energy_kwh_per_t" in body["result_json"]
    assert body["started_at"] is not None
    assert body["finished_at"] is not None


def test_calc_run_not_found_flowsheet_version(client: TestClient):
    missing_id = "11111111-1111-1111-1111-111111111111"
    resp = client.post(
        "/api/calc/flowsheet-run",
        json={
            "flowsheet_version_id": missing_id,
            "input_json": {"feed_tph": 100, "target_p80_microns": 150},
        },
    )
    assert resp.status_code == 404
    assert missing_id in resp.json()["detail"]


def test_calc_run_invalid_input_json(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    resp = client.post(
        "/api/calc/flowsheet-run",
        json={
            "flowsheet_version_id": flowsheet_version_id,
            "input_json": {"feed_tph": 100},
        },
    )

    assert resp.status_code == 422

    body = resp.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)


def test_get_calc_runs_list(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    # Create two runs
    for scenario in ["Baseline", "Alt"]:
        resp = client.post(
            "/api/calc/flowsheet-run",
            json={
                "flowsheet_version_id": flowsheet_version_id,
                "scenario_name": scenario,
                "input_json": {"feed_tph": 120, "target_p80_microns": 160},
            },
        )
        assert resp.status_code in (200, 201)

    resp = client.get(f"/api/calc-runs/by-flowsheet-version/{flowsheet_version_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2
    assert any(item.get("scenario_name") for item in body["items"])
    for item in body["items"]:
        assert "scenario_id" in item
        assert "feed_tph" in item["input_json"]
        assert "throughput_tph" in item["result_json"]


def test_compare_calc_runs(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    run_ids = []
    inputs = [
        {"feed_tph": 100, "target_p80_microns": 140},
        {"feed_tph": 150, "target_p80_microns": 180},
    ]
    for input_json in inputs:
        resp = client.post(
            "/api/calc/flowsheet-run",
            json={
                "flowsheet_version_id": flowsheet_version_id,
                "scenario_name": "Scenario compare",
                "input_json": input_json,
            },
        )
        assert resp.status_code in (200, 201)
        run_ids.append(resp.json()["id"])

    compare_resp = client.get(
        "/api/calc-runs/compare",
        params=[("run_ids", rid) for rid in run_ids],
    )
    assert compare_resp.status_code == 200
    compare_body = compare_resp.json()

    assert compare_body["total"] == 2
    assert len(compare_body["items"]) == 2
    returned_ids = {item["id"] for item in compare_body["items"]}
    assert set(run_ids) == returned_ids

    item_map = {item["id"]: item for item in compare_body["items"]}
    for rid, input_json in zip(run_ids, inputs):
        item = item_map[rid]
        assert item["status"] == "success"
        assert item["input"]["feed_tph"] == input_json["feed_tph"]
        assert item["input"]["target_p80_microns"] == input_json["target_p80_microns"]
        assert item["result"] is not None
        assert "throughput_tph" in item["result"]
        assert "specific_energy_kwh_per_t" in item["result"]
        assert "p80_out_microns" in item["result"]


def test_compare_calc_runs_not_found(client: TestClient):
    random_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    compare_resp = client.get(
        "/api/calc-runs/compare",
        params=[("run_ids", rid) for rid in random_ids],
    )
    assert compare_resp.status_code == 404
    assert "No calc runs found" in compare_resp.json()["detail"]


def test_compare_with_baseline(client: TestClient):
    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    baseline_resp = client.post(
        "/api/calc/flowsheet-run",
        json={
            "flowsheet_version_id": flowsheet_version_id,
            "scenario_name": "Baseline",
            "input_json": {"feed_tph": 100, "target_p80_microns": 150},
        },
    )
    assert baseline_resp.status_code in (200, 201)
    baseline_body = baseline_resp.json()
    baseline_id = baseline_body["id"]
    baseline_result = baseline_body["result_json"]

    compare_runs = [
        {"feed_tph": 120, "target_p80_microns": 140},
        {"feed_tph": 80, "target_p80_microns": 160},
    ]
    run_ids = []
    run_results = []
    for payload in compare_runs:
        resp = client.post(
            "/api/calc/flowsheet-run",
            json={
                "flowsheet_version_id": flowsheet_version_id,
                "scenario_name": "Compare",
                "input_json": payload,
            },
        )
        assert resp.status_code in (200, 201)
        body = resp.json()
        run_ids.append(body["id"])
        run_results.append(body["result_json"])

    resp = client.get(
        "/api/calc-runs/compare-with-baseline",
        params=[("baseline_run_id", baseline_id)] + [("run_ids", rid) for rid in run_ids],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["baseline"]["id"] == baseline_id
    assert body["total"] == len(run_ids)
    assert len(body["items"]) == len(run_ids)

    item_map = {item["run"]["id"]: item for item in body["items"]}
    for rid, run_result in zip(run_ids, run_results):
        item = item_map[rid]
        deltas = item["deltas"]
        expected_throughput_delta = run_result["throughput_tph"] - baseline_result["throughput_tph"]
        expected_p80_delta = run_result["p80_out_microns"] - baseline_result["p80_out_microns"]
        assert deltas["throughput_delta_abs"] == approx(expected_throughput_delta)
        assert deltas["p80_out_delta_abs"] == approx(expected_p80_delta)
        assert deltas["throughput_delta_pct"] == approx(
            expected_throughput_delta / baseline_result["throughput_tph"] * 100.0
        )
        assert deltas["p80_out_delta_pct"] == approx(
            expected_p80_delta / baseline_result["p80_out_microns"] * 100.0
        )


def test_compare_with_baseline_invalid_ids(client: TestClient):
    resp = client.get(
        "/api/calc-runs/compare-with-baseline",
        params=[("baseline_run_id", str(uuid.uuid4())), ("run_ids", str(uuid.uuid4()))],
    )
    assert resp.status_code == 404


def test_run_and_save_with_flowsheet_nodes(client: TestClient):
    """Test F5.3 run-and-save endpoint with flowsheet nodes/edges"""
    _, token = _register_and_token(client, "run-and-save@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    plant_id = create_plant(client)
    flowsheet_id = create_flowsheet(client, plant_id)
    flowsheet_version_id = create_flowsheet_version(client, flowsheet_id)

    # Minimal flowsheet: Feed -> Product
    nodes = [
        {
            "id": "feed-1",
            "type": "feed",
            "data": {
                "type": "feed",
                "label": "Руда",
                "parameters": {"tph": 100, "solids_pct": 100, "f80_mm": 150},
            },
        },
        {
            "id": "product-1",
            "type": "product",
            "data": {
                "type": "product",
                "label": "Продукт",
                "parameters": {},
            },
        },
    ]

    edges = [
        {
            "id": "e1",
            "source": "feed-1",
            "target": "product-1",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
    ]

    payload = {
        "flowsheet_version_id": flowsheet_version_id,
        "project_id": None,
        "scenario_id": None,
        "scenario_name": "Test Run",
        "comment": "Testing run-and-save",
        "nodes": nodes,
        "edges": edges,
    }

    resp = client.post("/api/calc-runs/run-and-save", json=payload, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["flowsheet_version_id"] == flowsheet_version_id
    assert body["scenario_name"] == "Test Run"
    assert body["status"] in ("success", "error")
    assert "id" in body
    assert body["result_json"] is not None
    assert "global_kpi" in body["result_json"]
