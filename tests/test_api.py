"""HTTP API contract tests using FastAPI's TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_model_info(client: TestClient):
    response = client.get("/model")
    assert response.status_code == 200
    body = response.json()
    assert body["version"].startswith("m_")
    assert "roc_auc" in body["metadata"]["metrics"]


def test_score_valid_applicant(client: TestClient, applicant: dict):
    response = client.post("/score", json=applicant)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"] in {"approve", "review", "decline"}
    assert body["anchor"]["anchored"] is True
    assert len(body["reasons"]) >= 1


def test_score_rejects_invalid_region(client: TestClient, applicant: dict):
    bad = {**applicant, "region": "narnia"}
    response = client.post("/score", json=bad)
    assert response.status_code == 422


def test_score_rejects_underage(client: TestClient, applicant: dict):
    bad = {**applicant, "age": 15}
    response = client.post("/score", json=bad)
    assert response.status_code == 422


def test_fetch_and_verify_decision(client: TestClient, applicant: dict):
    decision_id = client.post("/score", json=applicant).json()["decision_id"]

    fetched = client.get(f"/decisions/{decision_id}")
    assert fetched.status_code == 200
    assert fetched.json()["decision_id"] == decision_id

    verified = client.get(f"/decisions/{decision_id}/verify")
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"


def test_unknown_decision_is_404(client: TestClient):
    assert client.get("/decisions/nope").status_code == 404
    assert client.get("/decisions/nope/verify").status_code == 404
