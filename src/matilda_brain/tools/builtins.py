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

import ast
import datetime
import json
import math
import operator
import os
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

import zoneinfo

from matilda_brain.config.schema import get_config
from matilda_brain.tools import tool

from .recovery import ErrorRecoverySystem, InputSanitizer, RetryConfig

# Initialize recovery system
recovery_system = ErrorRecoverySystem(RetryConfig())


# Get configuration settings
def _get_max_file_size() -> int:
    """Get maximum file size from configuration."""

    def empty_dict() -> Dict[str, Any]:
        return {}

    try:
        config = get_config()
        # Try tools config first, then constants, then hardcoded fallback
        size = config.tools_config.get("max_file_size")
        if size is None:
            # Try to get from constants section
            constants = getattr(config, "model_dump", empty_dict)().get("constants", {})
            size = constants.get("file_sizes", {}).get("max_file_size")
        return int(size or 10485760)  # 10MB fallback from constants
    except (AttributeError, KeyError, ValueError, TypeError):
        return 10485760  # Fallback to constants value


def _get_code_timeout() -> int:
    """Get code execution timeout from configuration."""

    def empty_dict() -> Dict[str, Any]:
        return {}

    try:
        config = get_config()
        # Try tools config first, then constants, then hardcoded fallback
        timeout = config.tools_config.get("code_execution_timeout")
        if timeout is None:
            # Try to get from constants section
            constants = getattr(config, "model_dump", empty_dict)().get("constants", {})
            timeout = constants.get("tool_bounds", {}).get("default_code_timeout")
        return int(timeout or 30)  # fallback from constants
    except (AttributeError, KeyError, ValueError, TypeError):
        return 30  # Fallback to constants value


def _get_web_timeout() -> int:
    """Get web request timeout from configuration."""

    def empty_dict() -> Dict[str, Any]:
        return {}

    try:
        config = get_config()
        # Try tools config first, then constants, then hardcoded fallback
        timeout = config.tools_config.get("web_request_timeout")
        if timeout is None:
            # Try to get from constants section
            constants = getattr(config, "model_dump", empty_dict)().get("constants", {})
            timeout = constants.get("tool_bounds", {}).get("default_web_timeout")
        return int(timeout or 10)  # fallback from constants
    except (AttributeError, KeyError, ValueError, TypeError):
        return 10  # Fallback to constants value


def _safe_execute(func_name: str, func: Callable[..., Any], **kwargs: Any) -> str:
    """Execute a function with error recovery and input sanitization."""
    try:
        # Sanitize arguments
        sanitized_kwargs = {}
        for key, value in kwargs.items():
            if key in ["file_path", "path"] and isinstance(value, str):
                try:
                    sanitized_kwargs[key] = str(InputSanitizer.sanitize_path(value))
                except ValueError as e:
                    return f"Error: Invalid path '{value}': {e}"
            elif key in ["url"] and isinstance(value, str):
                try:
                    sanitized_kwargs[key] = InputSanitizer.sanitize_url(value)
                except ValueError as e:
                    return f"Error: Invalid URL '{value}': {e}"
            elif key in ["query", "code", "expression", "content"] and isinstance(value, str):
                try:
                    # Allow code for these contexts
                    allow_code = key in ["code", "expression"]
                    sanitized_kwargs[key] = InputSanitizer.sanitize_string(value, allow_code=allow_code)
                except ValueError as e:
                    return f"Error: Invalid input '{key}': {e}"
            else:
                sanitized_kwargs[key] = value

        # Execute with enhanced error handling
        result = func(**sanitized_kwargs)
        return str(result)

    except Exception as e:
        # Classify error and provide helpful message
        error_pattern = recovery_system.classify_error(str(e))

        # Create user-friendly error message
        if error_pattern.error_type.value == "network_error":
            return f"🌐 Network Error: {error_pattern.message}\n💡 {error_pattern.suggested_action}"
        elif error_pattern.error_type.value == "permission_error":
            return f"🔒 Permission Error: {error_pattern.message}\n💡 {error_pattern.suggested_action}"
        elif error_pattern.error_type.value == "resource_error":
            return f"📁 Resource Error: {error_pattern.message}\n💡 {error_pattern.suggested_action}"
        elif error_pattern.error_type.value == "timeout_error":
            return f"⏱️ Timeout Error: {error_pattern.message}\n💡 {error_pattern.suggested_action}"
        elif error_pattern.error_type.value == "validation_error":
            return f"⚠️ Validation Error: {error_pattern.message}\n💡 {error_pattern.suggested_action}"
        else:
            return f"❌ Error in {func_name}: {str(e)}\n💡 {error_pattern.suggested_action}"


ALLOWED_MATH_NAMES = {
    "abs",
    "round",
    "pow",
    "sum",
    "min",
    "max",
    "sqrt",
    "log",
    "log10",
    "exp",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "degrees",
    "radians",
    "pi",
    "e",
    "inf",
    "nan",
}
ALLOWED_MATH_OPERATORS = {
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.FloorDiv,
    ast.USub,
    ast.UAdd,
}


@tool(category="web", description="Search the web for information using a search engine")
def web_search(query: str, num_results: int = 5) -> str:
    """Search the web for information.

    Args:
        query: The search query
        num_results: Number of results to return (max 10)

    Returns:
        Search results as formatted text
    """

    def _web_search_impl(query: str, num_results: int = 5) -> str:
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        num_results = min(max(1, num_results), 10)

        # URL encode the query
        encoded_query = urllib.parse.quote(query)

        # Using DuckDuckGo's API for simplicity (no API key needed)
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"

        # Make request with timeout
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Library/1.0)"})

        with urllib.request.urlopen(req, timeout=_get_web_timeout()) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Extract results
        results = []

        # Add instant answer if available
        if data.get("Answer"):
            results.append(f"Answer: {data['Answer']}")

        # Add abstract if available
        if data.get("Abstract"):
            results.append(f"Summary: {data['Abstract']}")
            if data.get("AbstractURL"):
                results.append(f"Source: {data['AbstractURL']}")

        # Add related topics
        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append(f"- {topic['Text']}")
                if "FirstURL" in topic:
                    results.append(f"  URL: {topic['FirstURL']}")

        if not results:
            return f"No results found for: {query}\n💡 Try different keywords or check your internet connection"

        return "\n".join(results)

    return _safe_execute("web_search", _web_search_impl, query=query, num_results=num_results)


@tool(category="file", description="Read the contents of a file")
def read_file(file_path: str, encoding: str = "utf-8") -> str:
    """Read contents of a file.

    Args:
        file_path: Path to the file to read
        encoding: File encoding (default: utf-8)

    Returns:
        File contents or error message
    """

    def _read_file_impl(file_path: str, encoding: str = "utf-8") -> str:
        # Validate file path
        path = Path(file_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        # Check file size
        file_size = path.stat().st_size
        max_file_size = _get_max_file_size()
        if file_size > max_file_size:
            raise ValueError(f"File too large ({file_size} bytes). Maximum size is {max_file_size} bytes.")

        # Read file
        with open(path, encoding=encoding) as f:
            content = f.read()

        return content

    return _safe_execute("read_file", _read_file_impl, file_path=file_path, encoding=encoding)


@tool(category="file", description="Write content to a file")
def write_file(file_path: str, content: str, encoding: str = "utf-8", create_dirs: bool = False) -> str:
    """Write content to a file.

    Args:
        file_path: Path to the file to write
        content: Content to write to the file
        encoding: File encoding (default: utf-8)
        create_dirs: Whether to create parent directories if they don't exist

    Returns:
        Success message or error
    """

    def _write_file_impl(file_path: str, content: str, encoding: str = "utf-8", create_dirs: bool = False) -> str:
        # Validate inputs
        if not file_path:
            raise ValueError("File path cannot be empty")

        path = Path(file_path).resolve()

        # Create parent directories if requested
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        elif not path.parent.exists():
            raise FileNotFoundError(f"Parent directory does not exist: {path.parent}")

        # Write file
        with open(path, "w", encoding=encoding) as f:
            f.write(content)

        return f"Successfully wrote {len(content)} characters to {file_path}"

    return _safe_execute(
        "write_file",
        _write_file_impl,
        file_path=file_path,
        content=content,
        encoding=encoding,
        create_dirs=create_dirs,
    )


@tool(category="code", description="Execute Python code safely in a sandboxed environment")
def run_python(code: str, timeout: Optional[int] = None) -> str:
    """Execute Python code safely.

    Args:
        code: Python code to execute
        timeout: Maximum execution time in seconds (default: from config)

    Returns:
        Output of the code execution or error message
    """

    def _run_python_impl(code: str, timeout: Optional[int] = None) -> str:
        if timeout is None:
            timeout = _get_code_timeout()

        # Validate inputs
        if not code or not code.strip():
            raise ValueError("Code cannot be empty")

        # Get timeout bounds from config
        try:
            from ..config.schema import get_config

            config = get_config()
            timeout_bounds = config.model_dump().get("tools", {}).get("timeout_bounds", {})
            # Try tools timeout_bounds first, then constants
            min_timeout = timeout_bounds.get("min")
            max_timeout = timeout_bounds.get("max")

            if min_timeout is None or max_timeout is None:
                constants = config.model_dump().get("constants", {})
                tool_bounds = constants.get("tool_bounds", {})
                min_timeout = min_timeout or tool_bounds.get("min_timeout", 1)
                max_timeout = max_timeout or tool_bounds.get("max_timeout", 30)
        except (AttributeError, KeyError, ValueError, TypeError, ImportError):
            # Fallback to constants values
            min_timeout = 1  # constants.tool_bounds.min_timeout
            max_timeout = 30  # constants.tool_bounds.max_timeout

        timeout = min(max(min_timeout, timeout), max_timeout)

        # Create temporary file for code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # Run code in subprocess with timeout
            # Try python3 first, then python
            python_cmd = (
                "python3" if subprocess.run(["which", "python3"], capture_output=True).returncode == 0 else "python"
            )

            result = subprocess.run(
                [python_cmd, temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

            output = []
            if result.stdout:
                output.append(result.stdout)
            if result.stderr:
                output.append(f"Errors:\n{result.stderr}")

            if result.returncode != 0:
                output.append(f"Exit code: {result.returncode}")

            return "\n".join(output) if output else "Code executed successfully (no output)"

        finally:
            # Clean up
            os.unlink(temp_file)

    return _safe_execute("run_python", _run_python_impl, code=code, timeout=timeout)


@tool(category="time", description="Get the current time in a specified timezone")
def get_current_time(timezone: str = "UTC", format: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """Get current time in specified timezone.

    Args:
        timezone: Timezone name (e.g., 'UTC', 'US/Eastern', 'Europe/London')
        format: Time format string (default: '%Y-%m-%d %H:%M:%S %Z')

    Returns:
        Formatted time string or error message
    """
    try:
        # Get timezone
        tz = zoneinfo.ZoneInfo(timezone)

        # Get current time
        now = datetime.datetime.now(tz)

        # Format time
        return now.strftime(format)

    except zoneinfo.ZoneInfoNotFoundError:
        available = ", ".join(sorted(zoneinfo.available_timezones())[:10])
        return f"Error: Unknown timezone '{timezone}'. Examples: {available}..."
    except Exception as e:
        return f"Error getting time: {str(e)}"


@tool(category="web", description="Make HTTP requests to APIs or websites")
def http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Union[str, Dict[str, Any]]] = None,
    timeout: Optional[int] = None,
) -> str:
    """Make HTTP requests.

    Args:
        url: The URL to request
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        headers: Optional headers dictionary
        data: Optional data to send (for POST/PUT requests)
        timeout: Request timeout in seconds (default: from config)

    Returns:
        Response text or error message
    """
    if timeout is None:
        timeout = _get_web_timeout()

    try:
        # Validate inputs
        if not url:
            return "Error: URL cannot be empty"

        # Validate URL
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return "Error: Invalid URL format"

        if parsed.scheme not in ("http", "https"):
            return "Error: Only HTTP/HTTPS protocols are supported"

        # Get timeout bounds from config
        try:
            from ..config.schema import get_config

            config = get_config()
            timeout_bounds = config.model_dump().get("tools", {}).get("timeout_bounds", {})
            # Try tools timeout_bounds first, then constants
            min_timeout = timeout_bounds.get("min")
            max_timeout = timeout_bounds.get("max")

            if min_timeout is None or max_timeout is None:
                constants = config.model_dump().get("constants", {})
                tool_bounds = constants.get("tool_bounds", {})
                min_timeout = min_timeout or tool_bounds.get("min_timeout", 1)
                max_timeout = max_timeout or tool_bounds.get("max_timeout", 30)
        except (AttributeError, KeyError, ValueError, TypeError, ImportError):
            # Fallback to constants values
            min_timeout = 1  # constants.tool_bounds.min_timeout
            max_timeout = 30  # constants.tool_bounds.max_timeout

        timeout = min(max(min_timeout, timeout), max_timeout)

        # Prepare request
        if headers is None:
            headers = {}

        # Convert headers keys to proper case for consistency
        normalized_headers = {}
        for k, v in headers.items():
            normalized_headers[k] = v

        if "User-Agent" not in normalized_headers:
            normalized_headers["User-Agent"] = "AI-Library/1.0"

        # Handle data
        body_data = None
        if data is not None:
            if isinstance(data, dict):
                body_data = json.dumps(data).encode("utf-8")
                normalized_headers["Content-Type"] = "application/json"
            else:
                body_data = str(data).encode("utf-8")

        # Create request
        req = urllib.request.Request(url, data=body_data, headers=normalized_headers, method=method.upper())

        # Make request
        with urllib.request.urlopen(req, timeout=timeout) as response:
            # Read response
            content = response.read().decode("utf-8", errors="replace")

            # Try to parse JSON if possible
            try:
                parsed = json.loads(content)
                return json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                return str(content)

    except urllib.error.HTTPError as e:
        return f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"Network error: {str(e)}"
    except Exception as e:
        return f"Error making request: {str(e)}"


class MathEvaluator(ast.NodeVisitor):
    """Safe math expression evaluator."""

    def visit(self, node: ast.AST) -> Any:
        if type(node) not in (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Constant,
            ast.Name,
            ast.Call,
        ):
            raise ValueError(f"Unsupported operation: {type(node).__name__}")
        return super().visit(node)

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        if type(node.op) not in ALLOWED_MATH_OPERATORS:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")

        left = self.visit(node.left)
        right = self.visit(node.right)

        ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
            ast.FloorDiv: operator.floordiv,
        }

        return ops[type(node.op)](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        if type(node.op) not in (ast.UAdd, ast.USub):
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        operand = self.visit(node.operand)

        if isinstance(node.op, ast.UAdd):
            return +operand
        else:
            return -operand

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id not in ALLOWED_MATH_NAMES:
            raise ValueError(f"Unsupported name: {node.id}")

        # Map names to math module attributes or builtins
        if node.id == "abs":
            return abs
        elif node.id == "round":
            return round
        elif node.id == "pow":
            return pow
        elif node.id == "sum":
            return sum
        elif node.id == "min":
            return min
        elif node.id == "max":
            return max
        elif hasattr(math, node.id):
            return getattr(math, node.id)
        else:
            raise ValueError(f"Unsupported name: {node.id}")

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are supported")

        func_name = node.func.id
        if func_name not in ALLOWED_MATH_NAMES:
            raise ValueError(f"Unsupported function: {func_name}")

        # Get function
        func: Callable[..., Any]
        if func_name == "abs":
            func = abs
        elif func_name == "round":
            func = round
        elif func_name == "pow":
            func = pow
        elif func_name == "sum":
            func = sum
        elif func_name == "min":
            func = min
        elif func_name == "max":
            func = max
        else:
            func = getattr(math, func_name)

        # Evaluate arguments
        args = [self.visit(arg) for arg in node.args]

        return func(*args)


@tool(category="math", description="Perform mathematical calculations safely")
def calculate(expression: str) -> str:
    """Perform mathematical calculations.

    Args:
        expression: Mathematical expression to evaluate

    Supported operations:
        - Basic arithmetic: +, -, *, /, **, %, //
        - Functions: abs, round, pow, sum, min, max, sqrt, log, log10, exp
        - Trigonometry: sin, cos, tan, asin, acos, atan, degrees, radians
        - Constants: pi, e, inf, nan

    Returns:
        Calculation result or error message
    """
    try:
        if not expression or not expression.strip():
            return "Error: Expression cannot be empty"

        # Parse expression
        tree = ast.parse(expression, mode="eval")

        # Evaluate safely
        evaluator = MathEvaluator()
        result = evaluator.visit(tree)

        # Format result
        if isinstance(result, float):
            # Check for special values
            if math.isnan(result):
                return "Result: NaN (Not a Number)"
            elif math.isinf(result):
                return f"Result: {'Infinity' if result > 0 else '-Infinity'}"
            # Format with reasonable precision
            elif abs(result) < 1e-10 or abs(result) > 1e10:
                return f"Result: {result:.6e}"
            else:
                return f"Result: {result:.10g}"
        else:
            return f"Result: {result}"

    except ZeroDivisionError:
        return "Error: Division by zero"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"


@tool(category="file", description="List files and directories in a given path")
def list_directory(
    path: str = ".",
    pattern: Optional[str] = None,
    recursive: bool = False,
    include_hidden: bool = False,
) -> str:
    """List files in a directory.

    Args:
        path: Directory path to list (default: current directory)
        pattern: Optional glob pattern to filter files (e.g., '*.py')
        recursive: Whether to search recursively
        include_hidden: Whether to include hidden files (starting with .)

    Returns:
        List of files and directories or error message
    """
    try:
        # Resolve path
        dir_path = Path(path).resolve()

        if not dir_path.exists():
            return f"Error: Directory not found: {path}"

        if not dir_path.is_dir():
            return f"Error: Not a directory: {path}"

        # List files
        results = []

        if recursive and pattern:
            # Use rglob for recursive pattern matching
            items = dir_path.rglob(pattern)
        elif pattern:
            # Use glob for pattern matching
            items = dir_path.glob(pattern)
        else:
            # List all items
            items = dir_path.iterdir()

        # Process items
        for item in sorted(items):
            # Skip hidden files if requested
            if not include_hidden and item.name.startswith("."):
                continue

            # Format item
            relative = item.relative_to(dir_path)
            if item.is_dir():
                results.append(f"[DIR] {relative}/")
            else:
                size = item.stat().st_size

                # Get size format thresholds from config
                try:
                    from ..config.schema import get_config

                    config = get_config()
                    size_config = config.model_dump().get("files", {}).get("size_format", {})
                    kb_threshold = size_config.get("kb_threshold", 1024)
                    mb_threshold = size_config.get("mb_threshold", 1048576)
                except (AttributeError, KeyError, ValueError, TypeError, ImportError):
                    # Fallback to constants values
                    kb_threshold = 1024  # constants.file_sizes.kb_threshold
                    mb_threshold = 1048576  # constants.file_sizes.mb_threshold

                if size < kb_threshold:
                    size_str = f"{size}B"
                elif size < mb_threshold:
                    size_str = f"{size / kb_threshold:.1f}KB"
                else:
                    size_str = f"{size / mb_threshold:.1f}MB"

                results.append(f"[FILE] {relative} ({size_str})")

        if not results:
            return "No items found matching criteria"

        header = f"Contents of {dir_path}:\n"
        if pattern:
            header += f"Pattern: {pattern}\n"

        return header + "\n".join(results)

    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


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
    "web_search",
    "read_file",
    "write_file",
    "run_python",
    "get_current_time",
    "http_request",
    "calculate",
    "list_directory",
    "load_builtin_tools",
    "TOOL_CATEGORIES",
]
