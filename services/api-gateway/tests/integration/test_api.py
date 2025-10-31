import pytest
from fastapi.testclient import TestClient
from api_gateway.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["service"] == "api-gateway"
    assert "services" in json_response
