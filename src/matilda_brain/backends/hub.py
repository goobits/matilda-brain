from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional, Union

import httpx

from ..core.models import AIResponse, ImageInput
from ..core.exceptions import BackendNotAvailableError
from .base import BaseBackend

if TYPE_CHECKING:
    from matilda_transport import HubClient  # type: ignore[import-untyped]  # noqa: F401


class HubBackend(BaseBackend):
    @property
    def name(self) -> str:
        return "hub"

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
        payload = self._build_payload(prompt, model, system, temperature, max_tokens)
        try:
            from matilda_transport import HubClient
        except ImportError as exc:
            raise BackendNotAvailableError(
                self.name,
                "matilda-transport is required for hub backend. Install matilda-transport and retry.",
            ) from exc

        client = HubClient(timeout=self.timeout)
        try:
            response = await asyncio.to_thread(client.post_capability, "reason-over-context", payload)
        except Exception as exc:
            return AIResponse("", error=str(exc))
        error = response.get("error")
        if error:
            message = error.get("message") if isinstance(error, dict) else str(error)
            return AIResponse("", error=message or "hub request failed")
        result = response.get("result") or {}
        text = result.get("text") if isinstance(result, dict) else str(result)
        usage = response.get("usage") or {}
        tokens_in = usage.get("prompt") if isinstance(usage, dict) else None
        tokens_out = usage.get("completion") if isinstance(usage, dict) else None
        return AIResponse(
            text or "",
            model=response.get("model"),
            backend=self.name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            metadata={"provider": response.get("provider")},
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
            payload = self._build_payload(prompt, model, system, temperature, max_tokens)
            try:
                from matilda_transport import HubClient
            except ImportError as exc:
                raise BackendNotAvailableError(
                    self.name,
                    "matilda-transport is required for hub backend. Install matilda-transport and retry.",
                ) from exc

            client_info = HubClient(timeout=self.timeout)
            base_url = client_info.base_url
            token = client_info.api_token
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            url = f"{base_url}/v1/capabilities/reason-over-context/stream"
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data:
                            continue
                        try:
                            envelope = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        result = envelope.get("result") or {}
                        if isinstance(result, dict):
                            delta = result.get("delta")
                            if delta:
                                yield str(delta)
                            if result.get("done"):
                                break

        return _gen()

    async def models(self) -> List[str]:
        return []

    async def status(self) -> Dict[str, Any]:
        return {"available": self.is_available, "name": self.name}

    def _build_payload(
        self,
        prompt: Union[str, List[Union[str, ImageInput]]],
        model: Optional[str],
        system: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        prompt_value: str | List[str]
        if isinstance(prompt, list):
            prompt_value = []
            for item in prompt:
                if isinstance(item, ImageInput):
                    prompt_value.append(item.to_base64())
                else:
                    prompt_value.append(str(item))
        else:
            prompt_value = prompt
        return {
            "prompt": prompt_value,
            "model": model,
            "system": system,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
