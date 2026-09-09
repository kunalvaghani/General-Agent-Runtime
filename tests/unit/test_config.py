import pytest
from pydantic import ValidationError

from gar.config import Settings


def test_defaults():
    settings = Settings()
    assert (settings.host, settings.port, settings.log_level) == ("127.0.0.1", 8000, "INFO")


def test_config_precedence(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("GAR_PORT=8100\nGAR_LOG_LEVEL=WARNING\n", encoding="utf-8")
    assert Settings().port == 8100
    monkeypatch.setenv("GAR_PORT", "8200")
    assert Settings().port == 8200
    assert Settings(port=8300).port == 8300
    assert Settings().log_level == "WARNING"


@pytest.mark.parametrize("value", ["0", "65536", "invalid"])
def test_invalid_port(monkeypatch, value):
    monkeypatch.setenv("GAR_PORT", value)
    with pytest.raises(ValidationError):
        Settings()


def test_rejects_public_bind():
    with pytest.raises(ValidationError):
        Settings(host="0.0.0.0")


def test_invalid_log_level(monkeypatch):
    monkeypatch.setenv("GAR_LOG_LEVEL", "NOISY")
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "3601"])
def test_invalid_model_timeout(monkeypatch, value):
    monkeypatch.setenv("GAR_MODEL_TIMEOUT", value)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "value",
    [
        "file:///tmp/a",
        "http://user:pass@localhost:11434",
        "http://localhost:11434?token=secret",
        "http://localhost:11434/#fragment",
    ],
)
def test_invalid_provider_url(monkeypatch, value):
    monkeypatch.setenv("GAR_OLLAMA_URL", value)
    with pytest.raises(ValidationError):
        Settings()
