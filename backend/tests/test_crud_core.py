from fastapi.testclient import TestClient

from .utils import create_flowsheet, create_flowsheet_version, create_plant


def test_plant_crud(client: TestClient):
    # create
    plant_payload = {"name": "Plant A", "code": "PA-001", "company": "ACME", "is_active": True}
    resp = client.post("/api/plants/", json=plant_payload)
    assert resp.status_code == 201
    plant = resp.json()
    plant_id = plant["id"]
    assert plant["name"] == plant_payload["name"]

    # read by id
    resp = client.get(f"/api/plants/{plant_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == plant_id

    # list
    resp = client.get("/api/plants/")
    assert resp.status_code == 200
    assert any(item["id"] == plant_id for item in resp.json()["items"])

    # update
    update_payload = {"name": "Plant A Updated"}
    resp = client.put(f"/api/plants/{plant_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Plant A Updated"

    # delete
    resp = client.delete(f"/api/plants/{plant_id}")
    assert resp.status_code in (200, 204)

    # optional read after delete
    resp = client.get(f"/api/plants/{plant_id}")
    assert resp.status_code in (200, 404, 410)


def test_flowsheet_crud(client: TestClient):
    plant_id = create_plant(client)

    # create
    fs_payload = {
        "plant_id": plant_id,
        "name": "Flowsheet A",
        "description": "desc",
        "status": "DRAFT",
    }
    resp = client.post("/api/flowsheets/", json=fs_payload)
    assert resp.status_code == 201
    fs = resp.json()
    fs_id = fs["id"]
    assert fs["plant_id"] == plant_id

    # read by id
    resp = client.get(f"/api/flowsheets/{fs_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == fs_id

    # list
    resp = client.get("/api/flowsheets/")
    assert resp.status_code == 200
    assert any(item["id"] == fs_id for item in resp.json()["items"])

    # update
    update_payload = {"name": "Flowsheet A Updated"}
    resp = client.put(f"/api/flowsheets/{fs_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Flowsheet A Updated"

    # delete
    resp = client.delete(f"/api/flowsheets/{fs_id}")
    assert resp.status_code in (200, 204)

    # optional read after delete
    resp = client.get(f"/api/flowsheets/{fs_id}")
    assert resp.status_code in (200, 404, 410)


def test_flowsheet_version_crud(client: TestClient):
    plant_id = create_plant(client)
    fs_id = create_flowsheet(client, plant_id)

    # create
    fsv_payload = {
        "flowsheet_id": fs_id,
        "version_label": "v1",
        "status": "DRAFT",
        "is_active": True,
        "comment": "initial",
    }
    resp = client.post("/api/flowsheet-versions/", json=fsv_payload)
    assert resp.status_code == 201
    fsv = resp.json()
    fsv_id = fsv["id"]
    assert fsv["flowsheet_id"] == fs_id

    # read by id
    resp = client.get(f"/api/flowsheet-versions/{fsv_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == fsv_id

    # list
    resp = client.get("/api/flowsheet-versions/")
    assert resp.status_code == 200
    assert any(item["id"] == fsv_id for item in resp.json()["items"])

    # update
    update_payload = {"version_label": "v1.1"}
    resp = client.put(f"/api/flowsheet-versions/{fsv_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["version_label"] == "v1.1"

    # delete
    resp = client.delete(f"/api/flowsheet-versions/{fsv_id}")
    assert resp.status_code in (200, 204)

    # optional read after delete
    resp = client.get(f"/api/flowsheet-versions/{fsv_id}")
    assert resp.status_code in (200, 404, 410)


def test_unit_crud(client: TestClient):
    plant_id = create_plant(client)
    fs_id = create_flowsheet(client, plant_id)
    fsv_id = create_flowsheet_version(client, fs_id)

    # create
    unit_payload = {
        "flowsheet_version_id": fsv_id,
        "name": "Crusher 1",
        "unit_type": "CRUSHER",
        "is_active": True,
    }
    resp = client.post("/api/units/", json=unit_payload)
    assert resp.status_code == 201
    unit = resp.json()
    unit_id = unit["id"]
    assert unit["flowsheet_version_id"] == fsv_id

    # read by id
    resp = client.get(f"/api/units/{unit_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == unit_id

    # list
    resp = client.get("/api/units/")
    assert resp.status_code == 200
    assert any(item["id"] == unit_id for item in resp.json()["items"])

    # update
    update_payload = {"name": "Crusher 1 Updated"}
    resp = client.put(f"/api/units/{unit_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Crusher 1 Updated"

    # delete
    resp = client.delete(f"/api/units/{unit_id}")
    assert resp.status_code in (200, 204)

    # optional read after delete
    resp = client.get(f"/api/units/{unit_id}")
    assert resp.status_code in (200, 404, 410)
