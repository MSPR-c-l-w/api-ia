import os

import pytest

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("BACKEND_API_KEY", "test-api-key")


@pytest.fixture
def client():
    from app.main import app

    app.config["TESTING"] = True
    return app.test_client()
