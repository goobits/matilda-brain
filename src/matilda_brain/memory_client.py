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
                 timeout: float = 5.0, agent_name: str = "assistant"):
        # Note: server.rs implements routes at root (e.g. /vaults), not /api/v1 prefix yet.
        # Adjusted to match server implementation
        self.base_url = "http://localhost:3214"
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
# ... (rest of class)

def get_memory(enabled: bool = True, agent_name: str = "assistant") -> MemoryStore:
    """Factory function - returns real client or null implementation"""
    if not enabled:
        return NullMemory()

    client = MemoryClient(agent_name=agent_name)
    if client.is_available():
        return client

    # Service not running - return null implementation
    return NullMemory()
