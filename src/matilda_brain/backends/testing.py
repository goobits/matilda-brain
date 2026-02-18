"""Deterministic backend for tests and offline development.

This backend is always available, never performs network calls, and returns
stable outputs. It is intended for unit tests and local smoke checks.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional, Union

from .base import BaseBackend
from ..core.models import AIResponse, ImageInput


class TestingBackend(BaseBackend):
    @property
    def name(self) -> str:
        return "testing"

    @property
    def is_available(self) -> bool:
        return True

    async def ask(
        self,
        prompt: Union[str, List[Union[str, ImageInput]]],
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> AIResponse:
        _ = (system, temperature, max_tokens, tools, kwargs)

        text = _prompt_to_text(prompt)

        # A couple of stable "known answers" that are useful for tests.
        normalized = " ".join(text.lower().split())
        if "2+2" in normalized or "two plus two" in normalized:
            content = "4"
        elif "count from 1 to 3" in normalized:
            content = "1\n2\n3\n"
        else:
            content = "OK"

        return AIResponse(
            content,
            model=model or "testing",
            backend=self.name,
        )

    def astream(
        self,
        prompt: Union[str, List[Union[str, ImageInput]]],
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            resp = await self.ask(
                prompt,
                model=model,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                **kwargs,
            )
            for ch in str(resp):
                yield ch

        return _gen()

    async def models(self) -> List[str]:
        return ["testing"]

    async def status(self) -> Dict[str, Any]:
        return {"backend": self.name, "available": True, "mode": "offline"}


def _prompt_to_text(prompt: Union[str, List[Union[str, ImageInput]]]) -> str:
    if isinstance(prompt, str):
        return prompt

    parts: List[str] = []
    for item in prompt:
        if isinstance(item, str):
            parts.append(item)
        else:
            # Images are ignored for the deterministic backend.
            parts.append("[image]")
    return " ".join(parts)
