"""Validated API and model settings; no filesystem side effects."""

from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Explicit values override environment, then .env, then defaults."""

    model_config = SettingsConfigDict(
        env_prefix="GAR_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    host: Literal["127.0.0.1", "localhost", "::1"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    ollama_url: HttpUrl = HttpUrl("http://127.0.0.1:11434")
    model_timeout: float = Field(default=120, gt=0, le=3600, allow_inf_nan=False)
    config_dir: Path = Path.home() / ".gar"
    default_model: str | None = None
    data_dir: Path = Path("data")
    web_origin: HttpUrl = HttpUrl("http://127.0.0.1:3000")

    @field_validator("web_origin")
    @classmethod
    def validate_web_origin(cls, value: HttpUrl) -> HttpUrl:
        if (
            value.host not in ("localhost", "127.0.0.1", "[::1]")
            or value.scheme != "http"
            or value.username
            or value.password
            or value.query
            or value.fragment
            or value.path not in (None, "/")
        ):
            raise ValueError("Web origin must be a loopback HTTP origin")
        return value

    @field_validator("ollama_url")
    @classmethod
    def validate_endpoint(cls, value: HttpUrl) -> HttpUrl:
        if value.username or value.password or value.query or value.fragment:
            raise ValueError("Ollama URL must not contain credentials, query or fragment")
        return value
