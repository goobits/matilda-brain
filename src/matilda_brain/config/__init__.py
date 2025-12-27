"""Configuration management for TTT."""

from .loader import get_project_config, set_suppress_warnings
from .manager import ConfigManager
from .schema import (
    configure,
    get_config,
    get_model_registry,
    load_config,
    merge_configs,
    model_registry,
    save_config,
    set_config,
)

__all__ = [
    "configure",
    "ConfigManager",
    "get_config",
    "get_model_registry",
    "get_project_config",
    "load_config",
    "merge_configs",
    "model_registry",
    "save_config",
    "set_config",
    "set_suppress_warnings",
]
