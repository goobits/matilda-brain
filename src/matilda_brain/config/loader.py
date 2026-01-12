"""Configuration loader utility for easy access to project config values."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import tomllib

from ..internal.utils import get_logger

logger = get_logger(__name__)

# Cache for project config
_project_config_cache: Optional[Dict[str, Any]] = None

# Check if we should suppress warnings (JSON mode or pipe mode)
_suppress_warnings = os.environ.get("TTT_JSON_MODE", "").lower() == "true"


def _is_pipe_mode() -> bool:
    """Check if stdin is coming from a pipe (not a tty)."""
    try:
        return not sys.stdin.isatty()
    except (OSError, AttributeError):
        # If we can't determine, assume not in pipe mode
        return False


def set_suppress_warnings(suppress: bool) -> None:
    """Set whether to suppress warnings (used in JSON mode)."""
    global _suppress_warnings
    _suppress_warnings = suppress


def _default_config_path() -> Path:
    env_path = os.environ.get("MATILDA_CONFIG")
    if env_path:
        return Path(env_path)
    return Path.home() / ".matilda" / "config.toml"


def get_project_config() -> Dict[str, Any]:
    """
    Get the project configuration from the shared TOML config.

    This function caches the configuration to avoid repeated file reads.

    Returns:
        Dictionary containing project configuration
    """
    global _project_config_cache

    if _project_config_cache is not None:
        return _project_config_cache

    config_path = _default_config_path()
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                full_config = tomllib.load(f)
            brain_config = full_config.get("brain")
            if brain_config is None:
                raise KeyError("Missing [brain] section in matilda config")
            _project_config_cache = brain_config
            logger.debug(f"Loaded project config from {config_path}")
            return _project_config_cache
        except Exception as e:
            if os.environ.get("TTT_JSON_MODE", "").lower() != "true" and not _is_pipe_mode():
                logger.warning(f"Failed to load project config from {config_path}: {e}")

    # If we get here, no config is available.
    json_mode = os.environ.get("TTT_JSON_MODE", "").lower() == "true"
    pipe_mode = _is_pipe_mode()

    if "--json" in getattr(sys, "argv", []) or json_mode or _suppress_warnings or pipe_mode:
        pass
    else:
        logger.warning("Matilda config not found - expected ~/.matilda/config.toml")

    _project_config_cache = {}
    return _project_config_cache


def get_config_value(path: str, default: Any = None) -> Any:
    """
    Get a configuration value by path (dot-separated).

    Args:
        path: Dot-separated path to the config value (e.g., "tools.max_file_size")
        default: Default value if path not found

    Returns:
        Configuration value or default

    Example:
        >>> get_config_value("tools.max_file_size", 10485760)
        10485760
        >>> get_config_value("backends.cloud.timeout", 30)
        30
    """
    config = get_project_config()

    keys = path.split(".")
    value = config

    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default
