"""
HTTP client for matilda-memory service.
Gracefully degrades to no-op if memory service unavailable.
"""

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

import httpx

DEFAULT_MEMORY_PORT = 3214
DEFAULT_GATEWAY_PORT = 3210


def _default_connection() -> tuple[str, Optional[str], Dict[str, str]]:
    transport = os.getenv("MATILDA_MEMORY_TRANSPORT", "tcp").strip().lower() or "tcp"
    endpoint = os.getenv("MATILDA_MEMORY_ENDPOINT", "").strip()
    host = os.getenv("MATILDA_LOCAL_HOST", "127.0.0.1")

    if transport == "unix" and endpoint:
        return "http://matilda-memory", endpoint, {}

    if transport == "pipe":
        gateway = os.getenv("MATILDA_GATEWAY_URL", "").rstrip("/")
        if not gateway:
            gateway_port = os.getenv("MATILDA_PORT_GATEWAY", str(DEFAULT_GATEWAY_PORT))
            gateway = f"http://{host}:{gateway_port}"
        token = os.getenv("MATILDA_API_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return f"{gateway}/v1/memory", None, headers

    if endpoint.startswith(("http://", "https://")):
        return endpoint.rstrip("/"), None, {}
    port = os.getenv("MATILDA_PORT_MEMORY", str(DEFAULT_MEMORY_PORT))
    return f"http://{host}:{port}", None, {}


class MemoryStore(Protocol):
    """Interface for memory operations - enables testing with mocks"""

    def query(self, agent: str, question: str, limit: int = 5) -> List[Any]: ...

    def add_knowledge(self, agent: str, path: str, content: str, commit_message: Optional[str] = None) -> bool: ...

    def log_conversation(self, agent: str, messages: List[Dict[str, str]]) -> bool: ...

    def get_recent_messages(self, agent: str, n: int = 10) -> List[Dict[str, str]]: ...

    def is_available(self) -> bool: ...

    def get_identity(self, agent: str) -> Optional[Dict[str, Any]]: ...

    def close(self) -> None: ...


@dataclass
class MemoryResult:
    path: str
    content: str
    relevance: float
    type: str  # "knowledge" or "conversation"


class MemoryClient(MemoryStore):
    """HTTP client for matilda-memory Rust service"""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 5.0, agent_name: str = "assistant"):
        resolved_url, self._uds, self._headers = _default_connection() if base_url is None else (base_url, None, {})
        self.base_url = resolved_url.rstrip("/")
        self.timeout = timeout
        self.agent_name = agent_name
        self._client: Optional[httpx.Client] = None
        self._available: Optional[bool] = None
        self._identity_cache: Optional[Dict[str, Any]] = None
        self._identity_cache_time: float = 0.0
        self._identity_cache_ttl: float = 60.0

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            headers = {**self._headers, "X-Agent-Name": self.agent_name}
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
                transport=httpx.HTTPTransport(uds=self._uds) if self._uds else None,
            )
        return self._client

    def is_available(self) -> bool:
        """Check if memory service is reachable."""
        if self._available is not None:
            return self._available
        try:
            resp = self.client.get("/health")
            self._available = resp.status_code == 200
        except Exception:
            self._available = False
        return self._available

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self._available = None
        self._identity_cache = None
        self._identity_cache_time = 0.0

    def query(self, agent: str, question: str, limit: int = 5) -> List[MemoryResult]:
        """Search memory for relevant context."""
        if not self.is_available():
            return []
        try:
            resp = self.client.get(f"/vaults/{agent}/search", params={"q": question, "limit": limit})
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [
                MemoryResult(
                    path=r.get("path", ""),
                    content=r.get("content", ""),
                    relevance=r.get("relevance", 0.0),
                    type=r.get("type", "knowledge"),
                )
                for r in data.get("results", [])
            ]
        except Exception:
            return []

    def add_knowledge(self, agent: str, path: str, content: str, commit_message: Optional[str] = None) -> bool:
        """Add knowledge to the vault."""
        if not self.is_available():
            return False
        try:
            payload: Dict[str, Any] = {"content": content}
            if commit_message:
                payload["commit_message"] = commit_message
            resp = self.client.put(f"/vaults/{agent}/knowledge/{path}", json=payload)
            return resp.status_code in (200, 201)
        except Exception:
            return False

    def log_conversation(self, agent: str, messages: List[Dict[str, str]]) -> bool:
        """Log conversation messages."""
        if not self.is_available():
            return False
        try:
            resp = self.client.post(f"/vaults/{agent}/conversations", json={"messages": messages})
            return resp.status_code in (200, 201)
        except Exception:
            return False

    def get_recent_messages(self, agent: str, n: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation messages."""
        if not self.is_available():
            return []
        try:
            resp = self.client.get(f"/vaults/{agent}/conversations/recent", params={"n": n})
            if resp.status_code != 200:
                return []
            data = resp.json()
            messages = data.get("messages", [])
            if not isinstance(messages, list):
                return []
            out: List[Dict[str, str]] = []
            for item in messages:
                if not isinstance(item, dict):
                    continue
                # Keep only string key/value pairs.
                filtered: Dict[str, str] = {k: v for k, v in item.items() if isinstance(k, str) and isinstance(v, str)}
                out.append(filtered)
            return out
        except Exception:
            return []

    def get_identity(self, agent: str) -> Optional[Dict[str, Any]]:
        """Get agent identity from memory vault (cached)."""
        if not self.is_available():
            return None
        now = time.monotonic()
        if self._identity_cache and (now - self._identity_cache_time) < self._identity_cache_ttl:
            return self._identity_cache
        try:
            resp = self.client.get(f"/vaults/{agent}/identity")
            if resp.status_code != 200:
                return None
            self._identity_cache = resp.json()
            self._identity_cache_time = now
            return self._identity_cache
        except Exception:
            return None


class NullMemory(MemoryStore):
    """No-op memory implementation when service is unavailable."""

    def is_available(self) -> bool:
        return False

    def query(self, agent: str, question: str, limit: int = 5) -> List[Any]:
        return []

    def add_knowledge(self, agent: str, path: str, content: str, commit_message: Optional[str] = None) -> bool:
        return False

    def log_conversation(self, agent: str, messages: List[Dict[str, str]]) -> bool:
        return False

    def get_recent_messages(self, agent: str, n: int = 10) -> List[Dict[str, str]]:
        return []

    def get_identity(self, agent: str) -> Optional[Dict[str, Any]]:
        return None

    def close(self) -> None:
        return None


def get_memory(enabled: bool = True, agent_name: str = "assistant") -> MemoryStore:
    """Factory function - returns real client or null implementation."""
    if not enabled:
        return NullMemory()

    client = MemoryClient(agent_name=agent_name)
    if client.is_available():
        return client

    client.close()
    return NullMemory()
