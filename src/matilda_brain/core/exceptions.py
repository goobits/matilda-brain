"""
Custom exception hierarchy for the AI library.

This module defines specific exceptions for different error scenarios,
making it easier for users to handle errors programmatically.
"""

from typing import Any, Dict, Optional


class AIError(Exception):
    """Base exception for all AI library errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize an AIError.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


# Backend-related exceptions


class BackendError(AIError):
    """Base exception for backend-related errors."""

    pass


class BackendNotAvailableError(BackendError):
    """Raised when a requested backend is not available or misconfigured."""

    def __init__(self, backend_name: str, reason: Optional[str] = None):
        message = f'Backend "{backend_name}" is not available'
        if reason:
            message += f": {reason}"
        super().__init__(message, {"backend": backend_name, "reason": reason})


class BackendConnectionError(BackendError):
    """Raised when connection to a backend fails."""

    def __init__(self, backend_name: str, original_error: Optional[Exception] = None):
        message = f"Failed to connect to backend '{backend_name}'"
        if original_error:
            message += f": {str(original_error)}"
        super().__init__(
            message,
            {
                "backend": backend_name,
                "original_error": str(original_error) if original_error else None,
            },
        )


class BackendTimeoutError(BackendError):
    """Raised when a backend operation times out."""

    def __init__(self, backend_name: str, timeout: float):
        message = f"Backend '{backend_name}' operation timed out after {timeout}s"
        super().__init__(message, {"backend": backend_name, "timeout": timeout})


# Model-related exceptions


class ModelError(AIError):
    """Base exception for model-related errors."""

    pass


class ModelNotFoundError(ModelError):
    """Raised when a requested model is not found."""

    def __init__(self, model_name: str, backend: Optional[str] = None):
        message = f'Model "{model_name}" not found'
        if backend:
            message += f' in backend "{backend}"'
        super().__init__(message, {"model": model_name, "backend": backend})


class ModelNotSupportedError(ModelError):
    """Raised when a model doesn't support requested features."""

    def __init__(self, model_name: str, feature: str, backend: Optional[str] = None):
        message = f"Model '{model_name}' does not support {feature}"
        if backend:
            message += f" on backend '{backend}'"
        super().__init__(message, {"model": model_name, "feature": feature, "backend": backend})


# Configuration-related exceptions


class ConfigurationError(AIError):
    """Base exception for configuration-related errors."""

    pass


class APIKeyError(ConfigurationError):
    """Raised when an API key is missing or invalid."""

    def __init__(self, provider: str, env_var: Optional[str] = None):
        message = f"API key for '{provider}' is missing or invalid"
        if env_var:
            message += f". Please set the {env_var} environment variable"
        super().__init__(message, {"provider": provider, "env_var": env_var})


class ConfigFileError(ConfigurationError):
    """Raised when there's an error with configuration file."""

    def __init__(self, file_path: str, reason: str):
        message = f"Error reading configuration file '{file_path}': {reason}"
        super().__init__(message, {"file_path": file_path, "reason": reason})


# Input validation exceptions


class ValidationError(AIError):
    """Base exception for input validation errors."""

    pass


class InvalidPromptError(ValidationError):
    """Raised when prompt input is invalid."""

    def __init__(self, reason: str):
        message = f"Invalid prompt: {reason}"
        super().__init__(message, {"reason": reason})


class InvalidParameterError(ValidationError):
    """Raised when a parameter value is invalid."""

    def __init__(self, parameter: str, value: Any, reason: str):
        message = f"Invalid value for parameter '{parameter}': {reason}"
        super().__init__(message, {"parameter": parameter, "value": value, "reason": reason})


# Response-related exceptions


class ResponseError(AIError):
    """Base exception for response-related errors."""

    pass


class EmptyResponseError(ResponseError):
    """Raised when the AI returns an empty response."""

    def __init__(self, model: str, backend: str):
        message = f"Received empty response from model '{model}' on backend '{backend}'"
        super().__init__(message, {"model": model, "backend": backend})


class ResponseParsingError(ResponseError):
    """Raised when response parsing fails."""

    def __init__(self, reason: str, raw_response: Optional[str] = None):
        message = f"Failed to parse response: {reason}"
        super().__init__(
            message,
            {
                "reason": reason,
                "raw_response": raw_response[:200] if raw_response else None,
            },
        )


# Feature-related exceptions


class FeatureNotAvailableError(AIError):
    """Raised when a requested feature is not available."""

    def __init__(self, feature: str, reason: Optional[str] = None):
        message = f"Feature '{feature}' is not available"
        if reason:
            message += f": {reason}"
        super().__init__(message, {"feature": feature, "reason": reason})


class MultiModalError(AIError):
    """Raised when there's an error with multi-modal input."""

    def __init__(self, reason: str):
        message = f"Multi-modal error: {reason}"
        super().__init__(message, {"reason": reason})


# Rate limiting and quota exceptions


class RateLimitError(AIError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, provider: str, retry_after: Optional[int] = None):
        message = f"Rate limit exceeded for '{provider}'"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message, {"provider": provider, "retry_after": retry_after})


class QuotaExceededError(AIError):
    """Raised when API quota is exceeded."""

    def __init__(self, provider: str, quota_type: str = "requests"):
        message = f"{quota_type.capitalize()} quota exceeded for '{provider}'"
        super().__init__(message, {"provider": provider, "quota_type": quota_type})


# Plugin-related exceptions


class PluginError(AIError):
    """Base exception for plugin-related errors."""

    pass


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""

    def __init__(self, plugin_path: str, reason: str):
        message = f"Failed to load plugin '{plugin_path}': {reason}"
        super().__init__(message, {"plugin_path": plugin_path, "reason": reason})


class PluginValidationError(PluginError):
    """Raised when a plugin is invalid."""

    def __init__(self, plugin_name: str, reason: str):
        message = f"Plugin '{plugin_name}' validation failed: {reason}"
        super().__init__(message, {"plugin_name": plugin_name, "reason": reason})


# Session-related exceptions


class SessionError(AIError):
    """Base exception for session-related errors."""

    pass


class SessionNotFoundError(SessionError):
    """Raised when a session is not found."""

    def __init__(self, session_id: str):
        message = f"Session '{session_id}' not found"
        super().__init__(message, {"session_id": session_id})


class SessionLoadError(SessionError):
    """Raised when session loading fails."""

    def __init__(self, file_path: str, reason: str):
        message = f"Failed to load session from '{file_path}': {reason}"
        super().__init__(message, {"file_path": file_path, "reason": reason})


class SessionSaveError(SessionError):
    """Raised when session saving fails."""

    def __init__(self, file_path: str, reason: str):
        message = f"Failed to save session to '{file_path}': {reason}"
        super().__init__(message, {"file_path": file_path, "reason": reason})
