import pytest
from fastapi.testclient import TestClient

from gateway.app import app

client = TestClient(app)


def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_predict_invalid_json():
    response = client.post(
        "/v1/predict",
        content="invalid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_predict_unknown_fields():
    response = client.post(
        "/v1/predict",
        json={"inputs": ["hello"], "unknown_field": "bad"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_predict_invalid_inputs_count():
    response = client.post(
        "/v1/predict",
        json={"inputs": []},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_predict_invalid_model_version():
    response = client.post(
        "/v1/predict",
        json={"inputs": ["hello"], "model_version": "invalid-v999"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_MODEL"
