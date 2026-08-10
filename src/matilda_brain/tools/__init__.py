"""Tool system for the AI library.

This module provides the @tool decorator and core functionality for adding
function calling capabilities to AI interactions.

Example usage:
    @tool
    def get_weather(city: str, units: str = "fahrenheit") -> str:
        '''Get weather information for a city.

        Args:
            city: Name of the city
            units: Temperature units (fahrenheit or celsius)
        '''
        return f"Weather in {city}: 72°{units[0].upper()}"

    # Use the tool
    response = ask("What's the weather in NYC?", tools=[get_weather])
"""

import inspect
from functools import wraps
from typing import Any, Callable, Optional, cast

from .base import (
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolParameterType,
    ToolResult,
    create_tool_definition,
)
from .executor import ToolExecutor, execute_tool, execute_tools, get_execution_stats
from .policy import ExecutionConfig, InputSanitizer, ToolPolicy
from .registry import (
    ToolRegistry,
    clear_registry,
    get_categories,
    get_registry,
    get_tool,
    list_tools,
    register_tool,
    resolve_tools,
    unregister_tool,
)


def _attach_tool_metadata(func: Callable, definition: ToolDefinition) -> None:
    target = cast(Any, func)
    target._tool_definition = definition
    target._is_tool = True


def tool(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "general",
    register: bool = True,
) -> Callable:
    """
    Decorator to mark a function as a tool.

    Can be used with or without parameters:

    @tool
    def simple_tool(arg: str) -> str:
        return f"Result: {arg}"

    @tool(name="custom_name", description="Custom description")
    def complex_tool(arg: str) -> str:
        return f"Result: {arg}"

    Args:
        func: The function to decorate (when used without parentheses)
        name: Custom name for the tool (defaults to function name)
        description: Custom description (defaults to function docstring)
        category: Category for organizing tools
        register: Whether to register in the global registry

    Returns:
        Either the decorated function (retains original behavior) or ToolDefinition
    """

    def decorator(f: Callable) -> Callable:
        # Create tool definition
        tool_def = create_tool_definition(f, name, description, category)

        # Register in global registry if requested
        if register:
            try:
                register_tool(f, name, description, category)
            except ValueError:
                # Tool already registered, that's okay
                pass

        # Add tool metadata to the function
        _attach_tool_metadata(f, tool_def)

        # Create appropriate wrapper based on function type
        if inspect.iscoroutinefunction(f):

            @wraps(f)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Async function still works normally
                return await f(*args, **kwargs)

            # Preserve tool metadata on wrapper
            _attach_tool_metadata(async_wrapper, tool_def)

            return async_wrapper
        else:

            @wraps(f)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Function still works normally
                return f(*args, **kwargs)

            # Preserve tool metadata on wrapper
            _attach_tool_metadata(wrapper, tool_def)

            return wrapper

    if func is None:
        # Called with parameters: @tool(name="...", ...)
        return decorator
    else:
        # Called without parameters: @tool
        return decorator(func)


def is_tool(func: Callable) -> bool:
    """Check if a function is decorated as a tool."""
    return getattr(func, "_is_tool", False)


def get_tool_definition(func: Callable) -> Optional[ToolDefinition]:
    """Get the ToolDefinition for a decorated function."""
    return getattr(func, "_tool_definition", None)


# Export all public classes and functions
__all__ = [
    # Decorator
    "tool",
    "is_tool",
    "get_tool_definition",
    # Base classes
    "ToolDefinition",
    "ToolCall",
    "ToolResult",
    "ToolParameter",
    "ToolParameterType",
    "create_tool_definition",
    # Registry functions
    "ToolRegistry",
    "register_tool",
    "unregister_tool",
    "get_tool",
    "list_tools",
    "get_categories",
    "resolve_tools",
    "clear_registry",
    "get_registry",
    # Execution functions
    "ToolExecutor",
    "ExecutionConfig",
    "InputSanitizer",
    "ToolPolicy",
    "execute_tool",
    "execute_tools",
    "get_execution_stats",
]
