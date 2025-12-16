from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.db import SessionLocal


def test_mapper_config_and_projects_endpoint(client: TestClient):
    configure_mappers()
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))

    resp = client.get("/api/projects/my")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body


def test_projects_demo_seed_and_list_anonymous(client: TestClient):
    resp_empty = client.get("/api/projects/my")
    assert resp_empty.status_code == 200
    empty_body = resp_empty.json()
    assert empty_body["items"] == []
    assert empty_body["total"] == 0

    seed_resp = client.post("/api/projects/demo-seed")
    assert seed_resp.status_code == 200
    seeded = seed_resp.json()
    assert seeded["id"]
    assert seeded["name"]

    resp_after = client.get("/api/projects/my")
    assert resp_after.status_code == 200
    after_body = resp_after.json()
    assert after_body["total"] >= 1
    assert any(item["id"] == seeded["id"] for item in after_body["items"])
