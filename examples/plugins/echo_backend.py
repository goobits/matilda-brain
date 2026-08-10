"""Minimal loadable backend plugin."""

from collections.abc import AsyncIterator
from typing import Any

from matilda_brain import AIResponse
from matilda_brain.backends import BaseBackend


class EchoBackend(BaseBackend):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def is_available(self) -> bool:
        return True

    async def ask(self, prompt: Any, **kwargs: Any) -> AIResponse:
        model = kwargs.get("model") or "echo"
        return AIResponse(f"Echo: {prompt}", model=model, backend=self.name)

    async def astream(self, prompt: Any, **kwargs: Any) -> AsyncIterator[str]:
        yield "Echo: "
        yield str(prompt)

    async def models(self) -> list[str]:
        return ["echo"]

    async def status(self) -> dict[str, Any]:
        return {"backend": self.name, "available": True}


def register_plugin(registry: Any) -> None:
    registry.register_backend("echo", EchoBackend, version="1.0.0", description="Echo prompts")
