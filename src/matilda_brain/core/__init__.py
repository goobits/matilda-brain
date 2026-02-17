"""Core TTT library functionality."""

from typing import Any

# NOTE: This package is imported by low-level modules (e.g. backends/base.py imports
# `matilda_brain.core.models`). Avoid importing modules here that depend on backends,
# otherwise we create circular imports during package initialization.
#
# We keep the public API stable via lazy attribute resolution (PEP 562).
def __getattr__(name: str) -> Any:
    if name in {"ask", "chat", "stream"}:
        from .api import ask, chat, stream

        return {"ask": ask, "chat": chat, "stream": stream}[name]
    if name == "Router":
        from .routing import Router

        return Router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    # Keep IDE completion consistent with __all__.
    return sorted(set(globals().keys()) | {"ask", "chat", "stream", "Router"})


from .exceptions import (
    AIError,
    APIKeyError,
    BackendConnectionError,
    BackendError,
    BackendNotAvailableError,
    BackendTimeoutError,
    ConfigFileError,
    ConfigurationError,
    EmptyResponseError,
    FeatureNotAvailableError,
    InvalidParameterError,
    InvalidPromptError,
    ModelError,
    ModelNotFoundError,
    ModelNotSupportedError,
    MultiModalError,
    PluginError,
    PluginLoadError,
    PluginValidationError,
    QuotaExceededError,
    RateLimitError,
    ResponseError,
    ResponseParsingError,
    SessionError,
    SessionLoadError,
    SessionNotFoundError,
    SessionSaveError,
    ValidationError,
)
from .models import AIResponse, ImageInput, ModelInfo
from .types import ContentKind, Message, Proposal, RiskLevel, Role

__all__ = [
    # API functions
    "ask",
    "chat",
    "stream",
    # Data models
    "AIResponse",
    "ImageInput",
    "ModelInfo",
    "Role",
    "ContentKind",
    "Message",
    "Proposal",
    "RiskLevel",
    "Router",
    # Exceptions
    "AIError",
    "APIKeyError",
    "BackendConnectionError",
    "BackendError",
    "BackendNotAvailableError",
    "BackendTimeoutError",
    "ConfigFileError",
    "ConfigurationError",
    "EmptyResponseError",
    "FeatureNotAvailableError",
    "InvalidParameterError",
    "InvalidPromptError",
    "ModelError",
    "ModelNotFoundError",
    "ModelNotSupportedError",
    "MultiModalError",
    "PluginError",
    "PluginLoadError",
    "PluginValidationError",
    "QuotaExceededError",
    "RateLimitError",
    "ResponseError",
    "ResponseParsingError",
    "SessionError",
    "SessionLoadError",
    "SessionNotFoundError",
    "SessionSaveError",
    "ValidationError",
]
