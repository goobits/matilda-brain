"""Core API functions providing the main user interface."""

from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator, List, Optional, Union

from ..backends import BaseBackend
from ..plugins import discover_plugins
from ..session.chat import PersistentChatSession
from ..utils import get_logger, run_async, run_coro_in_background
from .models import AIResponse, ImageInput
from .routing import router

# Backward compatibility alias - prefer PersistentChatSession in new code
ChatSession = PersistentChatSession


logger = get_logger(__name__)

# Initialize plugins on module load
try:
    discover_plugins()
except Exception as e:
    logger.debug(f"Plugin discovery failed: {e}")


def ask(
    prompt: Union[str, List[Union[str, ImageInput]]],
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    backend: Optional[Union[str, BaseBackend]] = None,
    tools: Optional[List] = None,
    **kwargs: Any,
) -> AIResponse:
    """
    Get a response from AI. The simplest way to use AI.

    Examples:
        >>> response = ask("What is Python?")
        >>> print(response)

        >>> response = ask("Fix this code", system="You are a code reviewer")
        >>> print(f"Model: {response.model}, Time: {response.time}s")

        >>> response = ask("Quick question", model="gpt-3.5-turbo")
        >>> response = ask("Complex analysis", model="gpt-4")

        >>> # Multi-modal with images
        >>> response = ask([
        ...     "What's in this image?",
        ...     ImageInput("photo.jpg")
        ... ], model="gpt-4-vision-preview")

        >>> # Multiple images
        >>> response = ask([
        ...     "Compare these images:",
        ...     ImageInput("image1.png"),
        ...     ImageInput("image2.png")
        ... ], backend="cloud")

        >>> # With tools
        >>> def get_weather(city: str) -> str:
        ...     return f"Weather in {city}: 72°F, sunny"
        >>> response = ask("What's the weather in NYC?", tools=[get_weather])
        >>> print(f"Called {len(response.tool_calls)} tools")

    Args:
        prompt: Your question - can be a string or list of content (text/images)
        model: Specific model to use (optional)
        system: System prompt to set context (optional)
        temperature: Sampling temperature 0-1 (optional)
        max_tokens: Maximum tokens to generate (optional)
        backend: Backend to use, "local", "cloud", "auto", or Backend instance (optional)
        tools: List of functions/tools the AI can call (optional)
        **kwargs: Additional backend-specific parameters

    Returns:
        AIResponse that behaves like a string but contains metadata
    """
    logger.debug(f"API ask() called with: model={model}, max_tokens={max_tokens}, temperature={temperature}")
    # Use smart routing
    backend_instance, resolved_model = router.smart_route(
        prompt,
        model=model,
        backend=backend,
        **kwargs,
    )

    async def _ask_wrapper() -> AIResponse:
        return await backend_instance.ask(
            prompt,
            model=resolved_model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            **kwargs,
        )

    return run_async(_ask_wrapper())


def stream(
    prompt: Union[str, List[Union[str, ImageInput]]],
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    backend: Optional[Union[str, BaseBackend]] = None,
    tools: Optional[List] = None,
    **kwargs: Any,
) -> Iterator[str]:
    """
    Stream a response token by token.

    Examples:
        >>> for chunk in stream("Tell me a story"):
        ...     print(chunk, end="", flush=True)

        >>> # Multi-modal streaming
        >>> for chunk in stream([
        ...     "Describe this image:",
        ...     ImageInput("photo.jpg")
        ... ], model="gpt-4-vision-preview"):
        ...     print(chunk, end="", flush=True)

    Args:
        prompt: Your question - can be a string or list of content (text/images)
        model: Specific model to use (optional)
        system: System prompt to set context (optional)
        temperature: Sampling temperature 0-1 (optional)
        max_tokens: Maximum tokens to generate (optional)
        backend: Backend to use, "local", "cloud", "auto", or Backend instance (optional)
        tools: List of functions/tools the AI can call (optional)
        **kwargs: Additional backend-specific parameters

    Yields:
        String chunks as they arrive
    """
    # Use smart routing
    backend_instance, resolved_model = router.smart_route(
        prompt,
        model=model,
        backend=backend,
        **kwargs,
    )

    # This creates an async generator from the backend
    async def _async_generator() -> AsyncIterator[str]:
        async for chunk in backend_instance.astream(
            prompt,
            model=resolved_model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            **kwargs,
        ):
            yield chunk

    # Get the async generator
    async_gen = _async_generator()

    # We create a bridge to pull from the async generator synchronously
    # Using the optimized approach to avoid creating new event loops
    try:
        while True:
            try:
                # Use the background loop to get the next item
                chunk = run_coro_in_background(async_gen.__anext__())
                yield chunk
            except StopAsyncIteration:
                # The async generator is exhausted - no cleanup needed
                break
    finally:
        # Note: We deliberately do NOT call async_gen.aclose() here because
        # it can cause "Task was destroyed but it is pending" errors with aiohttp
        # connections. The LiteLLM library and aiohttp will handle cleanup
        # automatically when the generator goes out of scope.
        pass


@contextmanager
def chat(
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    backend: Optional[Union[str, BaseBackend]] = None,
    session_id: Optional[str] = None,
    tools: Optional[List] = None,
    **kwargs: Any,
) -> Iterator[ChatSession]:
    """
    Context manager for chat sessions.

    Examples:
        >>> with chat() as session:
        ...     response = session.ask("Hello!")
        ...     print(response)
        ...     response = session.ask("What's 2+2?")
        ...     print(response)

        >>> with chat(system="You are a helpful coding assistant") as session:
        ...     response = session.ask("Write a Python function")
        ...     print(response)

        >>> # Session that can be saved
        >>> with chat() as session:
        ...     session.ask("Remember this: My name is Alice")
        ...     session.save("alice_chat.json")

        >>> # Resume a saved session
        >>> from matilda_brain.session.chat import PersistentChatSession
        >>> session = PersistentChatSession.load("alice_chat.json")
        >>> session.ask("What's my name?")  # Will remember it's Alice

        >>> # Chat with tools
        >>> def get_weather(city: str) -> str:
        ...     return f"Weather in {city}: 72°F, sunny"
        >>> with chat(tools=[get_weather]) as session:
        ...     response = session.ask("What's the weather in NYC?")
        ...     print(response)

    Args:
        system: System prompt to set the assistant's behavior
        model: Default model to use for this session
        backend: Backend to use for this session
        session_id: Unique identifier for persistent sessions
        tools: List of functions/tools the AI can call
        **kwargs: Additional parameters passed to each request

    Yields:
        PersistentChatSession instance
    """
    # Always create the powerful session object. It handles both
    # transient and persistent use cases gracefully.
    session = PersistentChatSession(
        system=system,
        model=model,
        backend=backend,
        session_id=session_id,
        tools=tools,
        **kwargs,
    )
    try:
        yield session
    finally:
        # No specific cleanup needed here anymore. The session object
        # can handle its own state. Auto-save logic could be
        # implemented within PersistentChatSession if desired.
        pass


# Async versions for advanced users
async def ask_async(
    prompt: Union[str, List[Union[str, ImageInput]]],
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    backend: Optional[Union[str, BaseBackend]] = None,
    tools: Optional[List] = None,
    **kwargs: Any,
) -> AIResponse:
    """
    Async version of ask().

    Args:
        prompt: Your question - can be a string or list of content (text/images)
        model: Specific model to use (optional)
        system: System prompt to set context (optional)
        temperature: Sampling temperature 0-1 (optional)
        max_tokens: Maximum tokens to generate (optional)
        backend: Backend to use, "local", "cloud", "auto", or Backend instance (optional)
        tools: List of functions/tools the AI can call (optional)
        **kwargs: Additional backend-specific parameters

    Returns:
        AIResponse that behaves like a string but contains metadata
    """
    # Use smart routing (same as synchronous version)
    backend_instance, resolved_model = router.smart_route(
        prompt,
        model=model,
        backend=backend,
        **kwargs,
    )

    return await backend_instance.ask(
        prompt,
        model=resolved_model,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        **kwargs,
    )


async def stream_async(
    prompt: Union[str, List[Union[str, ImageInput]]],
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    backend: Optional[Union[str, BaseBackend]] = None,
    tools: Optional[List] = None,
    **kwargs: Any,
) -> AsyncIterator[str]:
    """
    Async version of stream().

    Args:
        prompt: Your question - can be a string or list of content (text/images)
        model: Specific model to use (optional)
        system: System prompt to set context (optional)
        temperature: Sampling temperature 0-1 (optional)
        max_tokens: Maximum tokens to generate (optional)
        backend: Backend to use, "local", "cloud", "auto", or Backend instance (optional)
        tools: List of functions/tools the AI can call (optional)
        **kwargs: Additional backend-specific parameters

    Yields:
        String chunks as they arrive
    """
    # Use smart routing (same as synchronous version)
    backend_instance, resolved_model = router.smart_route(
        prompt,
        model=model,
        backend=backend,
        **kwargs,
    )

    async for chunk in backend_instance.astream(
        prompt,
        model=resolved_model,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        **kwargs,
    ):
        yield chunk


@asynccontextmanager
async def achat(
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    backend: Optional[Union[str, BaseBackend]] = None,
    session_id: Optional[str] = None,
    tools: Optional[List] = None,
    **kwargs: Any,
) -> AsyncIterator[ChatSession]:
    """
    Async context manager for chat sessions.

    Args:
        system: System prompt to set the assistant's behavior
        model: Default model to use for this session
        backend: Backend to use for this session
        session_id: Unique identifier for persistent sessions
        tools: List of functions/tools the AI can call
        **kwargs: Additional parameters passed to each request

    Yields:
        PersistentChatSession instance
    """
    # Use PersistentChatSession for consistency with sync version
    session = PersistentChatSession(
        system=system,
        model=model,
        backend=backend,
        session_id=session_id,
        tools=tools,
        **kwargs,
    )
    try:
        yield session
    finally:
        pass


def stateless(
    message: str,
    *,
    system: Optional[str] = None,
    history: Optional[List[dict]] = None,
    tools: Optional[List[str]] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    **kwargs: Any,
):
    """
    Execute a stateless AI request without creating a session.

    This is a wrapper around the execute_stateless function that provides
    a clean API-level interface. No session files are created or modified.

    Examples:
        >>> from matilda_brain.core.api import stateless
        >>> response = stateless("What is Python?")
        >>> print(response.content)

        >>> # With system prompt
        >>> response = stateless(
        ...     "Explain quantum computing",
        ...     system="You are a physics professor"
        ... )

        >>> # With conversation history
        >>> response = stateless(
        ...     "What was my first question?",
        ...     history=[
        ...         {"role": "user", "content": "Hello"},
        ...         {"role": "assistant", "content": "Hi! How can I help?"}
        ...     ]
        ... )

        >>> # With tools
        >>> response = stateless(
        ...     "What's the weather in NYC?",
        ...     tools=["web_search"]
        ... )

    Args:
        message: The user's message/question
        system: System prompt to set context (optional)
        history: Previous conversation messages (optional)
        tools: List of tool names to enable (optional)
        model: Specific model to use (optional)
        temperature: Sampling temperature 0-2 (default: 0.7)
        max_tokens: Maximum tokens to generate (default: 2048)
        **kwargs: Additional backend-specific parameters

    Returns:
        StatelessResponse with content, tool_calls, finish_reason, usage, model
    """
    from ..stateless import StatelessRequest, execute_stateless

    request = StatelessRequest(
        message=message,
        system=system,
        history=history or [],
        tools=tools,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )

    return execute_stateless(request)
