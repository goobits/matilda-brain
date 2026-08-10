#!/usr/bin/env python3
"""
Hooks module for Matilda Brain CLI business logic.

This module provides all hook handlers for the CLI commands:
- core: on_ask, on_chat (main interaction handlers)
- config: on_config_*, on_list, on_export
- tools: on_tools_*
- models: on_models, on_info, on_status
- server: on_serve, on_stateless
- utils: helper functions
"""

from .config import on_config_get, on_config_list, on_config_set, on_export, on_list
from .core import on_ask, on_chat
from .models import on_info, on_models, on_status, show_backend_status, show_model_info, show_models_list
from .server import on_serve, on_stateless
from .tools import on_tools_disable, on_tools_enable, on_tools_list
from .utils import (
    apply_coding_optimization,
    get_enabled_tool_names,
    is_verbose_mode,
    parse_tools_arg,
    resolve_model_alias,
    resolve_tools,
    setup_logging_level,
)

__all__ = [
    # Utils
    "is_verbose_mode",
    "setup_logging_level",
    "resolve_model_alias",
    "parse_tools_arg",
    "resolve_tools",
    "apply_coding_optimization",
    "get_enabled_tool_names",
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
