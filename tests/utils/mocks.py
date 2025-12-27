"""Shared mock objects for testing."""

from typing import AsyncIterator, Dict, List, Optional, Any, Union
from matilda_brain import AIResponse
from matilda_brain.backends import BaseBackend


class MockBackend(BaseBackend):
    """Unified mock backend for testing.

    Supports all the patterns used across different test files:
    - Multiple responses with cycling (test_chat.py style)
    - Custom response text (test_api_streaming.py style)
    - Config-based initialization (test_routing.py style)
    - Request tracking for verification
    - Streaming support with configurable chunks
    """

    def __init__(
        self,
        name_or_config: Union[str, Dict[str, Any]] = "mock",
        config: Optional[Dict[str, Any]] = None,
        response_text: str = "Mock response",
        responses: Optional[List[str]] = None,
    ):
        """Initialize mock backend.

        Args:
            name_or_config: Backend name OR configuration dict (for router compatibility)
            config: Configuration dict (for test_routing.py compatibility)
            response_text: Single response text (for test_api_streaming.py compatibility)
            responses: List of responses to cycle through (for test_chat.py compatibility)
        """
        # Handle router-style initialization where first arg is config
        if isinstance(name_or_config, dict):
            config = name_or_config
            self.name_value = "mock"  # Default name for plugin backends
        else:
            self.name_value = name_or_config

        # Handle config-based initialization (test_routing.py style)
        if config and isinstance(config, dict):
            # Extract name from config if available
            self.name_value = config.get("name", self.name_value)

        self._is_available = True
        self._supports_streaming = True

        # Support multiple response patterns
        if responses:
            self.responses = responses
        else:
            self.responses = [response_text]
        self.response_index = 0
        self.response_text = response_text

        # Track requests for verification (test_api_streaming.py style)
        self.last_prompt = None
        self.last_kwargs = None

    @property
    def name(self) -> str:
        return self.name_value

    @property
    def is_available(self) -> bool:
        return self._is_available

    @property
    def supports_streaming(self) -> bool:
        return self._supports_streaming

    @property
    def models(self) -> List[str]:
        return ["mock-model-1", "mock-model-2"]

    async def status(self, **kwargs) -> Dict[str, Any]:
        return {"available": self._is_available, "name": self.name_value, "backend": self.name_value}

    async def ask(self, prompt: Union[str, List], **kwargs) -> AIResponse:
        """Generate an AI response.

        Supports both string and list prompts (test_chat.py compatibility).
        Tracks requests for verification.
        """
        self.last_prompt = prompt
        self.last_kwargs = kwargs

        # Check if response_text has been updated and use it, otherwise use responses array
        if self.response_text != "Mock response" or len(self.responses) == 1:
            # response_text was updated or we only have default response
            response = self.response_text
        else:
            # Use cycling responses for multi-response scenarios
            response = self.responses[self.response_index % len(self.responses)]
            self.response_index += 1

        # Handle both string and list prompts (test_chat.py style)
        if isinstance(prompt, list):
            # Extract text content from list
            text_parts = [item for item in prompt if isinstance(item, str)]
            prompt_text = " ".join(text_parts)
        else:
            prompt_text = prompt

        return AIResponse(
            content=response,
            model=kwargs.get("model", "mock-model"),
            backend=self.name,
            time_taken=0.1,
            tokens_in=len(prompt_text.split()) * 2 if prompt_text else 10,
            tokens_out=len(response.split()) * 2,
            cost=0.001,
        )

    async def astream(self, prompt: Union[str, List], **kwargs) -> AsyncIterator[str]:
        """Stream a response.

        Supports different streaming patterns from different test files.
        """
        self.last_prompt = prompt
        self.last_kwargs = kwargs

        # Check if response_text has been updated and use it, otherwise use responses array
        if self.response_text != "Mock response" or len(self.responses) == 1:
            # response_text was updated or we only have default response
            response = self.response_text
        else:
            # Use cycling responses for multi-response scenarios
            response = self.responses[self.response_index % len(self.responses)]
            self.response_index += 1

        # Split response into chunks for streaming
        chunks = response.split()
        for chunk in chunks:
            yield chunk + " "

    async def list_models(self, **kwargs) -> List[str]:
        """List available models."""
        return self.models
