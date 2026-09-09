import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from gar.models.base import (
    InvalidModelResponse,
    Message,
    ModelNotFound,
    ModelTimeout,
    ModelUnavailable,
    ToolDefinition,
)
from gar.models.ollama import OllamaAdapter
from gar.models.registry import ModelRegistry
from gar.models.selection import load_selection, save_selection


def adapter(handler, timeout=1):
    return OllamaAdapter(transport=httpx.MockTransport(handler), timeout=timeout)


def test_discovery_deduplicates_and_health():
    client = adapter(
        lambda r: httpx.Response(
            200, json={"models": [{"name": "z"}, {"name": "a"}, {"name": "z"}]}
        )
    )
    assert [p.id for p in asyncio.run(client.discover())] == ["a", "z"]
    assert asyncio.run(client.health())


def test_generate_wire_contract_and_tool_proposal():
    def respond(request):
        assert request.url.path == "/api/chat"
        data = json.loads(request.content)
        assert data["stream"] is False
        assert data["model"] == "test"
        assert data["format"] == {"type": "object"}
        assert data["tools"][0]["function"]["name"] == "read"
        return httpx.Response(
            200,
            json={
                "model": "test",
                "done": True,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "read", "arguments": {"path": "a.txt"}}}],
                },
            },
        )

    result = asyncio.run(
        adapter(respond).generate(
            "test",
            [Message(role="user", content="hello")],
            tools=[ToolDefinition(name="read", description="Read", parameters={"type": "object"})],
            response_schema={"type": "object"},
        )
    )
    assert result.tool_calls[0].arguments == {"path": "a.txt"}


@pytest.mark.parametrize(
    "body", [{}, {"models": "bad"}, {"models": [{"name": 12}]}, {"error": "secret"}, []]
)
def test_invalid_discovery(body):
    with pytest.raises(InvalidModelResponse):
        asyncio.run(adapter(lambda r: httpx.Response(200, json=body)).discover())


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"model": "test", "done": False, "message": {"role": "assistant", "content": "hi"}},
        {"model": "test", "done": True, "message": {"role": "user", "content": "hi"}},
        {"model": "test", "done": True, "message": {"role": "assistant", "content": ""}},
        {"model": "test", "done": True, "message": {"role": "assistant", "content": 2}},
    ],
)
def test_invalid_generation(body):
    with pytest.raises(InvalidModelResponse):
        asyncio.run(
            adapter(lambda r: httpx.Response(200, json=body)).generate(
                "test", [Message(role="user", content="hi")]
            )
        )


def test_invalid_json():
    with pytest.raises(InvalidModelResponse):
        asyncio.run(adapter(lambda r: httpx.Response(200, text="not json")).discover())


@pytest.mark.parametrize("code", [301, 401, 429, 500])
def test_http_failure_does_not_echo_body(code):
    with pytest.raises(ModelUnavailable) as error:
        asyncio.run(adapter(lambda r: httpx.Response(code, text="private-data")).discover())
    assert "private-data" not in str(error.value)


def test_missing_model():
    with pytest.raises(ModelNotFound):
        asyncio.run(
            adapter(lambda r: httpx.Response(404)).generate(
                "missing", [Message(role="user", content="hi")]
            )
        )


@pytest.mark.parametrize(
    "exception, expected",
    [
        (httpx.ConnectError("secret"), ModelUnavailable),
        (httpx.ReadTimeout("secret"), ModelTimeout),
    ],
)
def test_transport_errors(exception, expected):
    def fail(request):
        raise exception

    with pytest.raises(expected):
        asyncio.run(adapter(fail).discover())
    assert not asyncio.run(adapter(fail).health())


def test_absolute_deadline():
    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json={"models": []})

    with pytest.raises(ModelTimeout):
        asyncio.run(adapter(slow, timeout=0.01).discover())


def test_cancellation_propagates():
    async def cancelled(request):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(adapter(cancelled).discover())


def test_registry_atomic_refresh_and_unknown_model():
    broken = False

    def respond(request):
        return httpx.Response(500 if broken else 200, json={"models": [{"name": "test"}]})

    client = adapter(respond)
    registry = ModelRegistry()
    registry.register(client)
    asyncio.run(registry.refresh())
    assert registry.resolve("test") is client
    with pytest.raises(ValueError):
        registry.register(client)
    with pytest.raises(ModelNotFound):
        registry.resolve("unknown")
    broken = True
    with pytest.raises(ModelUnavailable):
        asyncio.run(registry.refresh())
    assert registry.resolve("test") is client


def test_selection_roundtrip_and_corruption(tmp_path):
    assert load_selection(tmp_path) is None
    save_selection(tmp_path, "test")
    assert load_selection(tmp_path) == "test"
    save_selection(tmp_path, "replacement")
    assert load_selection(tmp_path) == "replacement"
    assert len(list(tmp_path.iterdir())) == 1
    (tmp_path / "model.json").write_text("broken")
    from gar.models.base import ModelError

    with pytest.raises(ModelError):
        load_selection(tmp_path)


def test_message_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Message(role="user", content="hi", execute=True)


def test_external_schema_reference_is_not_fetched():
    client = adapter(
        lambda r: httpx.Response(
            200,
            json={
                "model": "test",
                "done": True,
                "message": {"role": "assistant", "content": "{}"},
            },
        )
    )
    with pytest.raises(InvalidModelResponse):
        asyncio.run(
            client.generate(
                "test",
                [Message(role="user", content="hi")],
                response_schema={"$ref": "https://example.com/private-schema"},
            )
        )


@pytest.mark.parametrize(
    "content,valid", [('{"answer": 42}', True), ('{"answer": "wrong"}', False), ("not JSON", False)]
)
def test_structured_response_validation(content, valid):
    client = adapter(
        lambda r: httpx.Response(
            200,
            json={
                "model": "test",
                "done": True,
                "message": {"role": "assistant", "content": content},
            },
        )
    )

    async def run():
        return await client.generate(
            "test",
            [Message(role="user", content="hi")],
            response_schema={
                "type": "object",
                "properties": {"answer": {"type": "integer"}},
                "required": ["answer"],
            },
        )

    if valid:
        assert asyncio.run(run()).content == content
    else:
        with pytest.raises(InvalidModelResponse):
            asyncio.run(run())
