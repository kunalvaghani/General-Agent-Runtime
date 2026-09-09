"""Strict tool contracts and normalized results."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Risk(StrEnum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    DANGEROUS = "DANGEROUS"
    PROHIBITED = "PROHIBITED"


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PathInput(ToolInput):
    path: str = Field(default=".", min_length=1, max_length=4096)


class WriteInput(PathInput):
    content: str = Field(max_length=1_000_000)


class CommandInput(ToolInput):
    argv: list[str] = Field(min_length=1, max_length=30)


class PythonInput(ToolInput):
    code: str = Field(min_length=1, max_length=100_000)


class EmptyInput(ToolInput):
    pass


class ToolResult(BaseModel):
    call_id: str
    tool: str
    status: str
    output: str = ""
    exit_code: int | None = None
    error: str | None = None
    truncated: bool = False


class ToolSpec(BaseModel):
    name: str
    description: str
    risk: Risk
    input_schema: dict[str, Any]


class ToolFailure(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
