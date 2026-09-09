"""Ollama HTTP adapter with bounded requests and validated response envelopes."""

import asyncio
import json
from typing import Any, Literal

import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from referencing import Registry
from referencing.exceptions import Unresolvable

from gar.models.base import (
    Generation,
    InvalidModelResponse,
    Message,
    ModelAdapter,
    ModelError,
    ModelNotFound,
    ModelProfile,
    ModelTimeout,
    ModelUnavailable,
    ToolDefinition,
    ToolProposal,
)


class WireModel(BaseModel):
    # Ollama may add metadata; known fields must retain their exact types.
    model_config = ConfigDict(strict=True)


class Tag(WireModel):
    name: str = Field(min_length=1)


class Tags(WireModel):
    models: list[Tag]


class Function(WireModel):
    name: str = Field(min_length=1)
    arguments: dict[str, Any]


class ToolCall(WireModel):
    function: Function


class Reply(WireModel):
    role: Literal["assistant"]
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)


class Chat(WireModel):
    model: str = Field(min_length=1)
    message: Reply
    done: Literal[True]


class OllamaAdapter(ModelAdapter):
    provider = "ollama"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 120,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.transport = transport

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            async with asyncio.timeout(self.timeout):
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout,
                    transport=self.transport,
                    trust_env=False,
                    follow_redirects=False,
                ) as client:
                    response = await client.request(method, path, **kwargs)
            if response.status_code == 404 and path == "api/chat":
                raise ModelNotFound("Ollama model was not found; run gar models refresh.")
            if not response.is_success:
                raise ModelUnavailable(f"Ollama returned HTTP {response.status_code}.")
            data = response.json()
            if not isinstance(data, dict) or "error" in data:
                raise InvalidModelResponse("Ollama returned an invalid response envelope.")
            return data
        except (TimeoutError, httpx.TimeoutException):
            raise ModelTimeout("Ollama request timed out.") from None
        except httpx.RequestError:
            raise ModelUnavailable(
                "Cannot reach Ollama; check the service and GAR_OLLAMA_URL."
            ) from None
        except ValueError:
            raise InvalidModelResponse("Ollama returned invalid JSON.") from None

    async def discover(self) -> list[ModelProfile]:
        data = await self._request("GET", "api/tags")
        try:
            tags = Tags.model_validate(data)
        except ValidationError:
            raise InvalidModelResponse("Ollama returned an invalid model list.") from None
        return [
            ModelProfile(id=name, provider=self.provider)
            for name in sorted({tag.name for tag in tags.models})
        ]

    async def health(self) -> bool:
        try:
            await self.discover()
            return True
        except ModelError:
            return False

    async def generate(
        self,
        model: str,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> Generation:
        if not model.strip() or not messages:
            raise ValueError("A model and at least one message are required")
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.model_dump() for message in messages],
            "stream": False,
        }
        if tools is not None:
            payload["tools"] = [
                {"type": "function", "function": tool.model_dump()} for tool in tools
            ]
        if response_schema is not None:
            try:
                Draft202012Validator.check_schema(response_schema)
            except SchemaError:
                raise ValueError("Invalid response schema") from None
            payload["format"] = response_schema
        data = await self._request("POST", "api/chat", json=payload)
        try:
            chat = Chat.model_validate(data)
        except ValidationError:
            raise InvalidModelResponse("Ollama returned an invalid chat response.") from None
        if not chat.message.content.strip() and not chat.message.tool_calls:
            raise InvalidModelResponse("Ollama returned an empty answer.")
        if response_schema is not None and not chat.message.tool_calls:
            try:
                value = json.loads(chat.message.content)
                # An empty registry prevents fetching external schema references.
                Draft202012Validator(response_schema, registry=Registry()).validate(value)
            except (ValueError, SchemaValidationError, Unresolvable):
                raise InvalidModelResponse(
                    "Model output does not match the response schema."
                ) from None
        return Generation(
            model=chat.model,
            content=chat.message.content,
            tool_calls=[
                ToolProposal(**call.function.model_dump()) for call in chat.message.tool_calls
            ],
        )
