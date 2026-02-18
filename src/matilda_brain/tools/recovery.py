"""Smart error recovery and fallback system for AI tools."""

import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, cast

import bleach  # type: ignore[import-untyped]
import validators

from .base import ToolCall


class ErrorType(Enum):
    """Types of errors that can occur during tool execution."""

    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    PERMISSION_ERROR = "permission_error"
    VALIDATION_ERROR = "validation_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    TOOL_NOT_FOUND = "tool_not_found"
    INVALID_INPUT = "invalid_input"
    RESOURCE_ERROR = "resource_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ErrorPattern:
    """Pattern matching for error classification."""

    pattern: str
    error_type: ErrorType
    message: str
    suggested_action: str
    can_retry: bool = True
    fallback_tools: List[str] = field(default_factory=list)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: Optional[int] = None
    base_delay: Optional[float] = None
    max_delay: Optional[float] = None
    exponential_base: float = 2.0
    jitter: bool = True

    def __post_init__(self) -> None:
        """Load defaults from config if not set."""
        from ..config.loader import get_config_value

        # Use `or` to handle explicit null in config (which returns None, not the default)
        if self.max_attempts is None:
            self.max_attempts = get_config_value("tools.retry.max_attempts", 3) or 3
        if self.base_delay is None:
            self.base_delay = get_config_value("tools.retry.base_delay", 1.0) or 1.0
        if self.max_delay is None:
            self.max_delay = get_config_value("tools.retry.max_delay", 60.0) or 60.0


@dataclass
class FallbackSuggestion:
    """Suggestion for alternative approaches when a tool fails."""

    tool_name: str
    description: str
    arguments: Dict[str, Any]
    confidence: float


class InputSanitizer:
    """Professional input sanitization using battle-tested libraries."""

    # Only block truly dangerous patterns (much more targeted)
    DANGEROUS_PATTERNS = [
        # Actual command injection (not legitimate code)
        r"^\s*sudo\s+",
        r"\brm\s+-rf\s+/",
        r"\bdel\s+/[sq]",
        r"\bformat\s+[c-z]:",
        # Path traversal
        r"\.\./",
        r"\.\.\\",
        # System file access
        r"/etc/passwd",
        r"/etc/shadow",
        r"C:\\Windows\\System32",
        # Binary/executable content
        r"^\x7fELF",  # ELF header
        r"^MZ",  # DOS header
    ]

    # Patterns that are dangerous specifically in code execution contexts
    CODE_DANGEROUS_PATTERNS = [
        # OS module execution methods
        r"os\.system\s*\(",
        r"os\.popen\s*\(",
        r"os\.execv\s*\(",
        r"os\.execve\s*\(",
        r"os\.execl\s*\(",
        r"os\.execlp\s*\(",
        r"os\.execvp\s*\(",
        r"os\.spawn\w*\s*\(",  # Generic spawn pattern
        # Subprocess module execution methods
        r"subprocess\.(run|call|Popen|check_output|check_call|getoutput|getstatusoutput)\s*\(",
        # Dynamic code execution
        r"eval\s*\(",
        r"exec\s*\(",
        r"compile\s*\(",
        r"__import__\s*\(",
        # String concatenation bypasses for critical functions
        r'getattr\s*\(\s*os\s*,\s*["\']\s*sys\s*["\']\s*\+',
        r'getattr\s*\(\s*os\s*,\s*["\']sys["\']\s*\+',
        r'getattr\s*\(\s*os\s*,\s*["\']\s*system\s*["\']',
        r"getattr\s*\(\s*subprocess\s*,",
        r"getattr\s*\(\s*__import__\s*\(",
        # Import bypasses
        r"from\s+subprocess\s+import\s+(check_output|check_call|getoutput|getstatusoutput|run|call|Popen)",
        r"from\s+os\s+import\s+(system|popen|exec)",
        r"import\s+subprocess\s+as\s+\w+",
        r"import\s+os\s+as\s+\w+",
        # File system access
        r'open\s*\(\s*["\'][/\\]',  # Opening system files
        # Globals and builtins access
        r"globals\s*\(\s*\)\s*\[",
        r"__builtins__\s*\[",
        r"locals\s*\(\s*\)\s*\[",
        # Type and reflection-based bypasses
        r"type\s*\(\s*lambda\s*:",
        r"chr\s*\(\s*\d+\s*\)\s*\+.*chr\s*\(",  # Character concatenation
    ]

    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 10000, allow_code: bool = True) -> str:
        """Sanitize string input using professional bleach library."""
        if not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value)}")

        # Length check
        if len(value) > max_length:
            raise ValueError(f"String too long: {len(value)} > {max_length}")

        # Check for truly dangerous patterns (much more targeted now)
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE | re.MULTILINE):
                raise ValueError("Potentially dangerous content detected")

        if allow_code:
            # For code content, check code-specific dangerous patterns
            for pattern in cls.CODE_DANGEROUS_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE | re.MULTILINE):
                    raise ValueError("Dangerous code pattern detected")

            # Remove null bytes and other control characters
            sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
            return sanitized.strip()
        else:
            # For HTML/text content, use bleach for proper sanitization
            sanitized = bleach.clean(value, strip=True)
            return str(sanitized)

    @classmethod
    def sanitize_path(cls, path: str) -> Path:
        """Sanitize file path input."""
        if not isinstance(path, str):
            raise ValueError(f"Expected string path, got {type(path)}")

        # Basic path validation
        if not path or path.isspace():
            raise ValueError("Path cannot be empty")

        # URL decode the path to prevent encoding bypasses
        import urllib.parse

        decoded_path = urllib.parse.unquote(path)

        # Check for path traversal in both original and decoded paths
        if ".." in path or ".." in decoded_path:
            raise ValueError("Path traversal detected")

        # Use the decoded path for further processing
        path = decoded_path

        # Resolve and validate
        try:
            resolved_path = Path(path).resolve()

            # Check if path is within allowed bounds (current directory or subdirectories)
            # Allow temporary directories for testing
            cwd = Path.cwd().resolve()
            temp_dirs = [Path("/tmp").resolve(), Path("/var/tmp").resolve()]

            # Use is_relative_to() to prevent directory traversal (e.g., /app vs /appdata)
            is_in_cwd = resolved_path.is_relative_to(cwd)
            is_in_temp = any(resolved_path.is_relative_to(temp_dir) for temp_dir in temp_dirs)

            if not (is_in_cwd or is_in_temp):
                raise ValueError(f"Path outside allowed directory: {resolved_path}")

            return resolved_path
        except Exception as e:
            raise ValueError(f"Invalid path: {e}") from e

    @classmethod
    def sanitize_url(cls, url: str) -> str:
        """Sanitize URL input using validators library."""
        if not isinstance(url, str):
            raise ValueError(f"Expected string URL, got {type(url)}")

        # Clean the URL
        url = url.strip()

        # Validate URL format using professional library
        if not validators.url(url):
            raise ValueError(f"Invalid URL format: {url}")

        # Ensure only HTTP/HTTPS schemes
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("Only HTTP and HTTPS URLs are allowed")

        # Check for dangerous patterns in URL
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                raise ValueError("Potentially dangerous URL content detected")

        return url

    @classmethod
    def sanitize_json(cls, json_str: str) -> Dict[str, Any]:
        """Sanitize and parse JSON input safely."""
        if not isinstance(json_str, str):
            raise ValueError(f"Expected JSON string, got {type(json_str)}")

        try:
            # Parse JSON using standard library
            data = json.loads(json_str)

            # Recursively sanitize string values with bleach
            def sanitize_recursive(obj: Any) -> Any:
                if isinstance(obj, dict):
                    return {k: sanitize_recursive(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [sanitize_recursive(item) for item in obj]
                elif isinstance(obj, str):
                    # Use bleach for text content in JSON
                    return cls.sanitize_string(obj, allow_code=False)
                else:
                    return obj

            result = sanitize_recursive(data)
            return cast(Dict[str, Any], result)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e


class ErrorRecoverySystem:
    """Smart error recovery and fallback system."""

    # Pre-defined error patterns for common issues
    ERROR_PATTERNS = [
        ErrorPattern(
            pattern=r"connection.*timeout|timeout.*connection|timed out",
            error_type=ErrorType.TIMEOUT_ERROR,
            message="Connection timed out",
            suggested_action="Check your internet connection and try again",
            can_retry=True,
        ),
        ErrorPattern(
            pattern=r"permission denied|access denied|forbidden",
            error_type=ErrorType.PERMISSION_ERROR,
            message="Permission denied",
            suggested_action="Check file permissions or try with appropriate credentials",
            can_retry=False,
        ),
        ErrorPattern(
            pattern=r"rate limit|too many requests|quota exceeded",
            error_type=ErrorType.RATE_LIMIT_ERROR,
            message="Rate limit exceeded",
            suggested_action="Wait a moment before retrying",
            can_retry=True,
        ),
        ErrorPattern(
            pattern=r"file not found|no such file|path does not exist",
            error_type=ErrorType.RESOURCE_ERROR,
            message="File or resource not found",
            suggested_action="Check the file path and ensure the file exists",
            can_retry=False,
            fallback_tools=["list_directory"],
        ),
        ErrorPattern(
            pattern=r"network.*unreachable|host.*unreachable|connection refused",
            error_type=ErrorType.NETWORK_ERROR,
            message="Network connection failed",
            suggested_action="Check your internet connection and firewall settings",
            can_retry=True,
        ),
        ErrorPattern(
            pattern=r"invalid.*argument|invalid.*parameter|validation.*failed",
            error_type=ErrorType.VALIDATION_ERROR,
            message="Invalid input provided",
            suggested_action="Check your input parameters and try again",
            can_retry=False,
        ),
    ]

    # Tool fallback mappings
    TOOL_FALLBACKS = {
        "web_search": ["http_request"],
        "http_request": ["web_search"],
        "read_file": ["list_directory"],
        "write_file": ["list_directory"],
        "run_python": ["calculate"],
        "calculate": ["run_python"],
    }

    def __init__(self, retry_config: Optional[RetryConfig] = None):
        self.retry_config = retry_config or RetryConfig()
        self.logger = logging.getLogger(__name__)

    def classify_error(self, error_message: str) -> ErrorPattern:
        """Classify an error message to determine recovery strategy."""
        error_message_lower = error_message.lower()

        for pattern in self.ERROR_PATTERNS:
            if re.search(pattern.pattern, error_message_lower, re.IGNORECASE):
                return pattern

        # Default to unknown error
        return ErrorPattern(
            pattern=".*",
            error_type=ErrorType.UNKNOWN_ERROR,
            message="An unexpected error occurred",
            suggested_action="Please try again or contact support if the problem persists",
            can_retry=True,
        )

    def create_recovery_message(self, tool_call: ToolCall, error_pattern: ErrorPattern) -> str:
        """Create a helpful recovery message for the user."""
        base_message = f"❌ **{tool_call.name}** failed: {error_pattern.message}"

        suggestions = []

        # Add suggested action
        if error_pattern.suggested_action:
            suggestions.append(f"💡 **Suggestion**: {error_pattern.suggested_action}")

        # Add retry information
        if error_pattern.can_retry:
            suggestions.append("🔄 **Retry**: This error can be retried automatically")

        # Add fallback tool suggestions
        if error_pattern.fallback_tools:
            fallback_list = ", ".join(error_pattern.fallback_tools)
            suggestions.append(f"🔧 **Alternatives**: Try using {fallback_list}")

        # Add general fallbacks
        general_fallbacks = self.TOOL_FALLBACKS.get(tool_call.name, [])
        if general_fallbacks:
            fallback_list = ", ".join(general_fallbacks)
            suggestions.append(f"🔧 **Similar tools**: {fallback_list}")

        # Combine message and suggestions
        if suggestions:
            return base_message + "\n\n" + "\n".join(suggestions)
        else:
            return base_message

    def get_fallback_suggestions(self, failed_tool: str, original_args: Dict[str, Any]) -> List[FallbackSuggestion]:
        """Get suggested fallback tools for a failed tool."""
        suggestions = []

        # Check predefined fallbacks
        fallback_tools = self.TOOL_FALLBACKS.get(failed_tool, [])

        for tool_name in fallback_tools:
            # Adapt arguments for the fallback tool
            adapted_args = self._adapt_arguments(failed_tool, tool_name, original_args)

            suggestions.append(
                FallbackSuggestion(
                    tool_name=tool_name,
                    description=f"Alternative to {failed_tool}",
                    arguments=adapted_args,
                    confidence=0.7,
                )
            )

        # Add context-specific suggestions
        if failed_tool == "read_file" and "file_path" in original_args:
            # If file read fails, suggest listing the directory
            file_path = Path(original_args["file_path"])
            suggestions.append(
                FallbackSuggestion(
                    tool_name="list_directory",
                    description="Check if file exists in directory",
                    arguments={"path": str(file_path.parent)},
                    confidence=0.9,
                )
            )

        elif failed_tool == "web_search" and "query" in original_args:
            # If web search fails, try direct HTTP request to a search engine
            query = original_args["query"]
            suggestions.append(
                FallbackSuggestion(
                    tool_name="http_request",
                    description="Try direct search engine request",
                    arguments={
                        "url": f"https://api.duckduckgo.com/?q={query}&format=json",
                        "method": "GET",
                    },
                    confidence=0.8,
                )
            )

        return suggestions

    def _adapt_arguments(self, from_tool: str, to_tool: str, original_args: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt arguments from one tool to another."""
        # Basic argument mapping
        arg_mappings = {
            ("web_search", "http_request"): {
                "query": lambda q: {"url": f"https://api.duckduckgo.com/?q={q}&format=json"}
            },
            ("http_request", "web_search"): {
                "url": lambda u: {"query": u.split("q=")[-1].split("&")[0] if "q=" in u else u}
            },
        }

        mapping = arg_mappings.get((from_tool, to_tool), {})
        adapted_args = {}

        for orig_key, orig_value in original_args.items():
            if orig_key in mapping:
                new_key_or_func = mapping[orig_key]
                if callable(new_key_or_func):
                    adapted_args.update(new_key_or_func(orig_value))
                else:
                    adapted_args[new_key_or_func] = orig_value
            else:
                # Keep original argument if no mapping exists
                adapted_args[orig_key] = orig_value

        return adapted_args

    def should_retry(self, error_pattern: ErrorPattern, attempt: int) -> bool:
        """Determine if a failed tool call should be retried."""
        if not error_pattern.can_retry:
            return False

        if self.retry_config.max_attempts is not None and attempt >= self.retry_config.max_attempts:
            return False

        # Special cases
        if error_pattern.error_type == ErrorType.RATE_LIMIT_ERROR:
            # Always retry rate limits with longer delays
            return attempt < 5

        return True

    def calculate_retry_delay(self, attempt: int, error_pattern: ErrorPattern) -> float:
        """Calculate delay before retry attempt."""
        base_delay = self.retry_config.base_delay or 1.0

        # Special handling for rate limits
        if error_pattern.error_type == ErrorType.RATE_LIMIT_ERROR:
            from ..config.loader import get_config_value

            min_rate_limit_delay = get_config_value("tools.retry.rate_limit_min_delay", 5.0)
            base_delay = max(base_delay, min_rate_limit_delay)

        # Exponential backoff
        delay = base_delay * (self.retry_config.exponential_base**attempt)

        # Cap at max delay
        if self.retry_config.max_delay is not None:
            delay = min(delay, self.retry_config.max_delay)

        # Add jitter to avoid thundering herd
        if self.retry_config.jitter:
            jitter = random.uniform(0.1, 0.3) * delay
            delay += jitter

        return delay

    async def execute_with_recovery(
        self,
        tool_function: Callable,
        tool_name: str,
        arguments: Dict[str, Any],
        attempt: int = 1,
    ) -> ToolCall:
        """Execute a tool with automatic recovery and retry logic."""
        call_id = f"{tool_name}_{int(time.time() * 1000)}"

        # Use iterative approach to avoid stack overflow on many retries
        while True:
            try:
                # Sanitize inputs before execution
                sanitized_args = self._sanitize_arguments(tool_name, arguments)

                # Execute the tool
                result = await tool_function(**sanitized_args)

                return ToolCall(id=call_id, name=tool_name, arguments=sanitized_args, result=result)

            except Exception as e:
                error_message = str(e)
                error_pattern = self.classify_error(error_message)

                # Log the error
                self.logger.warning(f"Tool {tool_name} failed (attempt {attempt}): {error_message}")

                # Check if we should retry
                if self.should_retry(error_pattern, attempt):
                    # Calculate delay and retry
                    delay = self.calculate_retry_delay(attempt, error_pattern)
                    self.logger.info(f"Retrying {tool_name} in {delay:.1f} seconds...")

                    await asyncio.sleep(delay)
                    attempt += 1
                    continue  # Retry without recursion
                else:
                    # Create enhanced error message with recovery suggestions
                    recovery_message = self.create_recovery_message(
                        ToolCall(call_id, tool_name, arguments, error=error_message),
                        error_pattern,
                    )

                    return ToolCall(
                        id=call_id,
                        name=tool_name,
                        arguments=arguments,
                        error=recovery_message,
                    )

    def _sanitize_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize tool arguments based on tool type."""
        sanitized = {}

        for key, value in arguments.items():
            try:
                if key in ["file_path", "path"]:
                    # File path sanitization
                    sanitized[key] = str(InputSanitizer.sanitize_path(value))
                elif key in ["url"]:
                    # URL sanitization
                    sanitized[key] = InputSanitizer.sanitize_url(value)
                elif key in ["code", "expression", "query", "content"]:
                    # Text content sanitization
                    sanitized[key] = InputSanitizer.sanitize_string(value)
                elif key in ["data"] and isinstance(value, str):
                    # JSON data sanitization - keep as string but validate
                    try:
                        # Validate JSON but keep as string
                        InputSanitizer.sanitize_json(value)
                        sanitized[key] = value
                    except ValueError:
                        # If not valid JSON, treat as string
                        sanitized[key] = InputSanitizer.sanitize_string(value)
                else:
                    # Basic type validation
                    if isinstance(value, str):
                        sanitized[key] = InputSanitizer.sanitize_string(value)
                    else:
                        sanitized[key] = value

            except ValueError as e:
                raise ValueError(f"Invalid argument '{key}': {e}") from e

        return sanitized


# Global recovery system instance
recovery_system = ErrorRecoverySystem()


def with_recovery(tool_function: Callable) -> Callable:
    """Decorator to add error recovery to a tool function."""

    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        tool_name = getattr(tool_function, "__name__", "unknown_tool")
        return await recovery_system.execute_with_recovery(tool_function, tool_name, kwargs)

    return wrapper
