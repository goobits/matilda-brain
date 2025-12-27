"""Configuration loader utility for easy access to project config values."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ..utils import get_logger

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


def get_project_config() -> Dict[str, Any]:
    """
    Get the project configuration from config.yaml.

    This function caches the configuration to avoid repeated file reads.

    Returns:
        Dictionary containing project configuration
    """
    global _project_config_cache

    if _project_config_cache is not None:
        return _project_config_cache

    # Try to load project config.yaml from current directory (optional)
    project_config_path = Path.cwd() / "config.yaml"
    if project_config_path.exists():
        try:
            with open(project_config_path) as f:
                _project_config_cache = yaml.safe_load(f)
                logger.debug(f"Loaded project config from {project_config_path}")
                return _project_config_cache
        except Exception as e:
            if os.environ.get("TTT_JSON_MODE", "").lower() != "true" and not _is_pipe_mode():
                logger.warning(f"Failed to load project config from {project_config_path}: {e}")

    # Fall back to bundled defaults (should always exist)
    defaults_path = Path(__file__).parent / "defaults.yaml"
    if defaults_path.exists():
        try:
            with open(defaults_path) as f:
                _project_config_cache = yaml.safe_load(f)
                logger.debug(f"Loaded project config from {defaults_path}")
                return _project_config_cache
        except Exception as e:
            if os.environ.get("TTT_JSON_MODE", "").lower() != "true" and not _is_pipe_mode():
                logger.warning(f"Failed to load bundled defaults from {defaults_path}: {e}")

    # If we get here, even defaults.yaml is missing (should never happen)
    # Check suppress warnings both from variable and environment
    json_mode = os.environ.get("TTT_JSON_MODE", "").lower() == "true"
    pipe_mode = _is_pipe_mode()

    # Only warn if even the bundled defaults are missing (serious issue)
    if "--json" in getattr(sys, "argv", []) or json_mode or _suppress_warnings or pipe_mode:
        # Suppress the warning - it will be included in JSON response or is not relevant in pipe mode
        pass
    else:
        logger.warning("Bundled defaults.yaml is missing - this indicates a broken installation")

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
