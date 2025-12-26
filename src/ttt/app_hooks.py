#!/usr/bin/env python3
"""Business logic hooks for the TTT CLI.

This module provides backward compatibility by re-exporting all hook
handlers from the hooks submodule.

The implementation has been split into:
- hooks/utils.py: Helper functions (is_verbose_mode, setup_logging_level, etc.)
- hooks/core.py: on_ask, on_chat handlers
- hooks/config.py: on_config_*, on_list, on_export handlers
- hooks/tools.py: on_tools_* handlers
- hooks/models.py: on_models, on_info, on_status handlers
- hooks/server.py: on_serve, on_stateless handlers
"""

# Re-export all hook handlers for backward compatibility
from .hooks import (
    # Utils
    is_verbose_mode,
    setup_logging_level,
    resolve_model_alias,
    parse_tools_arg,
    resolve_tools,
    apply_coding_optimization,
    # Core
    on_ask,
    on_chat,
    # Config
    on_list,
    on_config_get,
    on_config_set,
    on_config_list,
    on_export,
    # Tools
    on_tools_enable,
    on_tools_disable,
    on_tools_list,
    # Models
    show_models_list,
    show_model_info,
    show_backend_status,
    on_status,
    on_models,
    on_info,
    # Server
    on_stateless,
    on_serve,
)

__all__ = [
    # Utils
    "is_verbose_mode",
    "setup_logging_level",
    "resolve_model_alias",
    "parse_tools_arg",
    "resolve_tools",
    "apply_coding_optimization",
    # Core
    "on_ask",
    "on_chat",
    # Config
    "on_list",
    "on_config_get",
    "on_config_set",
    "on_config_list",
    "on_export",
    # Tools
    "on_tools_enable",
    "on_tools_disable",
    "on_tools_list",
    # Models
    "show_models_list",
    "show_model_info",
    "show_backend_status",
    "on_status",
    "on_models",
    "on_info",
    # Server
    "on_stateless",
    "on_serve",
]
