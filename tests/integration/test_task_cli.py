import json

from typer.testing import CliRunner

from gar.cli.app import app


def test_task_cli_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("GAR_DATA_DIR", str(tmp_path / "data"))
    runner = CliRunner()
    created = runner.invoke(app, ["task-create", "Record a goal", "test-model"])
    assert created.exit_code == 0, created.output
    task = json.loads(created.output)
    assert task["status"] == "PENDING"
    assert not (tmp_path / "data" / "workspaces").exists()
    assert json.loads(runner.invoke(app, ["tasks"]).output)[0]["id"] == task["id"]
    assert runner.invoke(app, ["cancel", task["id"]]).exit_code == 0
    detail = json.loads(runner.invoke(app, ["task", task["id"]]).output)
    assert detail["task"]["status"] == "CANCELLED"
    assert len(detail["events"]) == 2
    assert runner.invoke(app, ["cancel", task["id"]]).exit_code == 1
    assert runner.invoke(app, ["task", "missing"]).exit_code == 1
