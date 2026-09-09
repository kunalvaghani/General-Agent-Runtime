import httpx
from typer.testing import CliRunner

from gar.cli.app import app
from gar.models.ollama import OllamaAdapter
from gar.models.registry import ModelRegistry


def test_model_cli_flow(monkeypatch, tmp_path):
    def respond(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "test"}]})
        return httpx.Response(
            200,
            json={
                "model": "test",
                "done": True,
                "message": {"role": "assistant", "content": "hello [literal]"},
            },
        )

    def registry(settings):
        result = ModelRegistry()
        result.register(OllamaAdapter(transport=httpx.MockTransport(respond)))
        return result

    monkeypatch.setattr("gar.cli.models.make_registry", registry)
    monkeypatch.setenv("GAR_CONFIG_DIR", str(tmp_path))
    runner = CliRunner()
    for arguments in (["models"], ["models", "refresh"], ["use", "test"]):
        result = runner.invoke(app, arguments)
        assert result.exit_code == 0, result.output
        assert "test" in result.output
    result = runner.invoke(app, ["ask", "hello"])
    assert result.exit_code == 0, result.output
    assert "hello [literal]" in result.output
    result = runner.invoke(app, ["use", "unknown"])
    assert result.exit_code == 1
    assert "not installed" in result.output


def test_no_selection_and_bad_config(monkeypatch, tmp_path):
    monkeypatch.setenv("GAR_CONFIG_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(app, ["ask", "hello"])
    assert result.exit_code == 1
    assert "Choose a model" in result.output
    monkeypatch.setenv("GAR_MODEL_TIMEOUT", "secret-invalid")
    result = runner.invoke(app, ["models"])
    assert result.exit_code == 2
    assert "secret-invalid" not in result.output
