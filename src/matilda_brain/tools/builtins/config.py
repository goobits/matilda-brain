"""Configuration utilities for built-in tools.

This module provides configuration getters and safe execution utilities
used across all built-in tools.
"""

from typing import Any, Callable, Dict, Optional, Tuple

from matilda_brain.config.schema import get_config

from ..recovery import ErrorRecoverySystem, InputSanitizer, RetryConfig

# Initialize recovery system
recovery_system = ErrorRecoverySystem(RetryConfig())


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


def _get_timeout_bounds() -> tuple:
    """Get min/max timeout bounds from configuration."""
    try:
        config = get_config()
        timeout_bounds = config.model_dump().get("tools", {}).get("timeout_bounds", {})
        min_timeout = timeout_bounds.get("min")
        max_timeout = timeout_bounds.get("max")

        if min_timeout is None or max_timeout is None:
            constants = config.model_dump().get("constants", {})
            tool_bounds = constants.get("tool_bounds", {})
            min_timeout = min_timeout or tool_bounds.get("min_timeout", 1)
            max_timeout = max_timeout or tool_bounds.get("max_timeout", 30)
        return (min_timeout, max_timeout)
    except (AttributeError, KeyError, ValueError, TypeError, ImportError):
        return (1, 30)  # Fallback to constants values


def _sanitize_kwargs(kwargs: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """Sanitize keyword arguments."""
    sanitized_kwargs = {}
    for key, value in kwargs.items():
        if key in ["file_path", "path"] and isinstance(value, str):
            try:
                sanitized_kwargs[key] = str(InputSanitizer.sanitize_path(value))
            except ValueError as e:
                return {}, f"Error: Invalid path '{value}': {e}"
        elif key in ["url"] and isinstance(value, str):
            try:
                sanitized_kwargs[key] = InputSanitizer.sanitize_url(value)
            except ValueError as e:
                return {}, f"Error: Invalid URL '{value}': {e}"
        elif key in ["query", "code", "expression", "content"] and isinstance(value, str):
            try:
                # Allow code for these contexts
                allow_code = key in ["code", "expression"]
                sanitized_kwargs[key] = InputSanitizer.sanitize_string(value, allow_code=allow_code)
            except ValueError as e:
                return {}, f"Error: Invalid input '{key}': {e}"
        else:
            sanitized_kwargs[key] = value
    return sanitized_kwargs, None


def _handle_error(func_name: str, e: Exception) -> str:
    """Handle exceptions with error recovery system."""
    # Classify error and provide helpful message
    error_pattern = recovery_system.classify_error(str(e))

    # Create user-friendly error message
    if error_pattern.error_type.value == "network_error":
        return f"Network Error: {error_pattern.message}\n{error_pattern.suggested_action}"
    elif error_pattern.error_type.value == "permission_error":
        return f"Permission Error: {error_pattern.message}\n{error_pattern.suggested_action}"
    elif error_pattern.error_type.value == "resource_error":
        return f"Resource Error: {error_pattern.message}\n{error_pattern.suggested_action}"
    elif error_pattern.error_type.value == "timeout_error":
        return f"Timeout Error: {error_pattern.message}\n{error_pattern.suggested_action}"
    elif error_pattern.error_type.value == "validation_error":
        return f"Validation Error: {error_pattern.message}\n{error_pattern.suggested_action}"
    else:
        return f"Error in {func_name}: {str(e)}\n{error_pattern.suggested_action}"


def _safe_execute(func_name: str, func: Callable[..., Any], **kwargs: Any) -> str:
    """Execute a function with error recovery and input sanitization."""
    try:
        sanitized_kwargs, error = _sanitize_kwargs(kwargs)
        if error:
            return error

        # Execute with enhanced error handling
        result = func(**sanitized_kwargs)
        return str(result)

    except Exception as e:
        return _handle_error(func_name, e)


async def _safe_execute_async(func_name: str, func: Callable[..., Any], **kwargs: Any) -> str:
    """Execute an async function with error recovery and input sanitization."""
    try:
        sanitized_kwargs, error = _sanitize_kwargs(kwargs)
        if error:
            return error

        # Execute with enhanced error handling
        result = await func(**sanitized_kwargs)
        return str(result)

    except Exception as e:
        return _handle_error(func_name, e)


__all__ = [
    "_get_max_file_size",
    "_get_code_timeout",
    "_get_web_timeout",
    "_get_timeout_bounds",
    "_safe_execute",
    "_safe_execute_async",
    "recovery_system",
]
