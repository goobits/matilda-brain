"""Stateless entry point for TTT - accepts message, history, tools without creating sessions."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json

from ..core.models import AIResponse
from ..core.routing import router
from .utils import get_logger, run_async
from .protocol import Message, Proposal, Role, RiskLevel

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
        content: The response content/text
        tool_calls: List of tool calls requested by the model (optional)
        finish_reason: Reason for completion (default: "stop")
        usage: Token usage statistics (optional)
        model: Model that generated the response (optional)
    """

    content: str
    tool_calls: Optional[List[Dict]] = None
    finish_reason: str = "stop"
    usage: Optional[Dict] = None
    model: Optional[str] = None


def execute_stateless(req: StatelessRequest) -> StatelessResponse:
    """Execute a stateless TTT request and return a StatelessResponse.

    This function processes a single request without creating or persisting
    any session state. It builds messages from system prompt, history, and
    user message, then calls the appropriate backend.

    Args:
        req: StatelessRequest with all parameters

    Returns:
        StatelessResponse with content, tool_calls, finish_reason, usage, model
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

    async def _execute() -> AIResponse:
        # Call backend with full context
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

    try:
        # Execute the request
        ai_response = run_async(_execute())

        # Convert AIResponse to StatelessResponse
        return StatelessResponse(
            content=str(ai_response.content) if ai_response.content else "",
            tool_calls=ai_response.tool_calls,
            finish_reason=ai_response.finish_reason or "stop",
            usage=ai_response.usage,
            model=resolved_model,
        )

    except Exception:
        logger.exception("Error during stateless execution")
        raise


def execute_stateless_protocol(req: StatelessRequest) -> str:
    """Execute a stateless TTT request and return Matilda Protocol JSON.

    This is a wrapper around execute_stateless that converts the response
    to Matilda Protocol JSON format for server/CLI usage.

    Args:
        req: StatelessRequest with all parameters

    Returns:
        JSON string complying with Matilda Protocol (v1)
    """
    try:
        response = execute_stateless(req)

        # Convert to Matilda Protocol Message
        if response.tool_calls:
            # Handle tool call as Proposal
            # For simplicity, we take the first tool call
            tool_call = response.tool_calls[0]

            # Function/Tool name usually in 'function' key or 'name'
            tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name", "unknown")
            args = tool_call.get("arguments") or tool_call.get("function", {}).get("arguments", "{}")

            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}

            proposal = Proposal(
                tool_name="system",  # Grouping under 'system' capability for now
                action_name=tool_name,
                params=args,
                risk_level=RiskLevel.MEDIUM,  # Default to Medium
                reasoning="Agent requested this action.",
            )

            msg = Message.proposal_msg(proposal)
            msg.metadata["model"] = response.model
            return msg.to_protocol_json()

        else:
            # Standard Text Response
            msg = Message.assistant(response.content)
            msg.metadata["model"] = response.model
            return msg.to_protocol_json()

    except Exception as e:
        logger.exception("Error during stateless protocol execution")
        # Return Protocol Error
        error_msg = Message(role=Role.SYSTEM, kind="error", code="execution_failed", message=str(e))
        return error_msg.to_protocol_json()
