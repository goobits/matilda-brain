import matilda_transport
import pytest

from matilda_brain.backends import hub
from matilda_brain.backends.hub import HubBackend
from matilda_brain.core.models import ImageInput


@pytest.mark.asyncio
async def test_hub_ask_preserves_payload_and_response_metadata(monkeypatch):
    calls = []

    class FakeHubClient:
        def __init__(self, timeout):
            assert timeout == 12

        def post_capability(self, capability, payload):
            calls.append((capability, payload))
            return {
                "result": {"text": "answer"},
                "model": "resolved-model",
                "provider": "openai",
                "usage": {"prompt": 5, "completion": 2},
            }

    monkeypatch.setattr(matilda_transport, "HubClient", FakeHubClient)
    backend = HubBackend({"timeout": 12})

    response = await backend.ask(
        "question",
        model="requested-model",
        system="Be concise",
        temperature=0.4,
        max_tokens=100,
    )

    assert str(response) == "answer"
    assert response.model == "resolved-model"
    assert response.backend == "hub"
    assert response.tokens_in == 5
    assert response.tokens_out == 2
    assert response.metadata == {"provider": "openai"}
    assert calls == [
        (
            "reason-over-context",
            {
                "prompt": "question",
                "model": "requested-model",
                "system": "Be concise",
                "temperature": 0.4,
                "max_tokens": 100,
            },
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("hub_result", "expected_error"),
    [
        ({"error": {"message": "upstream failed"}}, "upstream failed"),
        ({"error": "plain failure"}, "plain failure"),
    ],
)
async def test_hub_ask_returns_upstream_errors(monkeypatch, hub_result, expected_error):
    class FakeHubClient:
        def __init__(self, timeout):
            pass

        def post_capability(self, capability, payload):
            return hub_result

    monkeypatch.setattr(matilda_transport, "HubClient", FakeHubClient)

    response = await HubBackend().ask("question")

    assert response.failed is True
    assert response.error == expected_error


@pytest.mark.asyncio
async def test_hub_ask_turns_transport_exceptions_into_failed_responses(monkeypatch):
    class FakeHubClient:
        def __init__(self, timeout):
            pass

        def post_capability(self, capability, payload):
            raise OSError("socket unavailable")

    monkeypatch.setattr(matilda_transport, "HubClient", FakeHubClient)

    response = await HubBackend().ask("question")

    assert response.failed is True
    assert response.error == "socket unavailable"


@pytest.mark.asyncio
async def test_hub_stream_parses_only_valid_delta_events_until_done(monkeypatch):
    captured = {}

    class FakeHubClient:
        def __init__(self, timeout):
            self.base_url = "http://gateway.test"
            self.api_token = "gateway-token"

    class FakeResponse:
        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            for line in [
                "",
                "event: message",
                "data:",
                "data: not-json",
                'data: {"result":{"delta":"hel"}}',
                'data: {"result":{"delta":"lo"}}',
                'data: {"result":{"done":true}}',
                'data: {"result":{"delta":"ignored"}}',
            ]:
                yield line

    class StreamContext:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *_args):
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout, headers):
            captured["timeout"] = timeout
            captured["headers"] = headers

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, method, url, *, json):
            captured.update(method=method, url=url, payload=json)
            return StreamContext()

    monkeypatch.setattr(matilda_transport, "HubClient", FakeHubClient)
    monkeypatch.setattr(hub.httpx, "AsyncClient", FakeAsyncClient)
    backend = HubBackend({"timeout": 9})

    chunks = [chunk async for chunk in backend.astream("question", model="model")]

    assert chunks == ["hel", "lo"]
    assert captured == {
        "timeout": 9,
        "headers": {"Authorization": "Bearer gateway-token"},
        "method": "POST",
        "url": "http://gateway.test/v1/capabilities/reason-over-context/stream",
        "payload": {
            "prompt": "question",
            "model": "model",
            "system": None,
            "temperature": None,
            "max_tokens": None,
        },
    }


@pytest.mark.asyncio
async def test_hub_metadata_and_multimodal_payload():
    backend = HubBackend()
    image = ImageInput(b"image-bytes")

    payload = backend._build_payload(["describe", image], None, None, None, None)

    assert payload["prompt"] == ["describe", image.to_base64()]
    assert await backend.models() == []
    assert await backend.status() == {"available": True, "name": "hub"}
