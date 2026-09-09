from fastapi.testclient import TestClient

from gar.api.app import create_app
from gar.config import Settings
from gar.core.events import EventType


def test_snapshot_journal_and_origin(tmp_path):
    with TestClient(
        create_app(Settings(data_dir=tmp_path, web_origin="http://127.0.0.1:3100"))
    ) as client:
        task = client.post(
            "/api/v1/tasks", json={"goal": "snapshot", "model": "m", "start": False}
        ).json()
        path = f"/api/v1/tasks/{task['id']}"
        view = client.get(path + "/snapshot").json()
        assert view["task"]["id"] == task["id"] and view["plan"] is None
        assert view["events"][0]["event"] == "task.created"
        client.post(path + "/cancel")
        view = client.get(path + "/snapshot").json()
        assert view["task"]["status"] == "CANCELLED"
        assert view["events"][-1]["event"] == "task.cancelled"
        assert client.get("/api/v1/tasks/missing/snapshot").status_code == 404
        assert client.get(path, headers={"Origin": "http://127.0.0.1:3100"}).status_code == 200
        assert client.get(path, headers={"Origin": "https://untrusted.example"}).status_code == 403


def test_exact_code_and_approval_arguments_survive_persistence(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        repo = client.app.state.runtime.repo
        task = client.post(
            "/api/v1/tasks", json={"goal": "whitespace", "model": "m", "start": False}
        ).json()
        current = repo.get(task["id"])
        payload = {"code": "  preserve indentation\n\n", "output": " result \n"}
        repo.checkpoint(
            current.id,
            {"metadata": {"payload": payload}},
            current.version,
            EventType.MODEL_RESPONDED,
            payload,
        )
        snapshot = client.get(f"/api/v1/tasks/{current.id}/snapshot").json()
        assert snapshot["task"]["metadata"]["payload"] == payload
        assert snapshot["events"][-1]["data"] == payload
