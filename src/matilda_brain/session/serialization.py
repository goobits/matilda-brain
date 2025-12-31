"""Serialization utilities for chat sessions.

This module provides functions for serializing and deserializing
chat session data, tools, and messages.
"""

import json
from typing import Any, Dict, List, Union

from ..core.models import ImageInput


def estimate_tokens(content: Union[str, List]) -> int:
    """Estimate token count for content.

    Args:
        content: Text string or list of content items

    Returns:
        Estimated token count
    """
    if isinstance(content, str):
        # Rough estimate: ~1 token per 4 characters
        return max(len(content) // 4, 0)
    elif isinstance(content, list):
        tokens = 0
        for item in content:
            if isinstance(item, str):
                tokens += len(item) // 4
            elif isinstance(item, ImageInput):
                # Images typically use more tokens
                tokens += 85  # Base64 encoded images use significant tokens
        return tokens
    return 0


def serialize_tools(tools: List) -> List[Dict[str, Any]]:
    """Serialize tools for storage.

    Args:
        tools: List of tool objects (functions, callables, or tool definitions)

    Returns:
        List of serialized tool dictionaries
    """
    if not tools:
        return []

    serialized = []
    for tool in tools:
        if hasattr(tool, "__name__"):
            # Function or callable
            serialized.append(
                {
                    "type": "function_name",
                    "name": tool.__name__,
                    "module": (tool.__module__ if hasattr(tool, "__module__") else None),
                }
            )
        elif hasattr(tool, "name"):
            # ToolDefinition-like object
            serialized.append(
                {
                    "type": "tool_definition",
                    "name": tool.name,
                    "description": getattr(tool, "description", None),
                }
            )
        else:
            # String tool name
            serialized.append({"type": "tool_name", "name": str(tool)})

    return serialized


def deserialize_tools(serialized_tools: List[Dict[str, Any]]) -> List:
    """Deserialize tools from storage.

    Args:
        serialized_tools: List of serialized tool dictionaries

    Returns:
        List of tool names (actual function resolution would need a registry)
    """
    if not serialized_tools:
        return []

    # For now, return tool names as strings
    # In a real implementation, we'd resolve these from a registry
    # or import the actual functions
    tools = []
    for tool_data in serialized_tools:
        if tool_data["type"] == "tool_name":
            tools.append(tool_data["name"])
        elif tool_data["type"] == "function_name":
            # Could attempt to import the function here
            tools.append(tool_data["name"])
        elif tool_data["type"] == "tool_definition":
            # Return as a dict for now
            tools.append(tool_data["name"])

    return tools


def export_messages_text(history: List[Dict[str, Any]]) -> str:
    """Export messages as plain text.

    Args:
        history: List of message dictionaries

    Returns:
        Formatted text string
    """
    lines = []
    for msg in history:
        role = msg["role"].capitalize()
        content = msg["content"]
        if isinstance(content, list):
            # Handle multi-modal content
            text_parts = [item for item in content if isinstance(item, str)]
            content = " ".join(text_parts)
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def export_messages_markdown(
    history: List[Dict[str, Any]],
    session_id: str = "Unknown",
    system: str = None
) -> str:
    """Export messages as markdown.

    Args:
        history: List of message dictionaries
        session_id: Session identifier for the header
        system: Optional system prompt

    Returns:
        Formatted markdown string
    """
    lines = []
    # Add header
    lines.append(f"# Chat Session: {session_id}")
    lines.append("")

    # Add system prompt if present
    if system:
        lines.append(f"**System:** {system}")
        lines.append("")

    # Add messages
    for msg in history:
        role = msg["role"].capitalize()
        content = msg["content"]
        if isinstance(content, list):
            # Handle multi-modal content
            text_parts = [item for item in content if isinstance(item, str)]
            content = " ".join(text_parts)

        lines.append(f"### {role}")
        lines.append(content)
        lines.append("")

    return "\n".join(lines).strip()


def export_messages_json(
    history: List[Dict[str, Any]],
    session_id: str = None,
    created_at: str = None,
    system: str = None
) -> str:
    """Export messages as JSON.

    Args:
        history: List of message dictionaries
        session_id: Optional session identifier
        created_at: Optional creation timestamp
        system: Optional system prompt

    Returns:
        JSON string
    """
    export_data = {
        "session_id": session_id,
        "created_at": created_at,
        "system": system,
        "messages": history,
    }
    return json.dumps(export_data, indent=2, default=str)


__all__ = [
    "estimate_tokens",
    "serialize_tools",
    "deserialize_tools",
    "export_messages_text",
    "export_messages_markdown",
    "export_messages_json",
]
