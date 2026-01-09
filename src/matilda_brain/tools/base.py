"""Base classes for the tool system."""

import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ToolParameterType(str, Enum):
    """Supported parameter types for tools."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """Represents a single tool parameter."""

    name: str
    type: ToolParameterType
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None


@dataclass
class ToolDefinition:
    """Defines a tool that can be called by the AI."""

    name: str
    description: str
    parameters: List[ToolParameter]
    function: Callable
    category: str = "general"

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling schema.

        Transforms the tool definition into the JSON schema format
        expected by OpenAI's function calling API.

        Returns:
            A dictionary containing the OpenAI-compatible schema with
            function name, description, and parameter specifications.

        Example:
            >>> tool = ToolDefinition(name="greet", description="Say hello", parameters=[])
            >>> schema = tool.to_openai_schema()
            >>> schema["type"]
            "function"
        """
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type.value,
                "description": param.description,
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.default is not None:
                properties[param.name]["default"] = param.default
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def to_anthropic_schema(self) -> Dict[str, Any]:
        """Convert to Anthropic function calling schema.

        Transforms the tool definition into the JSON schema format
        expected by Anthropic's Claude function calling API.

        Returns:
            A dictionary containing the Anthropic-compatible schema with
            function name, description, and input_schema specifications.

        Example:
            >>> tool = ToolDefinition(name="calculate", description="Do math", parameters=[])
            >>> schema = tool.to_anthropic_schema()
            >>> "input_schema" in schema
            True
        """
        input_schema: Dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        for param in self.parameters:
            input_schema["properties"][param.name] = {
                "type": param.type.value,
                "description": param.description,
            }
            if param.enum:
                input_schema["properties"][param.name]["enum"] = param.enum
            if param.default is not None:
                input_schema["properties"][param.name]["default"] = param.default
            if param.required:
                input_schema["required"].append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": input_schema,
        }


@dataclass
class ToolCall:
    """Represents a call to a tool by the AI."""

    id: str
    name: str
    arguments: Dict[str, Any]
    result: Any = None
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        """Check if the tool call succeeded.

        Returns:
            True if no error occurred during execution, False otherwise.
        """
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            A dictionary representation of the tool call including
            all metadata, arguments, results, and success status.
        """
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
            "succeeded": self.succeeded,
        }


@dataclass
class ToolResult:
    """Result of executing one or more tools."""

    calls: List[ToolCall] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        """Check if all tool calls succeeded.

        Returns:
            True if all individual tool calls succeeded, False if any failed.
        """
        return all(call.succeeded for call in self.calls)

    @property
    def failed_calls(self) -> List[ToolCall]:
        """Get list of failed tool calls.

        Returns:
            A list of ToolCall objects that failed during execution.
        """
        return [call for call in self.calls if not call.succeeded]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            A dictionary representation including all tool calls,
            overall success status, and count of failed calls.
        """
        return {
            "calls": [call.to_dict() for call in self.calls],
            "succeeded": self.succeeded,
            "failed_count": len(self.failed_calls),
        }


def extract_parameter_info(func: Callable) -> List[ToolParameter]:
    """Extract parameter information from a function using type hints and docstring.

    Analyzes a function's signature and docstring to automatically generate
    ToolParameter objects for each parameter. Type hints are used to determine
    parameter types, and docstring Args sections provide descriptions.

    Args:
        func: The function to analyze for parameter information

    Returns:
        A list of ToolParameter objects representing the function's parameters,
        excluding 'self' if present.

    Example:
        >>> def greet(name: str, age: int = 25):
        ...     '''Greet a person.
        ...     Args:
        ...         name: Person's name
        ...         age: Person's age
        ...     '''
        ...     pass
        >>> params = extract_parameter_info(greet)
        >>> len(params)
        2
    """
    sig = inspect.signature(func)
    parameters = []

    # Parse docstring for parameter descriptions
    doc_params = {}
    if func.__doc__:
        lines = func.__doc__.strip().split("\n")
        in_params = False
        for line in lines:
            line = line.strip()
            if line.lower().startswith("args:") or line.lower().startswith("parameters:"):
                in_params = True
                continue
            if in_params and line.startswith("returns:"):
                break
            if in_params and ":" in line:
                parts = line.split(":", 1)
                param_name = parts[0].strip()
                param_desc = parts[1].strip()
                doc_params[param_name] = param_desc

    for param_name, param in sig.parameters.items():
        # Skip self parameter
        if param_name == "self":
            continue

        # Determine type
        param_type = ToolParameterType.STRING  # default
        if param.annotation != inspect.Parameter.empty:
            if param.annotation is int:
                param_type = ToolParameterType.INTEGER
            elif param.annotation is float:
                param_type = ToolParameterType.NUMBER
            elif param.annotation is bool:
                param_type = ToolParameterType.BOOLEAN
            elif hasattr(param.annotation, "__origin__"):
                if param.annotation.__origin__ is list:
                    param_type = ToolParameterType.ARRAY
                elif param.annotation.__origin__ is dict:
                    param_type = ToolParameterType.OBJECT

        # Determine if required
        required = param.default == inspect.Parameter.empty

        # Get description
        description = doc_params.get(param_name, f"Parameter {param_name}")

        parameters.append(
            ToolParameter(
                name=param_name,
                type=param_type,
                description=description,
                required=required,
                default=(param.default if param.default != inspect.Parameter.empty else None),
            )
        )

    return parameters


def create_tool_definition(
    func: Callable,
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "general",
) -> ToolDefinition:
    """Create a ToolDefinition from a function.

    Automatically generates a complete tool definition by introspecting
    the function's signature, type hints, and docstring. This is the
    primary way to convert regular Python functions into AI-callable tools.

    Args:
        func: The function to convert into a tool
        name: Override name for the tool (defaults to function name)
        description: Override description (defaults to first line of docstring)
        category: Category for organizing tools (default: "general")

    Returns:
        A complete ToolDefinition ready for use with AI function calling

    Example:
        >>> def add_numbers(a: int, b: int) -> int:
        ...     '''Add two numbers together.'''
        ...     return a + b
        >>> tool = create_tool_definition(add_numbers)
        >>> tool.name
        'add_numbers'
    """
    tool_name = name or func.__name__
    tool_description = description or func.__doc__ or f"Tool: {tool_name}"

    # Extract first line of docstring as description if no description provided
    if not description and func.__doc__:
        tool_description = func.__doc__.strip().split("\n")[0]

    parameters = extract_parameter_info(func)

    return ToolDefinition(
        name=tool_name,
        description=tool_description,
        parameters=parameters,
        function=func,
        category=category,
    )
