"""Enhanced tool execution system with recovery and retry capabilities."""

import asyncio
import inspect
import logging
import time
from typing import Any, Dict, List, Mapping, Optional, Union

from ..internal.utils import get_logger
from .base import ToolCall, ToolDefinition, ToolResult
from .policy import ExecutionConfig, ToolPolicy
from .recovery import ErrorRecoverySystem, RetryConfig
from .registry import get_tool, list_tools

logger = get_logger(__name__)


class ToolExecutor:
    """Enhanced tool executor with recovery, retry, and fallback capabilities."""

    def __init__(self, config: Optional[ExecutionConfig] = None):
        self.config = config or ExecutionConfig()
        self.recovery_system = ErrorRecoverySystem(
            RetryConfig(max_attempts=self.config.max_retries, base_delay=1.0, max_delay=30.0)
        )
        self.policy = ToolPolicy(self.config)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, self.config.log_level))

        # Performance tracking
        self.execution_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "proposed_calls": 0,
            "retried_calls": 0,
            "fallback_calls": 0,
            "avg_execution_time": 0.0,
        }

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: Optional[float] = None,
        approved: bool = False,
        call_id: Optional[str] = None,
        tool_definitions: Optional[Mapping[str, ToolDefinition]] = None,
    ) -> ToolCall:
        """Execute a single tool with full recovery support."""
        start_time = time.time()
        call_id = call_id or f"{tool_name}_{int(start_time * 1000)}"
        execution_timeout = timeout or self.config.timeout_seconds

        self.execution_stats["total_calls"] += 1

        try:
            # Get tool definition
            tool = tool_definitions.get(tool_name) if tool_definitions is not None else get_tool(tool_name)
            if not tool:
                return self._finish_call(
                    ToolCall(
                        id=call_id,
                        name=tool_name,
                        arguments=arguments,
                        error=self._create_tool_not_found_error(
                            tool_name,
                            list(tool_definitions) if tool_definitions is not None else None,
                        ),
                    ),
                    start_time,
                )

            # Sanitize inputs if enabled
            if self.config.enable_input_sanitization:
                try:
                    arguments = self.policy.sanitize_arguments(tool_name, arguments)
                except ValueError as e:
                    return self._finish_call(
                        ToolCall(
                            id=call_id,
                            name=tool_name,
                            arguments=arguments,
                            error=f"Input validation failed: {e}",
                        ),
                        start_time,
                    )

            proposal = self.policy.authorize(tool_name, arguments, approved=approved)
            if proposal is not None:
                self.execution_stats["proposed_calls"] += 1
                return ToolCall(
                    id=call_id,
                    name=tool_name,
                    arguments=arguments,
                    error="Approval required before tool execution",
                    proposal=proposal,
                )

            # Execute with timeout and recovery
            result = await asyncio.wait_for(
                self._execute_with_recovery(tool, arguments, call_id, tool_definitions=tool_definitions),
                timeout=execution_timeout,
            )

            return self._finish_call(result, start_time)

        except asyncio.TimeoutError:
            return self._finish_call(
                ToolCall(
                    id=call_id,
                    name=tool_name,
                    arguments=arguments,
                    error=f"⏱️ Tool execution timed out after {execution_timeout} seconds\n💡 Try reducing the complexity of your request or increase the timeout",
                ),
                start_time,
            )
        except Exception as e:
            self.logger.exception(f"Unexpected error executing {tool_name}")
            return self._finish_call(
                ToolCall(
                    id=call_id,
                    name=tool_name,
                    arguments=arguments,
                    error=f"❌ Unexpected error: {e}\n💡 This appears to be a system error. Please try again or contact support.",
                ),
                start_time,
            )

    async def execute_tools(
        self,
        tool_calls: List[Dict[str, Any]],
        parallel: bool = False,
        approved: bool = False,
        tool_definitions: Optional[Mapping[str, ToolDefinition]] = None,
    ) -> ToolResult:
        """Execute multiple tools with optional parallel execution."""

        async def execute_call(call: Dict[str, Any]) -> ToolCall:
            call_id = str(call.get("id") or f"{call.get('name', 'tool')}_{int(time.time() * 1000)}")
            if call.get("error"):
                return ToolCall(
                    id=call_id,
                    name=str(call.get("name") or "unknown"),
                    arguments=call.get("arguments", {}),
                    error=str(call["error"]),
                )
            return await self.execute_tool(
                str(call["name"]),
                call.get("arguments", {}),
                approved=approved,
                call_id=call_id,
                tool_definitions=tool_definitions,
            )

        if parallel:
            tasks = [execute_call(call) for call in tool_calls]
            results: List[Union[ToolCall, BaseException]] = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert exceptions to error tool calls
            processed_results: List[ToolCall] = []
            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    call = tool_calls[i]
                    processed_results.append(
                        ToolCall(
                            id=str(call.get("id") or f"error_{i}_{int(time.time() * 1000)}"),
                            name=str(call.get("name") or "unknown"),
                            arguments=call.get("arguments", {}),
                            error=f"Parallel execution error: {result}",
                        )
                    )
                else:
                    # result should be a ToolCall
                    assert isinstance(result, ToolCall)
                    processed_results.append(result)

            return ToolResult(calls=processed_results)
        else:
            # Execute tools sequentially
            sequential_results: List[ToolCall] = []
            for call in tool_calls:
                result = await execute_call(call)
                sequential_results.append(result)

                # If a critical tool fails, consider stopping execution
                if not result.succeeded and self._is_critical_failure(result):
                    self.logger.warning(f"Critical tool failure, stopping execution: {result.error}")
                    break

            return ToolResult(calls=sequential_results)

    async def _execute_with_recovery(
        self,
        tool: ToolDefinition,
        arguments: Dict[str, Any],
        call_id: str,
        attempt: int = 1,
        tool_definitions: Optional[Mapping[str, ToolDefinition]] = None,
    ) -> ToolCall:
        """Execute tool with recovery and retry logic."""
        try:
            # Execute the tool function
            if inspect.iscoroutinefunction(tool.function):
                result = await tool.function(**arguments)
            else:
                # Run sync functions in thread pool to avoid blocking event loop
                result = await asyncio.to_thread(tool.function, **arguments)

            return ToolCall(id=call_id, name=tool.name, arguments=arguments, result=result)

        except Exception as e:
            error_message = str(e)
            error_pattern = self.recovery_system.classify_error(error_message)

            self.logger.warning(f"Tool {tool.name} failed (attempt {attempt}): {error_message}")

            # Check if we should retry
            if self.recovery_system.should_retry(error_pattern, attempt):
                self.execution_stats["retried_calls"] += 1

                # Calculate delay and retry
                delay = self.recovery_system.calculate_retry_delay(attempt, error_pattern)
                self.logger.info(f"Retrying {tool.name} in {delay:.1f} seconds...")

                await asyncio.sleep(delay)
                return await self._execute_with_recovery(
                    tool,
                    arguments,
                    call_id,
                    attempt + 1,
                    tool_definitions,
                )

            # If retry failed or not allowed, try fallbacks
            elif self.config.enable_fallbacks:
                fallback_result = await self._try_fallbacks(
                    tool.name,
                    arguments,
                    error_pattern,
                    call_id,
                    tool_definitions,
                )
                if fallback_result:
                    self.execution_stats["fallback_calls"] += 1
                    return fallback_result

            # Create enhanced error message
            recovery_message = self.recovery_system.create_recovery_message(
                ToolCall(call_id, tool.name, arguments, error=error_message),
                error_pattern,
            )

            return ToolCall(id=call_id, name=tool.name, arguments=arguments, error=recovery_message)

    async def _try_fallbacks(
        self,
        failed_tool: str,
        original_args: Dict[str, Any],
        error_pattern: Any,
        call_id: str,
        tool_definitions: Optional[Mapping[str, ToolDefinition]],
    ) -> Optional[ToolCall]:
        """Try fallback tools when the primary tool fails."""
        suggestions = self.recovery_system.get_fallback_suggestions(failed_tool, original_args)

        for suggestion in suggestions:
            try:
                self.logger.info(f"Trying fallback: {suggestion.tool_name}")

                fallback_tool = (
                    tool_definitions.get(suggestion.tool_name)
                    if tool_definitions is not None
                    else get_tool(suggestion.tool_name)
                )
                if not fallback_tool:
                    continue

                sanitized_arguments = self.policy.sanitize_arguments(suggestion.tool_name, suggestion.arguments)
                proposal = self.policy.authorize(suggestion.tool_name, sanitized_arguments)
                if proposal is not None:
                    return ToolCall(
                        id=call_id,
                        name=suggestion.tool_name,
                        arguments=sanitized_arguments,
                        error="Approval required before fallback tool execution",
                        proposal=proposal,
                    )

                # Execute fallback with limited retries
                if inspect.iscoroutinefunction(fallback_tool.function):
                    result = await fallback_tool.function(**sanitized_arguments)
                else:
                    result = await asyncio.to_thread(fallback_tool.function, **sanitized_arguments)

                # Add fallback notification to result
                fallback_notice = (
                    f"\n\n🔧 Note: Used fallback tool '{suggestion.tool_name}' because '{failed_tool}' failed."
                )
                if isinstance(result, str):
                    result = result + fallback_notice

                return ToolCall(
                    id=call_id,
                    name=suggestion.tool_name,
                    arguments=sanitized_arguments,
                    result=result,
                )

            except Exception:
                self.logger.exception(f"Fallback {suggestion.tool_name} also failed")
                continue

        return None

    def _create_tool_not_found_error(self, tool_name: str, available_tools: Optional[List[str]] = None) -> str:
        """Create helpful error message when tool is not found."""
        available_tools = available_tools if available_tools is not None else [tool.name for tool in list_tools()]

        # Find similar tools
        similar = []
        for available in available_tools:
            if tool_name.lower() in available.lower() or available.lower() in tool_name.lower():
                similar.append(available)

        error_msg = f"🔍 Tool '{tool_name}' not found"

        if similar:
            error_msg += f"\n💡 Did you mean: {', '.join(similar[:3])}"
        else:
            error_msg += f"\n💡 Available tools: {', '.join(available_tools[:5])}"
            if len(available_tools) > 5:
                error_msg += f" and {len(available_tools) - 5} more"

        error_msg += "\n🔧 Use 'ttt tools-list' to see all available tools"

        return error_msg

    def _is_critical_failure(self, tool_call: ToolCall) -> bool:
        """Determine if a tool failure should stop execution of subsequent tools."""
        # Critical failures that should halt execution
        critical_patterns = [
            "permission denied",
            "authentication failed",
            "access denied",
            "invalid api key",
            "quota exceeded",
        ]

        if tool_call.error:
            error_lower = tool_call.error.lower()
            return any(pattern in error_lower for pattern in critical_patterns)

        return False

    def _update_execution_stats(self, success: bool, execution_time: float) -> None:
        """Update execution statistics."""
        if success:
            self.execution_stats["successful_calls"] += 1
        else:
            self.execution_stats["failed_calls"] += 1

        # Update average execution time
        completed_calls = self.execution_stats["successful_calls"] + self.execution_stats["failed_calls"]
        if completed_calls > 0:
            current_avg = self.execution_stats["avg_execution_time"]
            self.execution_stats["avg_execution_time"] = (
                current_avg * (completed_calls - 1) + execution_time
            ) / completed_calls

    def _finish_call(self, call: ToolCall, start_time: float) -> ToolCall:
        self._update_execution_stats(call.succeeded, time.time() - start_time)
        return call

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        stats = self.execution_stats.copy()

        # Add calculated metrics
        total = stats["total_calls"]
        if total > 0:
            stats["success_rate"] = stats["successful_calls"] / total
            stats["failure_rate"] = stats["failed_calls"] / total
            stats["proposal_rate"] = stats["proposed_calls"] / total
            stats["retry_rate"] = stats["retried_calls"] / total
            stats["fallback_rate"] = stats["fallback_calls"] / total

        return stats

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self.execution_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "proposed_calls": 0,
            "retried_calls": 0,
            "fallback_calls": 0,
            "avg_execution_time": 0.0,
        }

    async def execute_multiple_async(
        self,
        tool_calls: List[Dict[str, Any]],
        tool_definitions: Dict[str, ToolDefinition],
    ) -> ToolResult:
        """Execute tool calls against an explicit definition map."""
        return await self.execute_tools(tool_calls, parallel=True, tool_definitions=tool_definitions)


# Global executor instance
global_executor = ToolExecutor()


async def execute_tool(tool_name: str, arguments: Dict[str, Any], **kwargs: Any) -> ToolCall:
    """Execute a tool using the global executor."""
    return await global_executor.execute_tool(tool_name, arguments, **kwargs)


async def execute_tools(tool_calls: List[Dict[str, Any]], **kwargs: Any) -> ToolResult:
    """Execute multiple tools using the global executor."""
    return await global_executor.execute_tools(tool_calls, **kwargs)


def get_execution_stats() -> Dict[str, Any]:
    """Get execution statistics from the global executor."""
    return global_executor.get_execution_stats()
