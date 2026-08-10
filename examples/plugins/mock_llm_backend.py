"""Deterministic offline backend plugin for demos and tests."""

from collections.abc import AsyncIterator
from typing import Any

from matilda_brain import AIResponse
from matilda_brain.backends import BaseBackend


class MockLLMBackend(BaseBackend):
    supports_messages = True

    @property
    def name(self) -> str:
        return "mock-llm"

    @property
    def is_available(self) -> bool:
        return True

    async def ask(self, prompt: Any, **kwargs: Any) -> AIResponse:
        text = str(prompt)
        content = "Mock response: " + (text[:80] or "empty prompt")
        return AIResponse(content, model=kwargs.get("model") or "mock-1", backend=self.name)

    async def astream(self, prompt: Any, **kwargs: Any) -> AsyncIterator[str]:
        response = await self.ask(prompt, **kwargs)
        for word in str(response).split():
            yield word + " "

    async def models(self) -> list[str]:
        return ["mock-1"]

    async def status(self) -> dict[str, Any]:
        return {"backend": self.name, "available": True, "offline": True}


def register_plugin(registry: Any) -> None:
    registry.register_backend(
        "mock-llm",
        MockLLMBackend,
        version="1.0.0",
        description="Deterministic offline responses",
    )
