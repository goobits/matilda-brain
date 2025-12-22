"""Stateless entry point for TTT - accepts message, history, tools without creating sessions."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .backends import BaseBackend
from .core.models import AIResponse
from .core.routing import router
from .utils import get_logger, run_async

logger = get_logger(__name__)


@dataclass
class StatelessRequest:
    """Request for stateless TTT execution.

    Attributes:
        message: User message to send
        system: System prompt to set context (optional)
        history: Conversation history in standard format (optional)
        tools: List of tool names or functions to enable (optional)
        model: Specific model to use (optional)
        temperature: Sampling temperature 0-2 (default: 0.7)
        max_tokens: Maximum tokens to generate (default: 2048)
        timeout: Request timeout in seconds (default: 30)
    """

    message: str
    system: Optional[str] = None
    history: List[Dict[str, str]] = field(default_factory=list)
    tools: Optional[List[str]] = None
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 30


@dataclass
class StatelessResponse:
    """Response from stateless TTT execution.

    Attributes:
        content: The assistant's response text
        tool_calls: List of tool calls made (if any)
        finish_reason: Reason for completion (stop, length, tool_calls, etc.)
        usage: Token usage information (if available)
        model: Model that generated the response
    """

    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: str = "stop"
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None


def execute_stateless(req: StatelessRequest) -> StatelessResponse:
    """Execute a stateless TTT request.

    This function processes a single request without creating or persisting
    any session state. It builds messages from system prompt, history, and
    user message, then calls the appropriate backend.

    Args:
        req: StatelessRequest with all parameters

    Returns:
        StatelessResponse with the assistant's reply

    Examples:
        >>> req = StatelessRequest(
        ...     message="What is Python?",
        ...     system="You are a helpful assistant"
        ... )
        >>> response = execute_stateless(req)
        >>> print(response.content)

        >>> # With history
        >>> req = StatelessRequest(
        ...     message="What was my first question?",
        ...     history=[
        ...         {"role": "user", "content": "Hello"},
        ...         {"role": "assistant", "content": "Hi! How can I help?"}
        ...     ]
        ... )
        >>> response = execute_stateless(req)
    """
    logger.debug(
        f"Stateless request: message={req.message[:50]}..., "
        f"history_len={len(req.history)}, tools={req.tools}, model={req.model}"
    )

    # Use router to select backend
    backend_instance, resolved_model = router.smart_route(
        req.message,
        model=req.model,
        backend=None,
    )

    # Build messages list from history and new message
    messages = []

    # Add system prompt if provided
    if req.system:
        messages.append({"role": "system", "content": req.system})

    # Add history (should already be in correct format)
    if req.history:
        messages.extend(req.history)

    # Add new user message
    messages.append({"role": "user", "content": req.message})

    # Convert messages to prompt format for backend
    # For backends that use prompt-based API, we need to extract the last user message
    # But we'll pass full messages via kwargs for backends that support it
    async def _execute() -> AIResponse:
        # Call backend with full context
        # The backend's ask() method handles conversation context
        result = await backend_instance.ask(
            req.message,
            model=resolved_model,
            system=req.system,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            tools=req.tools,
            # Pass messages for backends that support conversation history
            messages=messages if len(messages) > 1 else None,
        )
        return result

    # Execute the request
    ai_response = run_async(_execute())

    # Convert AIResponse to StatelessResponse
    response = StatelessResponse(
        content=str(ai_response.content),
        tool_calls=ai_response.tool_calls if hasattr(ai_response, "tool_calls") else None,
        finish_reason=ai_response.finish_reason if hasattr(ai_response, "finish_reason") else "stop",
        usage=ai_response.usage if hasattr(ai_response, "usage") else None,
        model=ai_response.model if hasattr(ai_response, "model") else resolved_model,
    )

    logger.debug(f"Stateless response: content_len={len(response.content)}, finish={response.finish_reason}")

    return response
