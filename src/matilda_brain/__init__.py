"""
The Unified AI Library

A single, elegant interface for local and cloud AI models.
"""

# ruff: noqa: I001 (import order critical for avoiding circular imports)
from .core.api import ChatSession, achat, ask, ask_async, chat, stream, stream_async
from .backends import CloudBackend, LocalBackend
from .config import configure
from .core.exceptions import (
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
from .core.models import AIResponse, ConfigModel, ImageInput, ModelInfo
from .plugins import discover_plugins, load_plugin, register_backend
from .session.chat import PersistentChatSession
from .tools.builtins import load_builtin_tools


# Import model_registry lazily to avoid import-time initialization
def _get_model_registry():
    from .config import model_registry

    return model_registry


# Create a lazy proxy for model_registry
class _ModelRegistryProxy:
    def __getattr__(self, name: str):
        return getattr(_get_model_registry(), name)


model_registry = _ModelRegistryProxy()

load_builtin_tools()

__version__ = "1.0.3"
__all__ = [
    "ask",
    "stream",
    "chat",
    "ask_async",
    "stream_async",
    "achat",
    "ChatSession",
    "AIResponse",
    "ImageInput",
    "ConfigModel",
    "ModelInfo",
    "PersistentChatSession",
    "configure",
    "LocalBackend",
    "CloudBackend",
    "model_registry",
    "register_backend",
    "discover_plugins",
    "load_plugin",
    # Exceptions
    "AIError",
    "BackendError",
    "BackendNotAvailableError",
    "BackendConnectionError",
    "BackendTimeoutError",
    "ModelError",
    "ModelNotFoundError",
    "ModelNotSupportedError",
    "ConfigurationError",
    "APIKeyError",
    "ConfigFileError",
    "ValidationError",
    "InvalidPromptError",
    "InvalidParameterError",
    "ResponseError",
    "EmptyResponseError",
    "ResponseParsingError",
    "FeatureNotAvailableError",
    "MultiModalError",
    "RateLimitError",
    "QuotaExceededError",
    "PluginError",
    "PluginLoadError",
    "PluginValidationError",
    "SessionError",
    "SessionNotFoundError",
    "SessionLoadError",
    "SessionSaveError",
]
