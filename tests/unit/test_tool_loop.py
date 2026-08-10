"""Tests for the provider-neutral tool execution loop."""

from typing import Any, Dict, List

import pytest

from matilda_brain.core.exceptions import ResponseError
from matilda_brain.core.types import RiskLevel
from matilda_brain.tools.base import create_tool_definition
from matilda_brain.tools.executor import ToolExecutor
from matilda_brain.tools.loop import ToolCompletion, ToolRequest, run_tool_loop
from matilda_brain.tools.policy import ExecutionConfig


@pytest.mark.asyncio
async def test_tool_result_is_returned_to_model_before_final_response():
    def double(value: int) -> int:
        return value * 2

    definition = create_tool_definition(double)
    seen_messages: List[List[Dict[str, Any]]] = []

    async def complete(messages):
        seen_messages.append(messages)
        if len(seen_messages) == 1:
            return ToolCompletion(
                "",
                [ToolRequest("call_1", "double", {"value": 21}, '{"value": 21}')],
                tokens_in=5,
                tokens_out=2,
            )
        return ToolCompletion("The answer is 42.", tokens_in=3, tokens_out=4)

    result = await run_tool_loop([], {"double": definition}, complete, max_rounds=2)

    assert result.completion.content == "The answer is 42."
    assert result.tool_result is not None
    assert result.tool_result.calls[0].id == "call_1"
    assert result.tool_result.calls[0].result == 42
    assert result.tokens_in == 8
    assert result.tokens_out == 6
    assert seen_messages[1][-1]["content"] == "42"


@pytest.mark.asyncio
async def test_tool_loop_cannot_escape_explicit_definition_scope():
    seen_messages = []

    async def complete(messages):
        seen_messages.append(messages)
        if len(seen_messages) == 1:
            return ToolCompletion("", [ToolRequest("call_1", "read_file")])
        return ToolCompletion("I could not use that tool.")

    result = await run_tool_loop([], {}, complete, max_rounds=2)

    assert result.tool_result is not None
    assert not result.tool_result.calls[0].succeeded
    assert "not found" in (result.tool_result.calls[0].error or "")
    assert "not found" in seen_messages[1][-1]["content"]


@pytest.mark.asyncio
async def test_tool_loop_is_bounded():
    executions = 0

    def repeat() -> str:
        nonlocal executions
        executions += 1
        return "again"

    definition = create_tool_definition(repeat)

    async def complete(messages):
        return ToolCompletion("", [ToolRequest(f"call_{len(messages)}", "repeat")])

    with pytest.raises(ResponseError, match="limit of 1 rounds"):
        await run_tool_loop([], {"repeat": definition}, complete, max_rounds=1)

    assert executions == 1


@pytest.mark.asyncio
async def test_tool_loop_stops_for_required_approval(tmp_path):
    target = tmp_path / "approval.txt"

    def write_file(file_path: str, content: str) -> str:
        target.write_text(content)
        return file_path

    definition = create_tool_definition(write_file)
    executor = ToolExecutor(
        ExecutionConfig(
            allowed_file_roots=[tmp_path],
            require_approval=True,
            approval_threshold=RiskLevel.HIGH,
            max_retries=1,
        )
    )

    async def complete(messages):
        return ToolCompletion(
            "",
            [
                ToolRequest(
                    "call_1",
                    "write_file",
                    {"file_path": str(target), "content": "blocked"},
                )
            ],
        )

    result = await run_tool_loop([], {"write_file": definition}, complete, max_rounds=2, executor=executor)

    assert result.approval_required
    assert result.tool_result is not None
    assert result.tool_result.calls[0].proposal is not None
    assert not target.exists()
