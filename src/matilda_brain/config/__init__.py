"""Configuration management for Matilda Brain."""

from .manager import ConfigManager, get_config_value, get_project_config, set_suppress_warnings
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
    "ConfigManager",
    "configure",
    "get_config",
    "get_config_value",
    "get_model_registry",
    "get_project_config",
    "load_config",
    "merge_configs",
    "model_registry",
    "save_config",
    "set_config",
    "set_suppress_warnings",
]
