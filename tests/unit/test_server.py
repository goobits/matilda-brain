import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from matilda_brain import server
from matilda_brain.core.exceptions import BackendTimeoutError
from matilda_brain.core.models import AIResponse

TOKEN = "test-token"
AUTH_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
async def client():
    test_client = TestClient(TestServer(server.create_app(api_token=TOKEN, allowed_origins=["https://app.test"])))
    await test_client.start_server()
    yield test_client
    await test_client.close()


def parse_sse(body: str) -> list[dict]:
    return [json.loads(line.removeprefix("data: ")) for line in body.splitlines() if line.startswith("data: ")]


@pytest.mark.asyncio
async def test_health_is_public_but_api_routes_require_a_well_formed_token(client):
    health = await client.get("/health")
    assert health.status == 200
    assert (await health.json())["result"] == {"status": "ok", "service": "brain"}

    missing = await client.post("/ask", json={"prompt": "hello"})
    malformed = await client.post("/ask", json={"prompt": "hello"}, headers={"Authorization": "Bearer"})
    wrong = await client.post("/ask", json={"prompt": "hello"}, headers={"Authorization": "Bearer wrong"})

    assert missing.status == malformed.status == 401
    assert (await missing.json())["error"]["code"] == "unauthorized"
    assert (await malformed.json())["error"]["code"] == "unauthorized"
    assert wrong.status == 403
    assert (await wrong.json())["error"]["code"] == "forbidden"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "content_type", "expected_message"),
    [
        ("not-json", "application/json", "Invalid JSON"),
        ("[]", "application/json", "JSON object"),
        ("{}", "application/json", "prompt"),
        ('{"prompt":"   "}', "application/json", "prompt"),
        ('{"prompt":"hello","temperature":2.1}', "application/json", "temperature"),
        ('{"prompt":"hello","max_tokens":0}', "application/json", "max_tokens"),
    ],
)
async def test_ask_rejects_invalid_requests(client, body, content_type, expected_message):
    response = await client.post("/ask", data=body, headers={**AUTH_HEADERS, "Content-Type": content_type})
    payload = await response.json()

    assert response.status == 400
    assert payload["error"]["code"] in {"bad_request", "invalid_request"}
    assert expected_message in payload["error"]["message"]


@pytest.mark.asyncio
async def test_ask_uses_validated_async_session_and_preserves_supported_fields(client, monkeypatch):
    instances = []

    class FakeSession:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.history = []
            self.ask_args = None
            instances.append(self)

        async def ask_async(self, prompt, **kwargs):
            self.ask_args = (prompt, kwargs)
            return AIResponse(
                "answer",
                model="resolved-model",
                backend="cloud",
                tokens_in=12,
                tokens_out=4,
                metadata={"provider": "openai"},
            )

    monkeypatch.setattr(server, "PersistentChatSession", FakeSession)
    response = await client.post(
        "/ask",
        json={
            "prompt": "  hello  ",
            "model": "test-model",
            "temperature": 0.4,
            "max_tokens": 80,
            "memory_enabled": False,
            "agent_name": "matilda",
            "unused_compatibility_field": "ignored",
            "messages": [
                {"role": "system", "content": "Be concise", "ignored": True},
                {"role": "user", "content": "Earlier question"},
                {"role": "assistant", "content": "Earlier answer"},
            ],
        },
        headers={**AUTH_HEADERS, "Origin": "https://app.test"},
    )
    payload = await response.json()

    assert response.status == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://app.test"
    assert response.headers["Vary"] == "Origin"
    assert payload["result"] == {"text": "answer"}
    assert payload["provider"] == "openai"
    assert payload["model"] == "resolved-model"
    assert payload["usage"] == {"prompt": 12, "completion": 4}

    session = instances[0]
    assert session.kwargs == {
        "system": "Be concise",
        "model": "test-model",
        "agent_name": "matilda",
        "memory_enabled": False,
    }
    assert [message["role"] for message in session.history] == ["user", "assistant"]
    assert session.ask_args == (
        "hello",
        {"model": "test-model", "temperature": 0.4, "max_tokens": 80},
    )


@pytest.mark.asyncio
async def test_ask_rejects_unsafe_agent_header_before_session_creation(client, monkeypatch):
    def fail_session(**_kwargs):
        raise AssertionError("session must not be created")

    monkeypatch.setattr(server, "PersistentChatSession", fail_session)
    response = await client.post(
        "/ask",
        json={"prompt": "hello"},
        headers={**AUTH_HEADERS, "X-Agent-Name": "../other-agent"},
    )

    assert response.status == 400
    assert (await response.json())["error"]["code"] == "invalid_request"


@pytest.mark.asyncio
async def test_stream_emits_valid_sse_with_one_request_id(client, monkeypatch):
    async def fake_stream(prompt, **kwargs):
        assert prompt == "hello"
        assert kwargs["model"] == "test-model"
        yield "hé"
        yield "llo"

    monkeypatch.setattr(server, "stream_async", fake_stream)
    response = await client.post(
        "/stream",
        json={"prompt": "hello", "model": "test-model"},
        headers={**AUTH_HEADERS, "Origin": "https://app.test"},
    )
    events = parse_sse(await response.text())

    assert response.status == 200
    assert response.headers["Content-Type"].startswith("text/event-stream")
    assert response.headers["Access-Control-Allow-Origin"] == "https://app.test"
    assert [event["result"] for event in events] == [{"delta": "hé"}, {"delta": "llo"}, {"done": True}]
    assert len({event["request_id"] for event in events}) == 1


@pytest.mark.asyncio
async def test_stream_sanitizes_backend_errors_and_keeps_request_id(client, monkeypatch):
    async def failing_stream(*_args, **_kwargs):
        yield "started"
        raise BackendTimeoutError("cloud", 30)

    monkeypatch.setattr(server, "stream_async", failing_stream)
    response = await client.post("/stream", json={"prompt": "hello"}, headers=AUTH_HEADERS)
    events = parse_sse(await response.text())

    assert [event.get("result") for event in events[:1]] == [{"delta": "started"}]
    assert events[-1]["error"] == {
        "message": "AI backend timed out",
        "code": "backend_timeout",
        "retryable": True,
    }
    assert len({event["request_id"] for event in events}) == 1


def test_create_app_with_explicit_policy_has_no_token_or_origin_side_effects(monkeypatch):
    monkeypatch.setattr(server, "get_or_create_token", lambda: (_ for _ in ()).throw(AssertionError("token read")))
    monkeypatch.setattr(server, "get_allowed_origins", lambda: (_ for _ in ()).throw(AssertionError("origin read")))

    app = server.create_app(api_token=TOKEN, allowed_origins=[])

    assert app is not None
