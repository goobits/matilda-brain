"""Global tool registry for managing available tools."""

import threading
from typing import Callable, Dict, List, Optional, Set, Union

from .base import ToolDefinition, create_tool_definition


class ToolRegistry:
    """Thread-safe registry for managing tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._categories: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()

    def register(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "general",
    ) -> ToolDefinition:
        """Register a function as a tool."""
        with self._lock:
            tool_def = create_tool_definition(func, name, description, category)

            if tool_def.name in self._tools:
                raise ValueError(f"Tool '{tool_def.name}' is already registered")

            self._tools[tool_def.name] = tool_def

            # Update categories
            if category not in self._categories:
                self._categories[category] = set()
            self._categories[category].add(tool_def.name)

            return tool_def

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        with self._lock:
            if name not in self._tools:
                return False

            tool_def = self._tools[name]
            del self._tools[name]

            # Remove from category
            if tool_def.category in self._categories:
                self._categories[tool_def.category].discard(name)
                if not self._categories[tool_def.category]:
                    del self._categories[tool_def.category]

            return True

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        with self._lock:
            return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[ToolDefinition]:
        """List all tools, optionally filtered by category."""
        with self._lock:
            if category is None:
                return list(self._tools.values())
            else:
                if category not in self._categories:
                    return []
                return [self._tools[name] for name in self._categories[category]]

    def get_categories(self) -> List[str]:
        """Get all available categories."""
        with self._lock:
            return list(self._categories.keys())

    def resolve_tools(self, tools: Union[List[str], List[Callable], List[ToolDefinition]]) -> List[ToolDefinition]:
        """Resolve a mixed list of tool references to ToolDefinition objects."""
        resolved = []

        for tool in tools:
            if isinstance(tool, str):
                # Tool name
                tool_def = self.get(tool)
                if tool_def is None:
                    raise ValueError(f"Tool '{tool}' not found in registry")
                resolved.append(tool_def)
            elif isinstance(tool, ToolDefinition):
                # Already a ToolDefinition
                resolved.append(tool)
            elif callable(tool):
                # Function - create temporary tool definition
                temp_tool = create_tool_definition(tool)
                resolved.append(temp_tool)
            else:
                raise ValueError(f"Invalid tool reference: {tool}")

        return resolved

    def clear(self) -> None:
        """Clear all registered tools."""
        with self._lock:
            self._tools.clear()
            self._categories.clear()

    def __len__(self) -> int:
        """Get number of registered tools."""
        with self._lock:
            return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        with self._lock:
            return name in self._tools


# Global registry instance
_global_registry = ToolRegistry()
_builtin_tools_loaded = False


def _ensure_builtin_tools_loaded() -> None:
    global _builtin_tools_loaded
    if _builtin_tools_loaded:
        return
    from .builtins import load_builtin_tools

    load_builtin_tools()
    _builtin_tools_loaded = True


def register_tool(
    func: Callable,
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "general",
) -> ToolDefinition:
    """Register a tool in the global registry."""
    return _global_registry.register(func, name, description, category)


def unregister_tool(name: str) -> bool:
    """Unregister a tool from the global registry."""
    return _global_registry.unregister(name)


def get_tool(name: str) -> Optional[ToolDefinition]:
    """Get a tool from the global registry."""
    tool = _global_registry.get(name)
    if tool is None:
        _ensure_builtin_tools_loaded()
        tool = _global_registry.get(name)
    return tool


def list_tools(category: Optional[str] = None) -> List[ToolDefinition]:
    """List tools from the global registry."""
    _ensure_builtin_tools_loaded()
    return _global_registry.list_tools(category)


def get_categories() -> List[str]:
    """Get all categories from the global registry."""
    _ensure_builtin_tools_loaded()
    return _global_registry.get_categories()


def resolve_tools(
    tools: Union[List[str], List[Callable], List[ToolDefinition]],
) -> List[ToolDefinition]:
    """Resolve tool references using the global registry."""
    try:
        return _global_registry.resolve_tools(tools)
    except ValueError:
        _ensure_builtin_tools_loaded()
        return _global_registry.resolve_tools(tools)


def clear_registry() -> None:
    """Clear the global registry."""
    global _builtin_tools_loaded
    _global_registry.clear()
    _builtin_tools_loaded = False


def get_registry() -> ToolRegistry:
    """Get the global registry instance for advanced usage."""
    return _global_registry
