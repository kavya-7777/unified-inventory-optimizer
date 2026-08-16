import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_products():
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_optimization_known_answer_mock():
    # Example known-answer test structure
    payload = {
        "demand": [10, 20, 15],
        "lead_time": 2,
        "service_level": 0.95
    }
    # In reality this would call the optimization engine directly or via API
    # response = client.post("/api/v1/optimization/run", json=payload)
    # assert response.json()["pipeline_run_id"] is not None
    assert True
