"""
Example custom backend plugin that echoes back the prompt.

This demonstrates how to create a custom backend for the AI library.
"""

import asyncio
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from matilda_brain.backends import BaseBackend
from matilda_brain.models import AIResponse


class EchoBackend(BaseBackend):
    """
    A simple backend that echoes back the user's prompt.

    This is useful for testing and demonstration purposes.
    """

    @property
    def name(self) -> str:
        """Backend name for identification."""
        return "echo"

    @property
    def is_available(self) -> bool:
        """Echo backend is always available."""
        return True

    async def ask(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AIResponse:
        """
        Echo back the prompt with some decoration.

        Args:
            prompt: The user prompt
            model: Ignored for echo backend
            system: System prompt (will be prepended if provided)
            temperature: Ignored
            max_tokens: Limits response length
            **kwargs: Additional parameters (ignored)

        Returns:
            AIResponse containing echoed prompt
        """
        start_time = time.time()

        # Simulate some processing time
        await asyncio.sleep(0.1)

        # Build response
        if system:
            response = f"[System: {system}]\n\n"
        else:
            response = ""

        response += f"Echo: {prompt}"

        # Apply max_tokens limit if specified
        if max_tokens and len(response) > max_tokens:
            response = response[:max_tokens] + "..."

        time_taken = time.time() - start_time

        return AIResponse(
            response,
            model=model or "echo-1.0",
            backend=self.name,
            tokens_in=len(prompt.split()),
            tokens_out=len(response.split()),
            time_taken=time_taken,
            metadata={"echo_mode": True, "original_prompt": prompt},
        )

    async def astream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream the echo response word by word.

        Args:
            prompt: The user prompt
            model: Ignored for echo backend
            system: System prompt (will be prepended if provided)
            temperature: Ignored
            max_tokens: Limits response length
            **kwargs: Additional parameters (ignored)

        Yields:
            Response chunks (words)
        """
        # Build full response
        if system:
            response = f"[System: {system}]\n\nEcho: {prompt}"
        else:
            response = f"Echo: {prompt}"

        # Apply max_tokens limit if specified
        if max_tokens and len(response) > max_tokens:
            response = response[:max_tokens] + "..."

        # Stream word by word
        words = response.split()
        for i, word in enumerate(words):
            await asyncio.sleep(0.05)  # Simulate streaming delay
            if i < len(words) - 1:
                yield word + " "
            else:
                yield word

    async def models(self) -> List[str]:
        """
        Get list of available models.

        Returns:
            List of echo model names
        """
        return ["echo-1.0", "echo-fast", "echo-verbose"]

    async def status(self) -> Dict[str, Any]:
        """
        Get backend status information.

        Returns:
            Dictionary containing status information
        """
        return {
            "backend": self.name,
            "available": True,
            "models": await self.models(),
            "features": ["echo", "streaming", "system_prompt"],
            "version": "1.0.0",
        }


def register_plugin(registry):
    """
    Register this backend with the plugin registry.

    This function is called automatically when the plugin is loaded.

    Args:
        registry: The plugin registry instance
    """
    registry.register_backend(
        "echo",
        EchoBackend,
        version="1.0.0",
        description="A simple echo backend for testing",
        author="AI Library Team",
    )
