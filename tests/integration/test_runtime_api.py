from fastapi.testclient import TestClient

from gar.api.app import create_app
from gar.config import Settings


def test_task_api_validation_cancel_and_sse(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        assert client.post("/api/v1/tasks", json={"goal": "", "model": "m"}).status_code == 422
        created = client.post("/api/v1/tasks", json={"goal": "test", "model": "m", "start": False})
        assert created.status_code == 201
        task_id = created.json()["id"]
        assert client.get(f"/api/v1/tasks/{task_id}/plan").json() is None
        assert (
            client.post(
                f"/api/v1/tasks/{task_id}/approve", json={"request_id": "bad", "approve": True}
            ).status_code
            == 409
        )
        assert client.post(f"/api/v1/tasks/{task_id}/cancel").json()["status"] == "CANCELLED"
        stream = client.get(f"/api/v1/tasks/{task_id}/events").text
        assert "task.cancelled" in stream and "event: end" in stream
        assert client.get("/api/v1/tasks/missing").status_code == 404
        assert (
            client.post(
                "/api/v1/tasks", headers={"Origin": "https://evil.test"}, json={}
            ).status_code
            == 403
        )
        assert client.patch("/api/v1/settings", json={"model_timeout": -1}).status_code == 422
        assert client.patch("/api/v1/settings", json={"default_model": "m"}).status_code == 200
