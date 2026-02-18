"""
The Unified AI Library

A single, elegant interface for local and cloud AI models.
"""

from importlib import metadata
from importlib import import_module
from pathlib import Path
import tomllib
from typing import TYPE_CHECKING


def _get_model_registry():
    from .config import model_registry

    return model_registry


# Create a lazy proxy for model_registry
class _ModelRegistryProxy:
    def __getattr__(self, name: str):
        return getattr(_get_model_registry(), name)


if TYPE_CHECKING:
    from .backends import CloudBackend, HubBackend, LocalBackend
    from .config import configure
    from .config.schema import ModelRegistry
    from .core.api import achat, ask, ask_async, chat, stream, stream_async
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
    from .core.types import ContentKind, Message, Proposal, RiskLevel, Role
    from .plugins import discover_plugins, load_plugin, register_backend
    from .session.chat import PersistentChatSession
    from .tools.base import ToolCall, ToolDefinition, ToolResult


model_registry: "ModelRegistry" = _ModelRegistryProxy()  # type: ignore[assignment]

_EXPORTS = {
    "ask": (".core.api", "ask"),
    "stream": (".core.api", "stream"),
    "chat": (".core.api", "chat"),
    "ask_async": (".core.api", "ask_async"),
    "stream_async": (".core.api", "stream_async"),
    "achat": (".core.api", "achat"),
    "AIResponse": (".core.models", "AIResponse"),
    "ImageInput": (".core.models", "ImageInput"),
    "ConfigModel": (".core.models", "ConfigModel"),
    "ModelInfo": (".core.models", "ModelInfo"),
    "Role": (".core.types", "Role"),
    "ContentKind": (".core.types", "ContentKind"),
    "Message": (".core.types", "Message"),
    "Proposal": (".core.types", "Proposal"),
    "RiskLevel": (".core.types", "RiskLevel"),
    "ToolCall": (".tools.base", "ToolCall"),
    "ToolResult": (".tools.base", "ToolResult"),
    "ToolDefinition": (".tools.base", "ToolDefinition"),
    "PersistentChatSession": (".session.chat", "PersistentChatSession"),
    "configure": (".config", "configure"),
    "LocalBackend": (".backends", "LocalBackend"),
    "CloudBackend": (".backends", "CloudBackend"),
    "HubBackend": (".backends", "HubBackend"),
    "register_backend": (".plugins", "register_backend"),
    "discover_plugins": (".plugins", "discover_plugins"),
    "load_plugin": (".plugins", "load_plugin"),
    "AIError": (".core.exceptions", "AIError"),
    "BackendError": (".core.exceptions", "BackendError"),
    "BackendNotAvailableError": (".core.exceptions", "BackendNotAvailableError"),
    "BackendConnectionError": (".core.exceptions", "BackendConnectionError"),
    "BackendTimeoutError": (".core.exceptions", "BackendTimeoutError"),
    "ModelError": (".core.exceptions", "ModelError"),
    "ModelNotFoundError": (".core.exceptions", "ModelNotFoundError"),
    "ModelNotSupportedError": (".core.exceptions", "ModelNotSupportedError"),
    "ConfigurationError": (".core.exceptions", "ConfigurationError"),
    "APIKeyError": (".core.exceptions", "APIKeyError"),
    "ConfigFileError": (".core.exceptions", "ConfigFileError"),
    "ValidationError": (".core.exceptions", "ValidationError"),
    "InvalidPromptError": (".core.exceptions", "InvalidPromptError"),
    "InvalidParameterError": (".core.exceptions", "InvalidParameterError"),
    "ResponseError": (".core.exceptions", "ResponseError"),
    "EmptyResponseError": (".core.exceptions", "EmptyResponseError"),
    "ResponseParsingError": (".core.exceptions", "ResponseParsingError"),
    "FeatureNotAvailableError": (".core.exceptions", "FeatureNotAvailableError"),
    "MultiModalError": (".core.exceptions", "MultiModalError"),
    "RateLimitError": (".core.exceptions", "RateLimitError"),
    "QuotaExceededError": (".core.exceptions", "QuotaExceededError"),
    "PluginError": (".core.exceptions", "PluginError"),
    "PluginLoadError": (".core.exceptions", "PluginLoadError"),
    "PluginValidationError": (".core.exceptions", "PluginValidationError"),
    "SessionError": (".core.exceptions", "SessionError"),
    "SessionNotFoundError": (".core.exceptions", "SessionNotFoundError"),
    "SessionLoadError": (".core.exceptions", "SessionLoadError"),
    "SessionSaveError": (".core.exceptions", "SessionSaveError"),
}


def __getattr__(name: str):
    if name == "model_registry":
        return model_registry

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def _get_version() -> str:
    try:
        return metadata.version("goobits-matilda-brain")
    except Exception:
        pass

    try:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return str(data["project"]["version"])
    except Exception:
        return "unknown"


__version__ = _get_version()
__all__ = [
    "ask",
    "stream",
    "chat",
    "ask_async",
    "stream_async",
    "achat",
    "AIResponse",
    "ImageInput",
    "ConfigModel",
    "ModelInfo",
    "Role",
    "ContentKind",
    "Message",
    "Proposal",
    "RiskLevel",
    "ToolCall",
    "ToolResult",
    "ToolDefinition",
    "PersistentChatSession",
    "configure",
    "LocalBackend",
    "CloudBackend",
    "HubBackend",
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
