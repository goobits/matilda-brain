"""HTTP-level mocking for integration tests.

This module provides realistic HTTP response mocks for different AI providers
to avoid rate limiting while preserving real behavior testing.
"""

import time
from typing import AsyncIterator, Optional, Union
from unittest.mock import Mock
import asyncio

# Realistic response templates for different providers
OPENAI_RESPONSE_TEMPLATE = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": int(time.time()),
    "model": "gpt-3.5-turbo-0613",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "Mock response content"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
}

ANTHROPIC_RESPONSE_TEMPLATE = {
    "id": "msg_123",
    "type": "message",
    "role": "assistant",
    "content": [{"type": "text", "text": "Mock response content"}],
    "model": "claude-3-haiku-20240307",
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 10, "output_tokens": 20},
}

OPENROUTER_RESPONSE_TEMPLATE = {
    "id": "gen-123",
    "object": "chat.completion",
    "created": int(time.time()),
    "model": "google/gemini-2.5-flash",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "Mock response content"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
}


class MockLiteLLMResponse:
    """Mock response object that matches LiteLLM's response structure."""

    def __init__(
        self,
        content: str,
        model: str = "gpt-3.5-turbo",
        provider: str = "openai",
        finish_reason: str = "stop",
        prompt_tokens: int = 10,
        completion_tokens: int = 20,
    ):
        self.content = content
        self.model = model
        self.provider = provider
        self.finish_reason = finish_reason
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

        # Create choices structure
        self.choices = [self._create_choice()]

        # Create usage structure
        self.usage = self._create_usage()

        # Add hidden params for cost calculation (LiteLLM feature)
        self._hidden_params = {"response_cost": 0.001}  # Mock cost

    def _create_choice(self):
        """Create a choice object matching LiteLLM structure."""
        choice = Mock()
        choice.index = 0
        choice.finish_reason = self.finish_reason

        # Create message object
        message = Mock()
        message.role = "assistant"
        message.content = self.content
        message.tool_calls = None  # No tool calls by default
        choice.message = message

        return choice

    def _create_usage(self):
        """Create usage object matching LiteLLM structure."""
        usage = Mock()
        usage.prompt_tokens = self.prompt_tokens
        usage.completion_tokens = self.completion_tokens
        usage.total_tokens = self.prompt_tokens + self.completion_tokens
        return usage


class MockStreamChunk:
    """Mock streaming chunk that matches LiteLLM's streaming structure."""

    def __init__(self, content: str, finish_reason: Optional[str] = None):
        self.choices = [self._create_choice(content, finish_reason)]

    def _create_choice(self, content: str, finish_reason: Optional[str]):
        """Create a streaming choice object."""
        choice = Mock()
        choice.index = 0
        choice.finish_reason = finish_reason

        # Create delta object for streaming
        delta = Mock()
        delta.content = content
        delta.role = "assistant" if content else None
        choice.delta = delta

        return choice


class SmartHTTPMocker:
    """Smart HTTP mocker that provides realistic responses based on the request."""

    def __init__(self):
        self.call_count = 0
        self.last_params = None

    def get_response_for_prompt(self, prompt: str, model: str, messages: list = None) -> str:
        """Generate appropriate response based on the prompt content and message history."""
        prompt_lower = prompt.lower()

        # Check message history for context (chat sessions)
        full_context = ""
        if messages:
            for msg in messages:
                if isinstance(msg.get("content"), str):
                    full_context += msg["content"].lower() + " "
                elif isinstance(msg.get("content"), list):
                    # Handle multimodal content
                    for item in msg["content"]:
                        if item.get("type") == "text":
                            full_context += item.get("text", "").lower() + " "

        full_context += prompt_lower

        # Math questions
        if "2+2" in prompt_lower or "2 + 2" in prompt_lower:
            return "4"

        if "5+5" in prompt_lower or "5 + 5" in prompt_lower:
            return "10"

        # Counting requests
        if "count from 1 to 3" in prompt_lower:
            return "1\n2\n3"

        # Name memory tests - check both current prompt and full context
        if "alice" in full_context and (
            "what did i say" in prompt_lower
            or "what did you say" in prompt_lower
            or "remember" in prompt_lower
            or "name was" in prompt_lower
        ):
            return "Your name is Alice."
        elif "alice" in prompt_lower and ("name" in prompt_lower or "5+5" in prompt_lower):
            return "Hello Alice! 10"

        # Specific response requests
        if "say 'openai test'" in prompt_lower:
            return "OpenAI test"

        if "say 'claude test'" in prompt_lower:
            return "Claude test"

        if "reply with just 'ok'" in prompt_lower:
            return "OK"

        if "exactly 3 words" in prompt_lower and "quantum" in prompt_lower:
            return "Quantum superposition computation"

        if "what is ai" in prompt_lower:
            return "AI is artificial intelligence that enables machines to simulate human thinking and decision-making processes."

        if "factorial" in prompt_lower and "python" in prompt_lower:
            return """def factorial(n):
    \"\"\"Calculate the factorial of a number.
    
    Args:
        n (int): The number to calculate factorial for
        
    Returns:
        int: The factorial of n
    \"\"\"
    if n <= 1:
        return 1
    return n * factorial(n - 1)"""

        if "mean and median" in prompt_lower:
            return "The mean is the average of all values, while the median is the middle value when data is sorted."

        # Count requests
        if "count:" in prompt_lower:
            import re

            match = re.search(r"count:\s*(\d+)", prompt_lower)
            if match:
                num = match.group(1)
                return f"Counting {num}"

        # Python programming language questions
        if any(term in prompt_lower for term in ["python programming", "python language", "python features"]):
            return (
                "Python is a high-level, interpreted programming language known for its clean syntax, "
                "extensive standard library, dynamic typing, and versatility. Key features include "
                "object-oriented programming, functional programming support, automatic memory management, "
                "and a vast ecosystem of third-party packages through pip and PyPI."
            )

        # Recursion questions
        if "recursion" in prompt_lower:
            return (
                "Recursion is a programming technique where a function calls itself to solve smaller "
                "subproblems. It consists of a base case that stops the recursion and a recursive case "
                "that reduces the problem size. Common examples include factorial calculation, tree "
                "traversal, and divide-and-conquer algorithms."
            )

        # Python code analysis questions
        if (
            "analyze" in prompt_lower
            and "python" in prompt_lower
            and ("function" in prompt_lower or "code" in prompt_lower)
        ):
            return (
                "This Python function uses list comprehension effectively for filtering and processing. "
                "Suggestions for improvement: add type hints for better code documentation, consider "
                "error handling for edge cases, and add docstring to explain the function's purpose. "
                "The logic is clean and follows Python best practices for functional programming."
            )

        # Documentation summarization questions
        if ("summarize" in prompt_lower or "summary" in prompt_lower) and (
            "component" in prompt_lower or "documentation" in prompt_lower or "main" in prompt_lower
        ):
            return (
                "The project documentation outlines several key components: a data processing module for handling "
                "information flow, a user interface component for user interaction, integration tests for quality "
                "assurance, and configuration management for system setup. The architecture follows modern best "
                "practices with clear separation of concerns between different project modules."
            )

        # Advanced computer science topics
        if any(term in prompt_lower for term in ["computer science", "algorithms", "data structures"]):
            return (
                "Computer science encompasses algorithms, data structures, software engineering, and "
                "computational theory. Key concepts include recursion, complexity analysis, abstract "
                "data types, and problem-solving methodologies that form the foundation of programming."
            )

        # Default responses
        if "hello" in prompt_lower:
            return "Hello! How can I help you today?"

        # Generic response (enhanced for CLI test expectations)
        return (
            "This is a comprehensive mock response from the AI model designed to provide "
            "realistic testing scenarios while maintaining appropriate length and detail for "
            "various test requirements and validation criteria."
        )

    def get_provider_from_model(self, model: str) -> str:
        """Determine provider from model name."""
        if model.startswith("openrouter/") or "gemini" in model:
            return "openrouter"
        elif model.startswith("gpt-") or "gpt" in model:
            return "openai"
        elif model.startswith("claude-") or "claude" in model:
            return "anthropic"
        else:
            return "openai"  # Default

    async def mock_acompletion(self, **params) -> Union[MockLiteLLMResponse, AsyncIterator[MockStreamChunk]]:
        """Mock LiteLLM's acompletion function."""
        self.call_count += 1
        self.last_params = params

        model = params.get("model", "gpt-3.5-turbo")
        messages = params.get("messages", [])
        is_streaming = params.get("stream", False)

        # Extract prompt from messages
        prompt = ""
        if messages:
            last_message = messages[-1]
            if isinstance(last_message.get("content"), str):
                prompt = last_message["content"]
            elif isinstance(last_message.get("content"), list):
                # Handle multimodal content
                text_parts = [item.get("text", "") for item in last_message["content"] if item.get("type") == "text"]
                prompt = " ".join(text_parts)

        # Get appropriate response
        response_content = self.get_response_for_prompt(prompt, model, messages)
        provider = self.get_provider_from_model(model)

        # Handle streaming vs non-streaming
        if is_streaming:
            return self._create_streaming_response(response_content)
        else:
            return MockLiteLLMResponse(content=response_content, model=model, provider=provider)

    async def _create_streaming_response(self, content: str) -> AsyncIterator[MockStreamChunk]:
        """Create a streaming response by chunking the content."""
        # Split content into words for realistic streaming
        words = content.split()

        for i, word in enumerate(words):
            # Add space after word except for last word
            chunk_content = word + (" " if i < len(words) - 1 else "")
            yield MockStreamChunk(chunk_content)

            # Small delay to simulate real streaming
            await asyncio.sleep(0.01)

        # Final chunk with finish reason
        yield MockStreamChunk("", finish_reason="stop")


class ErrorHTTPMocker(SmartHTTPMocker):
    """HTTP mocker that can simulate various error conditions."""

    def __init__(self, error_type: str = "rate_limit"):
        super().__init__()
        self.error_type = error_type

    async def mock_acompletion(self, **params):
        """Mock LiteLLM's acompletion function with errors."""
        self.call_count += 1
        self.last_params = params

        model = params.get("model", "gpt-3.5-turbo")

        if self.error_type == "rate_limit":
            # Create a mock response object that simulates rate limit error structure
            error = Exception("Rate limit exceeded. Please try again later.")
            error.response = Mock()
            error.response.headers = {"retry-after": "60"}
            raise error
        elif self.error_type == "auth":
            raise Exception("Invalid API key provided")
        elif self.error_type == "model_not_found":
            raise Exception(f"Model '{model}' not found")
        elif self.error_type == "quota":
            raise Exception("You exceeded your current quota")
        elif self.error_type == "timeout":
            raise asyncio.TimeoutError("Request timed out")
        elif self.error_type == "service_unavailable":
            error = Exception("Service temporarily unavailable (503). The model is currently overloaded.")
            error.__class__.__name__ = "ServiceUnavailableError"
            raise error
        else:
            raise Exception(f"Mock error: {self.error_type}")


# Global mocker instance
_global_mocker = SmartHTTPMocker()


def get_http_mocker() -> SmartHTTPMocker:
    """Get the global HTTP mocker instance."""
    return _global_mocker


def reset_http_mocker():
    """Reset the global HTTP mocker state."""
    global _global_mocker
    _global_mocker = SmartHTTPMocker()
