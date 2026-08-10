"""Plugin system for Matilda Brain."""

from .loader import (
    BackendPlugin,
    PluginRegistry,
    discover_plugins,
    load_plugin,
    plugin_registry,
    register_backend,
)

__all__ = [
    "BackendPlugin",
    "PluginRegistry",
    "discover_plugins",
    "load_plugin",
    "plugin_registry",
    "register_backend",
]
