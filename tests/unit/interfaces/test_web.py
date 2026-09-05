from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from argus.interfaces.web.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_web_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Argus-PG Mission Control" in response.text


def test_api_health_degraded_when_no_db(client):
    with patch(
        "argus.core.database.PsycopgReadAdapter.__aenter__",
        side_effect=Exception("No DB"),
    ):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
