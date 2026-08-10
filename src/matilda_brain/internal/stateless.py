"""Stateless entry point for TTT - accepts message, history, tools without creating sessions."""

import json
from typing import Any, Dict, List, Optional

from ..core.models import AIResponse
from ..core.request import (
    AIRequest,
    StatelessRequest,
    StatelessResponse,
    execute_request_with_model,
)
from ..core.routing import router
from .protocol import ContentKind, Message, Proposal, RiskLevel, Role
from .utils import get_logger, run_async

logger = get_logger(__name__)


async def _execute_stateless(req: StatelessRequest) -> StatelessResponse:
    logger.debug(
        f"Stateless request: message={req.message[:50]}..., "
        f"history_len={len(req.history)}, tools={req.tools}, model={req.model}"
    )
    messages: List[Dict[str, Any]] = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    messages.extend(req.history)
    messages.append({"role": "user", "content": req.message})
    request = AIRequest(
        prompt=req.message,
        model=req.model,
        system=req.system,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        backend=req.backend,
        tools=req.tools,
        messages=messages if len(messages) > 1 else None,
        include_messages=True,
        options={**req.options, "timeout": req.timeout},
    )
    ai_response, resolved_model = await execute_request_with_model(request, router)
    return _to_stateless_response(ai_response, resolved_model)


def _to_stateless_response(ai_response: AIResponse, resolved_model: Optional[str]) -> StatelessResponse:
    content_attr = getattr(ai_response, "content", None)
    content = content_attr if isinstance(content_attr, str) else str(ai_response)
    finish_reason_attr = getattr(ai_response, "finish_reason", None)
    finish_reason = finish_reason_attr if isinstance(finish_reason_attr, str) else "stop"
    usage_attr = getattr(ai_response, "usage", None)
    usage: Optional[Dict[str, Any]] = usage_attr if isinstance(usage_attr, dict) else None
    tool_calls_attr = getattr(ai_response, "tool_calls", None)
    tool_calls = tool_calls_attr if isinstance(tool_calls_attr, list) else None
    tool_result = getattr(ai_response, "tool_result", None)
    if tool_calls is None and tool_result:
        tool_calls = [call.to_dict() for call in tool_result.calls]

    tokens_in = getattr(ai_response, "tokens_in", None)
    tokens_out = getattr(ai_response, "tokens_out", None)
    if usage is None:
        usage = {
            "prompt_tokens": tokens_in,
            "completion_tokens": tokens_out,
            "total_tokens": (
                (tokens_in or 0) + (tokens_out or 0) if (tokens_in is not None or tokens_out is not None) else None
            ),
        }
    return StatelessResponse(
        content=content,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=usage,
        model=resolved_model,
    )


def execute_stateless(req: StatelessRequest) -> StatelessResponse:
    """Execute a request without creating or persisting session state."""
    try:
        return run_async(_execute_stateless(req))
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
            if response.model:
                msg.metadata["model"] = response.model
            return msg.to_protocol_json()

        else:
            # Standard Text Response
            msg = Message.assistant(response.content)
            if response.model:
                msg.metadata["model"] = response.model
            return msg.to_protocol_json()

    except Exception as e:
        logger.exception("Error during stateless protocol execution")
        # Return Protocol Error
        error_msg = Message(role=Role.SYSTEM, kind=ContentKind.ERROR, code="execution_failed", message=str(e))
        return error_msg.to_protocol_json()
