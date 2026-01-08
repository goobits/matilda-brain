"""
Example mock LLM backend plugin for testing and development.

This backend generates realistic-looking responses without calling any real AI service.
Useful for testing, development, and demos.
"""

import asyncio
import random
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from matilda_brain.backends import BaseBackend
from matilda_brain.models import AIResponse


class MockLLMBackend(BaseBackend):
    """
    A mock LLM backend that generates fake but realistic responses.

    This is useful for:
    - Testing applications without API costs
    - Development when offline
    - Demonstrations and tutorials
    """

    # Response templates for different types of queries
    TEMPLATES = {
        "greeting": [
            "Hello! How can I assist you today?",
            "Hi there! I'm here to help. What would you like to know?",
            "Greetings! Feel free to ask me anything.",
        ],
        "code": [
            "Here's a solution to your coding question:\n\n```python\ndef example_function(param):\n    # This is a mock implementation\n    result = process_data(param)\n    return result\n```\n\nThis function demonstrates the concept you asked about.",
            "Let me help you with that code:\n\n```python\n# Mock code example\nfor item in items:\n    process(item)\n```\n\nThis approach should solve your problem.",
        ],
        "explanation": [
            "That's an interesting question! Let me explain:\n\n1. First, we need to understand the concept\n2. Then, we can apply it to your specific case\n3. Finally, we'll see how it works in practice\n\nIn essence, this demonstrates the principle you're asking about.",
            "Great question! Here's a detailed explanation:\n\nThe concept you're asking about involves several key aspects. First, there's the theoretical foundation. Second, we have practical applications. Third, there are common use cases.\n\nThis should give you a comprehensive understanding.",
        ],
        "default": [
            "Based on your query, here's what I understand:\n\nYou're asking about an interesting topic. While this is a mock response, in a real scenario, I would provide detailed information about your specific question.\n\nIs there anything specific you'd like to know more about?",
            "Thank you for your question. Here's my response:\n\nThis is a simulated response from the mock backend. In production, you would get a real AI-generated answer tailored to your specific query.\n\nFeel free to ask follow-up questions!",
        ],
    }

    @property
    def name(self) -> str:
        """Backend name for identification."""
        return "mock"

    @property
    def is_available(self) -> bool:
        """Mock backend is always available."""
        return True

    def _categorize_prompt(self, prompt: str) -> str:
        """Categorize the prompt to select appropriate template."""
        prompt_lower = prompt.lower()

        if any(word in prompt_lower for word in ["hello", "hi", "hey", "greetings"]):
            return "greeting"
        elif any(word in prompt_lower for word in ["code", "function", "class", "debug", "python", "javascript"]):
            return "code"
        elif any(word in prompt_lower for word in ["explain", "what is", "how does", "why", "describe"]):
            return "explanation"
        else:
            return "default"

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
        Generate a mock response based on the prompt.

        Args:
            prompt: The user prompt
            model: Model to simulate (affects response style)
            system: System prompt (affects response tone)
            temperature: Randomness (0-1)
            max_tokens: Maximum response length
            **kwargs: Additional parameters

        Returns:
            AIResponse with mock content
        """
        start_time = time.time()

        # Simulate processing delay
        delay = random.uniform(0.5, 1.5)
        await asyncio.sleep(delay)

        # Select response template
        category = self._categorize_prompt(prompt)
        templates = self.TEMPLATES[category]

        # Use temperature to add randomness
        if temperature is None:
            temperature = 0.7

        if temperature > 0.5:
            response = random.choice(templates)
        else:
            response = templates[0]

        # Apply system prompt influence
        if system and "helpful" in system.lower():
            response = f"I'll do my best to help! {response}"
        elif system and "brief" in system.lower():
            response = response.split(".")[0] + "."

        # Apply max_tokens limit
        if max_tokens:
            words = response.split()
            if len(words) > max_tokens:
                response = " ".join(words[:max_tokens]) + "..."

        time_taken = time.time() - start_time

        # Simulate token counts
        tokens_in = len(prompt.split()) * 2  # Rough estimate
        tokens_out = len(response.split()) * 2

        return AIResponse(
            response,
            model=model or "mock-gpt-3.5",
            backend=self.name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            time_taken=time_taken,
            cost=0.0,  # Free!
            metadata={"mock": True, "category": category, "temperature": temperature},
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
        Stream a mock response token by token.

        Args:
            prompt: The user prompt
            model: Model to simulate
            system: System prompt
            temperature: Randomness
            max_tokens: Maximum response length
            **kwargs: Additional parameters

        Yields:
            Response chunks
        """
        # Get the full response first
        response = await self.ask(
            prompt,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Stream it word by word
        words = str(response).split()
        for i, word in enumerate(words):
            # Simulate realistic streaming delay
            delay = random.uniform(0.01, 0.1)
            await asyncio.sleep(delay)

            if i < len(words) - 1:
                yield word + " "
            else:
                yield word

    async def models(self) -> List[str]:
        """
        Get list of available mock models.

        Returns:
            List of mock model names
        """
        return [
            "mock-gpt-4",
            "mock-gpt-3.5",
            "mock-claude",
            "mock-llama",
            "mock-fast",
            "mock-quality",
        ]

    async def status(self) -> Dict[str, Any]:
        """
        Get backend status information.

        Returns:
            Dictionary containing status information
        """
        models = await self.models()
        return {
            "backend": self.name,
            "available": True,
            "models": models,
            "total_models": len(models),
            "features": [
                "mock_responses",
                "streaming",
                "system_prompt",
                "temperature_control",
                "zero_cost",
            ],
            "version": "1.0.0",
            "warning": "This is a mock backend - responses are not real AI output",
        }


def register_plugin(registry):
    """
    Register this backend with the plugin registry.

    This function is called automatically when the plugin is loaded.

    Args:
        registry: The plugin registry instance
    """
    registry.register_backend(
        "mock",
        MockLLMBackend,
        version="1.0.0",
        description="Mock LLM backend for testing and development",
        author="AI Library Team",
        requires=[],  # No external dependencies
    )
