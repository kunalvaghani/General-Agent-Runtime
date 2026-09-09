from typer.testing import CliRunner

from gar import __version__
from gar.cli.app import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.output


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_serve_uses_validated_config(monkeypatch):
    calls = []
    monkeypatch.setattr("gar.cli.app.uvicorn.run", lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.setenv("GAR_PORT", "8123")
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0
    assert calls == [{"host": "127.0.0.1", "port": 8123, "log_level": "info"}]


def test_invalid_config_does_not_leak_value(monkeypatch):
    monkeypatch.setenv("GAR_PORT", "sensitive-invalid-value")
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 2
    assert "port" in result.output
    assert "sensitive-invalid-value" not in result.output
