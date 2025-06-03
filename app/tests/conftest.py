# app/tests/conftest.py
import pytest
import os
from fastapi.testclient import TestClient
import asyncio

# Set test environment variables
os.environ["GOOGLE_API_KEY"] = ""
os.environ["INCLUDE_REASONING"] = "false"
os.environ["LOG_LEVEL"] = "DEBUG"

@pytest.fixture(scope="session")
def event_loop():
    "Create an instance of the default event loop for the test session."
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()