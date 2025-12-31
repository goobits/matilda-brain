"""Built-in tools for the AI library.

This module provides a comprehensive set of built-in tools that users can
immediately use without additional setup. All tools include proper error
handling, input validation, and security measures.

Usage:
    from matilda_brain.tools.builtins import load_builtin_tools

    # Load all built-in tools into the registry
    load_builtin_tools()

    # Or import specific tools
    from matilda_brain.tools.builtins import web_search, read_file
"""

# Import all tools from submodules
from .code import (
    ALLOWED_MATH_NAMES,
    ALLOWED_MATH_OPERATORS,
    MathEvaluator,
    calculate,
    run_python,
)
from .filesystem import list_directory, read_file, write_file
from .system import get_current_time
from .web import http_request, web_search


def load_builtin_tools() -> None:
    """Load all built-in tools into the global registry.

    This function is automatically called when the module is imported,
    but can be called manually to reload tools.
    """
    # The tools are already registered via the @tool decorator
    # This function is here for explicit loading if needed
    pass


# Tool categories mapping for easy discovery
TOOL_CATEGORIES = {
    "web": ["web_search", "http_request"],
    "file": ["read_file", "write_file", "list_directory"],
    "code": ["run_python"],
    "time": ["get_current_time"],
    "math": ["calculate"],
}

# Auto-load built-in tools when module is imported
load_builtin_tools()


__all__ = [
    # Web tools
    "web_search",
    "http_request",
    # Filesystem tools
    "read_file",
    "write_file",
    "list_directory",
    # Code tools
    "run_python",
    "calculate",
    "MathEvaluator",
    "ALLOWED_MATH_NAMES",
    "ALLOWED_MATH_OPERATORS",
    # System tools
    "get_current_time",
    # Utilities
    "load_builtin_tools",
    "TOOL_CATEGORIES",
]
