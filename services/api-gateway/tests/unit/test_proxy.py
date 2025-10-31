import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from api_gateway.main import app

client = TestClient(app)

@pytest.mark.asyncio
@patch("api_gateway.main.proxy_request", new_callable=AsyncMock)
async def test_chat_proxy(mock_proxy_request):
    mock_proxy_request.return_value = JSONResponse(
        content={"message": "success"},
        status_code=200
    )

    response = client.post("/api/v1/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json() == {"message": "success"}
