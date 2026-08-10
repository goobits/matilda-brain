import json

import httpx

from matilda_brain import memory_client
from matilda_brain.memory_client import MemoryClient, NullMemory


def test_memory_client_contract_and_identity_cache():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path == "/health":
            return httpx.Response(200)
        if path.endswith("/search"):
            assert dict(request.url.params) == {"q": "question", "limit": "3"}
            return httpx.Response(
                200,
                json={"results": [{"path": "notes/item", "content": "answer", "relevance": 0.9, "type": "knowledge"}]},
            )
        if "/knowledge/" in path:
            assert json.loads(request.content) == {"content": "fact", "commit_message": "remember"}
            return httpx.Response(201)
        if path.endswith("/conversations"):
            assert json.loads(request.content) == {"messages": [{"role": "user", "content": "hello"}]}
            return httpx.Response(200)
        if path.endswith("/conversations/recent"):
            return httpx.Response(200, json={"messages": [{"role": "user", "content": "hello", "count": 1}, "bad"]})
        if path.endswith("/identity"):
            return httpx.Response(200, json={"persona": {"name": "Matilda"}})
        raise AssertionError(path)

    client = MemoryClient(base_url="http://memory.test", agent_name="matilda")
    client._client = httpx.Client(base_url=client.base_url, transport=httpx.MockTransport(handler))

    assert client.is_available() is True
    assert client.is_available() is True
    assert len([request for request in requests if request.url.path == "/health"]) == 1

    results = client.query("matilda", "question", limit=3)
    assert [(result.path, result.content, result.relevance, result.type) for result in results] == [
        ("notes/item", "answer", 0.9, "knowledge")
    ]
    assert client.add_knowledge("matilda", "notes/item", "fact", commit_message="remember") is True
    assert client.log_conversation("matilda", [{"role": "user", "content": "hello"}]) is True
    assert client.get_recent_messages("matilda") == [{"role": "user", "content": "hello"}]
    assert client.get_identity("matilda") == {"persona": {"name": "Matilda"}}
    assert client.get_identity("matilda") == {"persona": {"name": "Matilda"}}
    assert len([request for request in requests if request.url.path.endswith("/identity")]) == 1

    client.close()
    assert client._client is None
    assert client._available is None
    assert client._identity_cache is None


def test_memory_client_degrades_cleanly_when_service_is_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = MemoryClient(base_url="http://memory.test")
    client._client = httpx.Client(base_url=client.base_url, transport=httpx.MockTransport(handler))

    assert client.is_available() is False
    assert client.query("assistant", "question") == []
    assert client.add_knowledge("assistant", "path", "content") is False
    assert client.log_conversation("assistant", []) is False
    assert client.get_recent_messages("assistant") == []
    assert client.get_identity("assistant") is None
    client.close()


def test_memory_factory_closes_failed_client(monkeypatch):
    instances = []

    class UnavailableMemory:
        def __init__(self, agent_name):
            self.agent_name = agent_name
            self.closed = False
            instances.append(self)

        def is_available(self):
            return False

        def close(self):
            self.closed = True

    monkeypatch.setattr(memory_client, "MemoryClient", UnavailableMemory)

    result = memory_client.get_memory(agent_name="matilda")

    assert isinstance(result, NullMemory)
    assert instances[0].agent_name == "matilda"
    assert instances[0].closed is True


def test_disabled_memory_is_a_complete_noop():
    memory = memory_client.get_memory(enabled=False)

    assert isinstance(memory, NullMemory)
    assert memory.is_available() is False
    assert memory.query("assistant", "question") == []
    assert memory.add_knowledge("assistant", "path", "content") is False
    assert memory.log_conversation("assistant", []) is False
    assert memory.get_recent_messages("assistant") == []
    assert memory.get_identity("assistant") is None
    assert memory.close() is None
