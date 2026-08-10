"""Provider-neutral execution loop for model-requested tools."""

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional

from ..core.exceptions import ResponseError
from .base import ToolCall, ToolDefinition, ToolResult
from .executor import ToolExecutor, global_executor


@dataclass
class ToolRequest:
    """Normalized tool request emitted by a model provider."""

    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    raw_arguments: str = "{}"
    error: Optional[str] = None

    def to_executor_call(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "error": self.error,
        }

    def to_provider_call(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.raw_arguments},
        }


@dataclass
class ToolCompletion:
    """Normalized provider completion consumed by the tool loop."""

    content: str
    tool_calls: List[ToolRequest] = field(default_factory=list)
    finish_reason: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost: Optional[float] = None


@dataclass
class ToolLoopResult:
    """Final completion plus cumulative tool and usage metadata."""

    completion: ToolCompletion
    tool_result: Optional[ToolResult]
    rounds: int
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    cost: Optional[float]
    approval_required: bool = False


Completion = Callable[[List[Dict[str, Any]]], Awaitable[ToolCompletion]]


async def run_tool_loop(
    messages: List[Dict[str, Any]],
    definitions: Mapping[str, ToolDefinition],
    complete: Completion,
    *,
    max_rounds: int,
    parallel: bool = True,
    approved: bool = False,
    executor: Optional[ToolExecutor] = None,
) -> ToolLoopResult:
    """Complete, execute requested tools, and return results to the model."""
    if max_rounds < 0:
        raise ValueError("max_rounds must be non-negative")

    active_executor = executor or global_executor
    conversation = list(messages)
    calls: List[ToolCall] = []
    rounds = 0
    tokens_in = tokens_out = 0
    saw_tokens_in = saw_tokens_out = False
    total_cost = 0.0
    saw_cost = False

    while True:
        completion = await complete(conversation)
        if completion.tokens_in is not None:
            tokens_in += completion.tokens_in
            saw_tokens_in = True
        if completion.tokens_out is not None:
            tokens_out += completion.tokens_out
            saw_tokens_out = True
        if completion.cost is not None:
            total_cost += completion.cost
            saw_cost = True

        if not completion.tool_calls:
            return ToolLoopResult(
                completion=completion,
                tool_result=ToolResult(calls) if calls else None,
                rounds=rounds,
                tokens_in=tokens_in if saw_tokens_in else None,
                tokens_out=tokens_out if saw_tokens_out else None,
                cost=total_cost if saw_cost else None,
            )
        if rounds >= max_rounds:
            raise ResponseError(f"Tool execution exceeded the configured limit of {max_rounds} rounds")

        batch = await active_executor.execute_tools(
            [request.to_executor_call() for request in completion.tool_calls],
            parallel=parallel,
            approved=approved,
            tool_definitions=definitions,
        )
        batch = _align_results(completion.tool_calls, batch)
        calls.extend(batch.calls)
        rounds += 1
        if any(call.proposal is not None for call in batch.calls):
            return ToolLoopResult(
                completion=completion,
                tool_result=ToolResult(calls),
                rounds=rounds,
                tokens_in=tokens_in if saw_tokens_in else None,
                tokens_out=tokens_out if saw_tokens_out else None,
                cost=total_cost if saw_cost else None,
                approval_required=True,
            )

        conversation.append(
            {
                "role": "assistant",
                "content": completion.content or None,
                "tool_calls": [request.to_provider_call() for request in completion.tool_calls],
            }
        )
        conversation.extend(_tool_messages(completion.tool_calls, batch))


def _align_results(requests: List[ToolRequest], result: ToolResult) -> ToolResult:
    by_id = {call.id: call for call in result.calls}
    return ToolResult(
        [
            by_id.get(request.id)
            or ToolCall(
                id=request.id,
                name=request.name,
                arguments=request.arguments,
                error="Tool execution was skipped",
            )
            for request in requests
        ]
    )


def _tool_messages(requests: List[ToolRequest], result: ToolResult) -> List[Dict[str, Any]]:
    return [
        {
            "role": "tool",
            "tool_call_id": call.id,
            "name": request.name,
            "content": _serialize_result(call),
        }
        for request, call in zip(requests, result.calls, strict=True)
    ]


def _serialize_result(call: ToolCall) -> str:
    if call.error:
        value: Any = {"error": call.error}
    else:
        value = call.result
    return value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
