"""Stateless entry point for TTT - accepts message, history, tools without creating sessions."""

from typing import Any, Dict, List, Optional, cast

from ..core.models import AIResponse
from ..core.request import (
    AIRequest,
    StatelessRequest,
    StatelessResponse,
    execute_request_with_model,
)
from ..core.routing import router
from .protocol import ContentKind, Message, Proposal, Role
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
    if not isinstance(finish_reason_attr, str):
        finish_reason_attr = ai_response.metadata.get("finish_reason")
    finish_reason = finish_reason_attr if isinstance(finish_reason_attr, str) else "stop"
    usage_attr = getattr(ai_response, "usage", None)
    usage: Optional[Dict[str, Any]] = usage_attr if isinstance(usage_attr, dict) else None
    tool_result = getattr(ai_response, "tool_result", None)
    tool_calls: Optional[List[Dict[str, Any]]]
    if tool_result:
        tool_calls = [call.to_dict() for call in tool_result.calls]
    else:
        tool_calls_attr = getattr(ai_response, "tool_calls", None)
        tool_calls = (
            cast(
                List[Dict[str, Any]],
                [call.to_dict() if hasattr(call, "to_dict") else call for call in tool_calls_attr],
            )
            if isinstance(tool_calls_attr, list)
            else None
        )

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

        proposal_data = next(
            (call.get("proposal") for call in response.tool_calls or [] if call.get("proposal")),
            None,
        )
        if proposal_data:
            proposal = Proposal.model_validate(proposal_data)
            msg = Message.proposal_msg(proposal)
            if response.model:
                msg.metadata["model"] = response.model
            return msg.to_protocol_json()

        msg = Message.assistant(response.content)
        if response.model:
            msg.metadata["model"] = response.model
        return msg.to_protocol_json()

    except Exception as e:
        logger.exception("Error during stateless protocol execution")
        # Return Protocol Error
        error_msg = Message(role=Role.SYSTEM, kind=ContentKind.ERROR, code="execution_failed", message=str(e))
        return error_msg.to_protocol_json()
