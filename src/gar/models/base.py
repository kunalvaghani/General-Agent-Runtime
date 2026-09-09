"""Provider-neutral contracts. Tool calls are data, never executable actions."""

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelError(Exception):
    """Safe, user-visible provider error with no raw response content."""


class ModelUnavailable(ModelError):
    pass


class ModelTimeout(ModelError):
    pass


class ModelNotFound(ModelError):
    pass


class InvalidModelResponse(ModelError):
    pass


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Message(Contract):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ToolDefinition(Contract):
    name: str = Field(min_length=1)
    description: str
    parameters: dict[str, Any]


class ToolProposal(Contract):
    name: str = Field(min_length=1)
    arguments: dict[str, Any]


class Generation(Contract):
    model: str
    content: str
    tool_calls: list[ToolProposal] = Field(default_factory=list)


class ModelProfile(Contract):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    local: bool = False
    context_window: int = Field(default=0, ge=0)
    coding: bool | None = None
    vision: bool | None = None
    cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ModelAdapter(ABC):
    provider: str

    @abstractmethod
    async def discover(self) -> list[ModelProfile]: ...

    @abstractmethod
    async def health(self) -> bool: ...

    @abstractmethod
    async def generate(
        self,
        model: str,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> Generation: ...
