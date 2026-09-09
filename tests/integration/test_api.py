from fastapi.testclient import TestClient

from gar import __version__
from gar.api.app import create_app
from gar.config import Settings


def test_health_and_openapi():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "gar", "version": __version__}
        assert "/api/v1/health" in client.get("/openapi.json").json()["paths"]
        assert client.get("/api/v1/tasks").status_code == 200


def test_factories_have_independent_settings():
    first = create_app(Settings(port=8100))
    second = create_app(Settings(port=8200))
    assert first.state.settings.port == 8100
    assert second.state.settings.port == 8200
