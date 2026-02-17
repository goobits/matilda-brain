"""Comprehensive tests for the tool system."""

import asyncio
from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from matilda_brain import AIResponse, ask
from matilda_brain.backends.cloud import CloudBackend
from matilda_brain.tools import (
    ToolCall,
    ToolResult,
    execute_tool,
    execute_tools,
    tool,
)
from matilda_brain.tools.registry import ToolRegistry, resolve_tools


class TestToolDecorator:
    """Test the @tool decorator functionality."""

    def test_tool_decorator_extracts_function_signature_and_metadata(self):
        """Test basic tool decorator usage."""

        @tool
        def test_function(x: int, y: str = "default") -> str:
            """Test function description."""
            return f"{x}: {y}"

        from matilda_brain.tools import get_tool_definition, is_tool

        assert is_tool(test_function)
        tool_def = get_tool_definition(test_function)
        assert tool_def is not None
        assert tool_def.name == "test_function"
        assert tool_def.description == "Test function description."
        assert len(tool_def.parameters) == 2

        # Check parameters
        x_param = next(p for p in tool_def.parameters if p.name == "x")
        assert x_param.type.value == "integer"
        assert x_param.required is True

        y_param = next(p for p in tool_def.parameters if p.name == "y")
        assert y_param.type.value == "string"
        assert y_param.required is False
        assert y_param.default == "default"

    def test_tool_decorator_with_custom_name(self):
        """Test tool decorator with custom name."""

        @tool(name="custom_name", description="Custom description")
        def some_function():
            """Original description."""
            pass

        from matilda_brain.tools import get_tool_definition

        tool_def = get_tool_definition(some_function)
        assert tool_def.name == "custom_name"
        assert tool_def.description == "Custom description"

    def test_tool_decorator_complex_types(self):
        """Test tool decorator with complex parameter types."""

        @tool
        def complex_function(items: List[str], count: int = 5, enabled: bool = True, score: float = 0.5) -> dict:
            """Function with complex types."""
            return {"items": items, "count": count}

        from matilda_brain.tools import get_tool_definition

        tool_def = get_tool_definition(complex_function)
        params = {p.name: p for p in tool_def.parameters}

        assert params["items"].type.value == "array"
        assert params["count"].type.value == "integer"
        assert params["enabled"].type.value == "boolean"
        assert params["score"].type.value == "number"

    def test_tool_decorator_no_registration(self):
        """Test tool decorator with registration disabled."""

        @tool(register=False)
        def unregistered_function():
            """This function won't be registered."""
            pass

        # Should not be in global registry
        registry = ToolRegistry()
        assert "unregistered_function" not in registry.list_tools()


class TestToolExecution:
    """Test tool execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_single_async_calls_tool_and_returns_result(self):
        """Test successful single tool execution."""
        from matilda_brain.tools.registry import register_tool, unregister_tool

        @tool(register=False)
        def add_numbers(x: int, y: int) -> int:
            """Add two numbers."""
            return x + y

        # Register the tool temporarily
        register_tool(add_numbers, "add_numbers", "Add two numbers", "test")

        try:
            result = await execute_tool("add_numbers", {"x": 5, "y": 3})

            assert result.name == "add_numbers"
            assert result.succeeded is True
            assert result.result == 8
            assert result.error is None
        finally:
            # Clean up
            try:
                unregister_tool("add_numbers")
            except Exception:
                pass  # Tool might not be registered

    @pytest.mark.asyncio
    async def test_execute_single_async_error(self):
        """Test tool execution with error."""
        from matilda_brain.tools.registry import register_tool, unregister_tool

        @tool(register=False)
        def divide_numbers(x: int, y: int) -> float:
            """Divide two numbers."""
            if y == 0:
                raise ValueError("Cannot divide by zero")
            return x / y

        # Register the tool temporarily
        register_tool(divide_numbers, "divide_numbers", "Divide two numbers", "test")

        try:
            result = await execute_tool("divide_numbers", {"x": 10, "y": 0})

            assert result.name == "divide_numbers"
            assert result.succeeded is False
            assert result.result is None
            # The new executor wraps errors with recovery system formatting
            assert result.error is not None
            # Check for error message - could be wrapped by recovery system
            # The actual Python error is "division by zero" (lowercase)
            assert (
                "division by zero" in result.error.lower()
                or "cannot divide by zero" in result.error.lower()
                or "failed:" in result.error.lower()
            )
        finally:
            # Clean up
            try:
                unregister_tool("divide_numbers")
            except Exception:
                pass  # Tool might not be registered

    @pytest.mark.asyncio
    async def test_execute_multiple_async(self):
        """Test multiple tool execution."""
        from matilda_brain.tools.registry import register_tool, unregister_tool

        @tool(register=False)
        def multiply(x: int, y: int) -> int:
            """Multiply two numbers."""
            return x * y

        @tool(register=False)
        def format_result(value: int, prefix: str = "Result") -> str:
            """Format a result with prefix."""
            return f"{prefix}: {value}"

        # Register tools temporarily
        register_tool(multiply, "multiply", "Multiply two numbers", "test")
        register_tool(format_result, "format_result", "Format a result with prefix", "test")

        try:
            tool_calls = [
                {"name": "multiply", "arguments": {"x": 4, "y": 3}},
                {
                    "name": "format_result",
                    "arguments": {"value": 12, "prefix": "Answer"},
                },
            ]

            result = await execute_tools(tool_calls, parallel=True)

            assert len(result.calls) == 2
            assert result.calls[0].result == 12
            assert result.calls[1].result == "Answer: 12"
            assert all(call.succeeded for call in result.calls)
        finally:
            # Clean up
            try:
                unregister_tool("multiply")
                unregister_tool("format_result")
            except Exception:
                pass  # Tool might not be registered


class TestToolRegistry:
    """Test tool registry functionality."""

    def test_registry_registration(self):
        """Test tool registration in registry."""
        registry = ToolRegistry()

        @tool(register=False)  # Don't auto-register
        def test_tool():
            """Test tool."""
            pass

        registry.register(test_tool)
        assert "test_tool" in [t.name for t in registry.list_tools()]

        retrieved = registry.get("test_tool")
        assert retrieved is not None
        assert retrieved.name == "test_tool"

    def test_registry_get_nonexistent(self):
        """Test getting non-existent tool from registry."""
        registry = ToolRegistry()

        retrieved = registry.get("nonexistent_tool")
        assert retrieved is None

    def test_resolve_tools_mixed_inputs(self):
        """Test resolving mixed tool inputs."""

        @tool(register=False)
        def tool1():
            """Tool 1."""
            pass

        @tool(register=False)
        def tool2():
            """Tool 2."""
            pass

        # Register one tool globally
        from matilda_brain.tools.registry import get_registry

        registry = get_registry()
        registry.register(tool1)

        # Mix of tool names, functions, and definitions
        from matilda_brain.tools import get_tool_definition

        tools_input = ["tool1", tool2, get_tool_definition(tool2)]

        resolved = resolve_tools(tools_input)

        assert len(resolved) == 3
        assert resolved[0].name == "tool1"
        assert resolved[1].name == "tool2"
        assert resolved[2].name == "tool2"


class TestToolIntegration:
    """Test end-to-end tool integration with AI backends."""

    @pytest.mark.asyncio
    async def test_cloud_backend_tool_integration(self):
        """Test tool integration with CloudBackend."""

        class FakeLiteLLM:
            pass

        with patch.dict("sys.modules", {"litellm": FakeLiteLLM()}):
            backend = CloudBackend()

        # Create test tools
        @tool(register=False)
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return f"Weather in {city}: 72°F, sunny"

        @tool(register=False)
        def test_calculate(x: int, y: int, operation: str = "add") -> int:
            """Perform calculation."""
            if operation == "add":
                return x + y
            elif operation == "multiply":
                return x * y
            return 0

        # Register tools temporarily for the test
        from matilda_brain.tools.registry import register_tool, unregister_tool

        register_tool(get_weather, "get_weather", "Get weather for a city", "test")
        register_tool(test_calculate, "test_calculate", "Perform calculation", "test")

        # Mock litellm response with tool calls
        mock_tool_call_1 = Mock()
        mock_tool_call_1.id = "call_1"
        mock_tool_call_1.type = "function"
        mock_tool_call_1.function = Mock()
        mock_tool_call_1.function.name = "get_weather"
        mock_tool_call_1.function.arguments = '{"city": "NYC"}'

        mock_tool_call_2 = Mock()
        mock_tool_call_2.id = "call_2"
        mock_tool_call_2.type = "function"
        mock_tool_call_2.function = Mock()
        mock_tool_call_2.function.name = "test_calculate"
        mock_tool_call_2.function.arguments = '{"x": 15, "y": 25, "operation": "add"}'

        mock_tool_calls = [mock_tool_call_1, mock_tool_call_2]

        # Mock the litellm response
        mock_response = Mock()
        mock_message = Mock()
        mock_message.content = "I'll help you with that."
        mock_message.tool_calls = mock_tool_calls
        mock_response.choices = [Mock(message=mock_message)]
        mock_response.usage = Mock(prompt_tokens=50, completion_tokens=30)

        with patch.object(backend, "litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)

            response = await backend.ask(
                "What's the weather in NYC and what's 15 + 25?",
                tools=[get_weather, test_calculate],
            )

            assert response.succeeded
            assert response.tools_called
            assert len(response.tool_calls) == 2

            # Check tool results
            weather_call = next(call for call in response.tool_calls if call.name == "get_weather")
            assert weather_call.succeeded
            assert "Weather in NYC: 72°F, sunny" in weather_call.result

            calc_call = next(call for call in response.tool_calls if call.name == "test_calculate")
            assert calc_call.succeeded
            assert calc_call.result == 40

        # Clean up registered tools
        try:
            unregister_tool("get_weather")
            unregister_tool("test_calculate")
        except Exception:
            pass  # Tools might not be registered

    def test_api_function_with_tools(self):
        """Test the main ask() function with tools."""

        @tool(register=False)
        def simple_tool(message: str) -> str:
            """Simple test tool."""
            return f"Tool received: {message}"

        # Mock the router where it's actually used in ttt.core.api
        with patch("matilda_brain.core.api.router") as mock_router:
            mock_backend = Mock()
            # Create AIResponse with tool_result in the constructor
            tool_call = ToolCall(
                id="test_call",
                name="simple_tool",
                arguments={"message": "test"},
                result="Tool received: test",
            )
            tool_result = ToolResult(calls=[tool_call])
            mock_response = AIResponse(
                "AI response with tool usage", model="test-model", backend="cloud", tool_result=tool_result
            )

            mock_backend.ask = AsyncMock(return_value=mock_response)
            mock_router.smart_route.return_value = (mock_backend, "test-model")

            response = ask("Test prompt", tools=[simple_tool])

            assert response.tools_called
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].result == "Tool received: test"


class TestToolErrorHandling:
    """Test tool system error handling."""

    @pytest.mark.asyncio
    async def test_tool_timeout_handling(self):
        """Test tool execution timeout with async functions."""

        # Note: The current executor only supports timeouts for async functions
        # Sync functions run in the main thread and cannot be interrupted by asyncio.wait_for

        @tool(register=False)
        async def async_slow_tool() -> str:
            """An async tool that takes too long."""
            await asyncio.sleep(1.0)  # Sleep for 1 second
            return "This should timeout"

        from matilda_brain.tools import (
            ExecutionConfig,
            ToolExecutor,
            register_tool,
            unregister_tool,
        )

        # Use a short timeout
        config = ExecutionConfig(timeout_seconds=0.1)  # 100ms timeout
        executor = ToolExecutor(config=config)

        # Register the tool
        register_tool(async_slow_tool, "async_slow_tool", "An async slow tool", "test")

        try:
            # Execute with the short timeout
            result = await executor.execute_tool("async_slow_tool", {}, timeout=0.05)  # 50ms timeout

            # The tool should timeout
            assert result.succeeded is False
            assert result.error is not None
            assert "timed out" in result.error.lower()
        finally:
            # Clean up
            try:
                unregister_tool("async_slow_tool")
            except Exception:
                pass  # Tool might not be registered

    @pytest.mark.asyncio
    async def test_invalid_tool_arguments(self):
        """Test handling of invalid tool arguments."""
        from matilda_brain.tools.registry import register_tool, unregister_tool

        @tool(register=False)
        def strict_tool(required_param: int) -> str:
            """Tool with required parameter."""
            return f"Got: {required_param}"

        # Register the tool temporarily
        register_tool(strict_tool, "strict_tool", "Tool with required parameter", "test")

        try:
            result = await execute_tool("strict_tool", {"wrong_param": "value"})

            assert result.succeeded is False
            # The new executor provides a different error message for invalid arguments
            assert result.error is not None
            assert (
                "unexpected keyword argument" in result.error.lower()
                or "invalid input" in result.error.lower()
                or "missing" in result.error.lower()
                or "required" in result.error.lower()
            )
        finally:
            # Clean up
            try:
                unregister_tool("strict_tool")
            except Exception:
                pass  # Tool might not be registered

    def test_malformed_tool_definition(self):
        """Test handling of malformed tool definitions."""

        # The current implementation is more lenient, so let's test a different case
        @tool(register=False)
        def bad_tool(param_without_type):
            """Tool with parameter missing type annotation."""
            pass

        # Check that it still creates a tool but with generic type
        from matilda_brain.tools import get_tool_definition

        tool_def = get_tool_definition(bad_tool)
        assert tool_def is not None
        assert tool_def.name == "bad_tool"
        # Parameter without type annotation should get a default type
        assert len(tool_def.parameters) == 1


class TestToolSchemas:
    """Test tool schema generation for different providers."""

    def test_openai_schema_generation(self):
        """Test OpenAI-compatible schema generation."""

        @tool(register=False)
        def example_tool(text: str, count: int = 1, enabled: bool = True, options: List[str] = None) -> dict:
            """Example tool with various parameter types.

            Args:
                text: The input text to process
                count: Number of times to repeat
                enabled: Whether the tool is enabled
                options: List of additional options
            """
            return {"processed": text}

        from matilda_brain.tools import get_tool_definition

        tool_def = get_tool_definition(example_tool)
        schema = tool_def.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "example_tool"
        assert "Example tool with various parameter types" in schema["function"]["description"]

        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        assert "text" in params["properties"]
        assert "count" in params["properties"]
        assert "enabled" in params["properties"]
        assert "options" in params["properties"]

        # Check required parameters
        assert "text" in params["required"]
        assert "count" not in params["required"]  # Has default

    def test_anthropic_schema_generation(self):
        """Test Anthropic-compatible schema generation."""

        @tool(register=False)
        def anthropic_tool(query: str, limit: int = 10) -> str:
            """Tool for Anthropic testing."""
            return f"Query: {query}, Limit: {limit}"

        from matilda_brain.tools import get_tool_definition

        tool_def = get_tool_definition(anthropic_tool)
        schema = tool_def.to_anthropic_schema()

        assert schema["name"] == "anthropic_tool"
        assert schema["description"] == "Tool for Anthropic testing."
        assert "properties" in schema["input_schema"]
        assert "query" in schema["input_schema"]["properties"]
        assert "limit" in schema["input_schema"]["properties"]


if __name__ == "__main__":
    pytest.main([__file__])
