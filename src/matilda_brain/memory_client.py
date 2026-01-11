"""
HTTP client for matilda-memory service.
Gracefully degrades to no-op if memory service unavailable.
"""

from typing import Protocol, Optional, List, Dict, Any
import httpx
from dataclasses import dataclass


class MemoryStore(Protocol):
    """Interface for memory operations - enables testing with mocks"""

    def query(self, agent: str, question: str, limit: int = 5) -> List[Any]:
        ...

    def add_knowledge(self, agent: str, path: str, content: str,
                      commit_message: Optional[str] = None) -> bool:
        ...

    def log_conversation(self, agent: str, messages: List[Dict[str, str]]) -> bool:
        ...

    def get_recent_messages(self, agent: str, n: int = 10) -> List[Dict[str, str]]:
        ...

    def is_available(self) -> bool:
        ...


@dataclass
class MemoryResult:
    path: str
    content: str
    relevance: float
    type: str  # "knowledge" or "conversation"


class MemoryClient(MemoryStore):
    """HTTP client for matilda-memory Rust service"""

    def __init__(self, base_url: str = "http://localhost:3214",
                 timeout: float = 5.0, agent_name: str = "assistant"):
        self.base_url = base_url
        self.timeout = timeout
        self.agent_name = agent_name
        self._client: Optional[httpx.Client] = None
        self._available: Optional[bool] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"X-Agent-Name": self.agent_name}
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

    def query(self, agent: str, question: str, limit: int = 5) -> List[MemoryResult]:
        """Search memory for relevant context."""
        if not self.is_available():
            return []
        try:
            resp = self.client.get(
                f"/vaults/{agent}/search",
                params={"q": question, "limit": limit}
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [
                MemoryResult(
                    path=r.get("path", ""),
                    content=r.get("content", ""),
                    relevance=r.get("relevance", 0.0),
                    type=r.get("type", "knowledge")
                )
                for r in data.get("results", [])
            ]
        except Exception:
            return []

    def add_knowledge(self, agent: str, path: str, content: str,
                      commit_message: Optional[str] = None) -> bool:
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
            resp = self.client.post(
                f"/vaults/{agent}/conversations",
                json={"messages": messages}
            )
            return resp.status_code in (200, 201)
        except Exception:
            return False

    def get_recent_messages(self, agent: str, n: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation messages."""
        if not self.is_available():
            return []
        try:
            resp = self.client.get(
                f"/vaults/{agent}/conversations",
                params={"limit": n}
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return data.get("messages", [])
        except Exception:
            return []


class NullMemory(MemoryStore):
    """No-op memory implementation when service is unavailable."""

    def is_available(self) -> bool:
        return False

    def query(self, agent: str, question: str, limit: int = 5) -> List[Any]:
        return []

    def add_knowledge(self, agent: str, path: str, content: str,
                      commit_message: Optional[str] = None) -> bool:
        return False

    def log_conversation(self, agent: str, messages: List[Dict[str, str]]) -> bool:
        return False

    def get_recent_messages(self, agent: str, n: int = 10) -> List[Dict[str, str]]:
        return []


def get_memory(enabled: bool = True, agent_name: str = "assistant") -> MemoryStore:
    """Factory function - returns real client or null implementation."""
    if not enabled:
        return NullMemory()

    client = MemoryClient(agent_name=agent_name)
    if client.is_available():
        return client

    # Service not running - return null implementation
    return NullMemory()
