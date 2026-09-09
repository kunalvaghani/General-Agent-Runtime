import json

from typer.testing import CliRunner

from gar.cli.app import app


def test_cli_write_read(monkeypatch, tmp_path):
    monkeypatch.setenv("GAR_DATA_DIR", str(tmp_path / "data"))
    runner = CliRunner()
    task = json.loads(runner.invoke(app, ["task-create", "Tool test", "test"]).output)
    arguments = tmp_path / "input.json"
    arguments.write_text(json.dumps({"path": "example.txt", "content": "hello"}))
    result = runner.invoke(app, ["tool", task["id"], "filesystem.write", str(arguments)])
    assert result.exit_code == 0, result.output
    arguments.write_text(json.dumps({"path": "example.txt"}))
    result = runner.invoke(app, ["tool", task["id"], "filesystem.read", str(arguments)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["output"] == "hello"
