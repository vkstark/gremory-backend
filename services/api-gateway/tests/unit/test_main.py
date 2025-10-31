import pytest
from fastapi.testclient import TestClient
from api_gateway.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "API Gateway - Microservices Architecture",
        "docs": "/docs",
        "available_apis": {
            "chat": "/api/v1/chat",
            "user_history": "/api/v1/user",
            "users": "/api/v1/users",
            "personalization": "/api/v1/personalization",
            "ext_tools": "/api/v1/tools",
            "models": "/api/v1/models",
            "health": "/health"
        },
        "services": {
            "chat-inference": "http://chat-inference:8002",
            "user-history": "http://user-history:8001",
            "user-profile": "http://user-profile:8003",
            "personalization": "http://personalization:8004",
            "ext-tools": "http://ext-tools:8005"
        }
    }
