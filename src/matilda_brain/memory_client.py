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


@dataclass
class MemoryResult:
    path: str
    content: str
    relevance: float
    type: str  # "knowledge" or "conversation"


class MemoryClient(MemoryStore):
    """HTTP client for matilda-memory Rust service"""

    def __init__(self, base_url: str = "http://localhost:3214/api/v1",
                 timeout: float = 5.0):
        # Note: server.rs implements routes at root (e.g. /vaults), not /api/v1 prefix yet.
        # Adjusted to match server implementation
        self.base_url = "http://localhost:3214"
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None
        self._available: Optional[bool] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client

    def is_available(self) -> bool:
        """Check if memory service is running"""
        if self._available is None:
            try:
                resp = self.client.get("/health")
                self._available = resp.status_code == 200
            except httpx.RequestError:
                self._available = False
        return self._available

    def query(self, agent: str, question: str, limit: int = 5) -> List[MemoryResult]:
        """Query knowledge and conversations for relevant context"""
        if not self.is_available():
            return []

        try:
            resp = self.client.get(
                f"/vaults/{agent}/search",
                params={"q": question, "limit": limit}
            )
            resp.raise_for_status()
            data = resp.json()
            return [MemoryResult(**r) for r in data.get("results", [])]
        except httpx.RequestError:
            return []
        except Exception:
            return []

    def add_knowledge(self, agent: str, path: str, content: str,
                      commit_message: Optional[str] = None) -> bool:
        """Add or update knowledge in agent's vault"""
        if not self.is_available():
            return False

        try:
            resp = self.client.put(
                f"/vaults/{agent}/knowledge/{path}",
                json={
                    "content": content,
                    "commit_message": commit_message or f"Update {path}",
                    "tags": []
                }
            )
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    def log_conversation(self, agent: str, messages: List[Dict[str, str]]) -> bool:
        """Append messages to conversation log"""
        if not self.is_available():
            return False

        try:
            resp = self.client.post(
                f"/vaults/{agent}/conversations",
                json={"messages": messages}
            )
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    def get_recent_messages(self, agent: str, n: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation history"""
        if not self.is_available():
            return []

        try:
            resp = self.client.get(
                f"/vaults/{agent}/conversations/recent",
                params={"n": n}
            )
            resp.raise_for_status()
            return resp.json().get("messages", [])
        except httpx.RequestError:
            return []


class NullMemory(MemoryStore):
    """No-op implementation when memory is disabled or unavailable"""

    def query(self, agent: str, question: str, limit: int = 5) -> List[Any]:
        return []

    def add_knowledge(self, agent: str, path: str, content: str,
                      commit_message: Optional[str] = None) -> bool:
        return False

    def log_conversation(self, agent: str, messages: List[Dict[str, str]]) -> bool:
        return False

    def get_recent_messages(self, agent: str, n: int = 10) -> List[Dict[str, str]]:
        return []


def get_memory(enabled: bool = True) -> MemoryStore:
    """Factory function - returns real client or null implementation"""
    if not enabled:
        return NullMemory()

    client = MemoryClient()
    if client.is_available():
        return client

    # Service not running - return null implementation
    return NullMemory()
