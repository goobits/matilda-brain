"""Enhanced tool execution system with recovery and retry capabilities."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ..internal.utils import get_logger
from .base import ToolCall, ToolDefinition, ToolResult
from .recovery import ErrorRecoverySystem, InputSanitizer, RetryConfig
from .registry import get_tool, list_tools, register_tool

logger = get_logger(__name__)


@dataclass
class ExecutionConfig:
    """Configuration for tool execution."""

    max_retries: Optional[int] = None
    timeout_seconds: Optional[float] = None
    enable_fallbacks: bool = True
    enable_input_sanitization: bool = True
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        """Load defaults from config if not set."""
        from ..config.loader import get_config_value

        if self.max_retries is None:
            self.max_retries = get_config_value("tools.executor.max_retries", 3)
        if self.timeout_seconds is None:
            self.timeout_seconds = get_config_value("tools.executor.timeout_seconds", 30.0)


class ToolExecutor:
    """Enhanced tool executor with recovery, retry, and fallback capabilities."""

    def __init__(self, config: Optional[ExecutionConfig] = None):
        self.config = config or ExecutionConfig()
        self.recovery_system = ErrorRecoverySystem(
            RetryConfig(max_attempts=self.config.max_retries, base_delay=1.0, max_delay=30.0)
        )
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, self.config.log_level))

        # Performance tracking
        self.execution_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retried_calls": 0,
            "fallback_calls": 0,
            "avg_execution_time": 0.0,
        }

    async def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any], timeout: Optional[float] = None
    ) -> ToolCall:
        """Execute a single tool with full recovery support."""
        start_time = time.time()
        call_id = f"{tool_name}_{int(start_time * 1000)}"

        self.execution_stats["total_calls"] += 1

        try:
            # Get tool definition
            tool = get_tool(tool_name)
            if not tool:
                return ToolCall(
                    id=call_id,
                    name=tool_name,
                    arguments=arguments,
                    error=self._create_tool_not_found_error(tool_name),
                )

            # Sanitize inputs if enabled
            if self.config.enable_input_sanitization:
                try:
                    arguments = self._sanitize_inputs(tool_name, arguments)
                except ValueError as e:
                    return ToolCall(
                        id=call_id,
                        name=tool_name,
                        arguments=arguments,
                        error=f"Input validation failed: {e}",
                    )

            # Execute with timeout and recovery
            execution_timeout = timeout or self.config.timeout_seconds
            result = await asyncio.wait_for(
                self._execute_with_recovery(tool, arguments, call_id),
                timeout=execution_timeout,
            )

            # Update stats
            execution_time = time.time() - start_time
            self._update_execution_stats(True, execution_time)

            return result

        except asyncio.TimeoutError:
            self.execution_stats["failed_calls"] += 1
            return ToolCall(
                id=call_id,
                name=tool_name,
                arguments=arguments,
                error=f"⏱️ Tool execution timed out after {execution_timeout} seconds\n💡 Try reducing the complexity of your request or increase the timeout",
            )
        except Exception as e:
            self.execution_stats["failed_calls"] += 1
            self.logger.exception(f"Unexpected error executing {tool_name}")
            return ToolCall(
                id=call_id,
                name=tool_name,
                arguments=arguments,
                error=f"❌ Unexpected error: {e}\n💡 This appears to be a system error. Please try again or contact support.",
            )

    async def execute_tools(self, tool_calls: List[Dict[str, Any]], parallel: bool = False) -> ToolResult:
        """Execute multiple tools with optional parallel execution."""
        if parallel:
            # Execute tools in parallel
            tasks = [self.execute_tool(call["name"], call.get("arguments", {})) for call in tool_calls]
            results: List[Union[ToolCall, BaseException]] = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert exceptions to error tool calls
            processed_results: List[ToolCall] = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    call = tool_calls[i]
                    processed_results.append(
                        ToolCall(
                            id=f"error_{i}_{int(time.time() * 1000)}",
                            name=call["name"],
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
                result = await self.execute_tool(call["name"], call.get("arguments", {}))
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
    ) -> ToolCall:
        """Execute tool with recovery and retry logic."""
        try:
            # Execute the tool function
            if asyncio.iscoroutinefunction(tool.function):
                result = await tool.function(**arguments)
            else:
                result = tool.function(**arguments)

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
                return await self._execute_with_recovery(tool, arguments, call_id, attempt + 1)

            # If retry failed or not allowed, try fallbacks
            elif self.config.enable_fallbacks:
                fallback_result = await self._try_fallbacks(tool.name, arguments, error_pattern)
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
        self, failed_tool: str, original_args: Dict[str, Any], error_pattern: Any
    ) -> Optional[ToolCall]:
        """Try fallback tools when the primary tool fails."""
        suggestions = self.recovery_system.get_fallback_suggestions(failed_tool, original_args)

        for suggestion in suggestions:
            try:
                self.logger.info(f"Trying fallback: {suggestion.tool_name}")

                fallback_tool = get_tool(suggestion.tool_name)
                if not fallback_tool:
                    continue

                # Execute fallback with limited retries
                if asyncio.iscoroutinefunction(fallback_tool.function):
                    result = await fallback_tool.function(**suggestion.arguments)
                else:
                    result = fallback_tool.function(**suggestion.arguments)

                # Add fallback notification to result
                fallback_notice = (
                    f"\n\n🔧 Note: Used fallback tool '{suggestion.tool_name}' because '{failed_tool}' failed."
                )
                if isinstance(result, str):
                    result = result + fallback_notice

                return ToolCall(
                    id=f"fallback_{int(time.time() * 1000)}",
                    name=suggestion.tool_name,
                    arguments=suggestion.arguments,
                    result=result,
                )

            except Exception:
                self.logger.exception(f"Fallback {suggestion.tool_name} also failed")
                continue

        return None

    def _sanitize_inputs(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize tool inputs based on argument types."""
        sanitized = {}

        for key, value in arguments.items():
            if key in ["file_path", "path"]:
                sanitized[key] = str(InputSanitizer.sanitize_path(value))
            elif key in ["url"]:
                sanitized[key] = InputSanitizer.sanitize_url(value)
            elif key in ["query", "code", "expression", "content"]:
                # Allow code for code/expression contexts
                allow_code = key in ["code", "expression"]
                sanitized[key] = InputSanitizer.sanitize_string(value, allow_code=allow_code)
            elif key in ["data"] and isinstance(value, str):
                try:
                    # Validate JSON but keep as string
                    InputSanitizer.sanitize_json(value)
                    sanitized[key] = value
                except ValueError:
                    sanitized[key] = InputSanitizer.sanitize_string(value, allow_code=False)
            else:
                # Basic validation for other types
                if isinstance(value, str):
                    sanitized[key] = InputSanitizer.sanitize_string(value, allow_code=False)
                else:
                    sanitized[key] = value

        return sanitized

    def _create_tool_not_found_error(self, tool_name: str) -> str:
        """Create helpful error message when tool is not found."""
        available_tools = [tool.name for tool in list_tools()]

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
        total_calls = self.execution_stats["total_calls"]
        if total_calls > 0:
            current_avg = self.execution_stats["avg_execution_time"]
            self.execution_stats["avg_execution_time"] = (
                current_avg * (total_calls - 1) + execution_time
            ) / total_calls

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        stats = self.execution_stats.copy()

        # Add calculated metrics
        total = stats["total_calls"]
        if total > 0:
            stats["success_rate"] = stats["successful_calls"] / total
            stats["failure_rate"] = stats["failed_calls"] / total
            stats["retry_rate"] = stats["retried_calls"] / total
            stats["fallback_rate"] = stats["fallback_calls"] / total

        return stats

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self.execution_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retried_calls": 0,
            "fallback_calls": 0,
            "avg_execution_time": 0.0,
        }

    async def execute_multiple_async(
        self,
        tool_calls: List[Dict[str, Any]],
        tool_definitions: Dict[str, ToolDefinition],
    ) -> ToolResult:
        """Execute multiple tool calls asynchronously (compatibility method).

        This method provides backward compatibility with previous execution patterns.
        It temporarily registers any tools not in the global registry.
        """
        # Register any tools that aren't already in the registry
        temp_registered = []
        for tool_name, tool_def in tool_definitions.items():
            if not get_tool(tool_name):
                register_tool(tool_def.function, tool_name, tool_def.description, "test")
                temp_registered.append(tool_name)

        try:
            # Use the new execute_tools method
            return await self.execute_tools(tool_calls, parallel=True)
        finally:
            # Clean up temporarily registered tools
            for tool_name in temp_registered:
                try:
                    from .registry import unregister_tool

                    unregister_tool(tool_name)
                except (ImportError, AttributeError, KeyError) as e:
                    logger.warning(f"Could not unregister temporary tool {tool_name}: {e}")
                except Exception:
                    logger.exception(f"Unexpected error unregistering tool {tool_name}")


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
