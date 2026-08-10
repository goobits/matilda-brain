"""Plugin system for TTT."""

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
