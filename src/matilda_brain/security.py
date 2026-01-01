"""
Security utilities for Matilda Brain server.

Provides secure default configurations for CORS and other security-related settings.
"""

import os
import warnings
from typing import List

from .utils import get_logger

logger = get_logger(__name__)


def get_allowed_origins() -> List[str]:
    """
    Get the list of allowed CORS origins.

    Behavior:
    - If ALLOWED_ORIGINS env var is set, parse and return those origins
    - If MATILDA_DEV_MODE=1 is set, return common development origins as defaults
    - Otherwise, return empty list (secure default) and issue a warning

    Returns:
        List of allowed origin strings. Empty list means no origins are allowed.
    """
    allowed_origins_env = os.getenv("ALLOWED_ORIGINS")

    if allowed_origins_env:
        # User has explicitly configured allowed origins
        origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
        logger.debug(f"Using configured ALLOWED_ORIGINS: {origins}")
        return origins

    # Check if we're in dev mode
    dev_mode = os.getenv("MATILDA_DEV_MODE", "").strip() == "1"

    if dev_mode:
        # Development mode: allow common development origins
        dev_origins = ["http://localhost:3000", "http://localhost:5173"]
        logger.info("MATILDA_DEV_MODE=1: Using development CORS origins")
        return dev_origins

    # Production mode without explicit configuration: secure default
    warnings.warn(
        "ALLOWED_ORIGINS not set and MATILDA_DEV_MODE not enabled. "
        "CORS will reject all cross-origin requests. "
        "Set ALLOWED_ORIGINS environment variable or enable MATILDA_DEV_MODE=1 for development.",
        UserWarning,
        stacklevel=2,
    )
    logger.warning(
        "CORS: No allowed origins configured. Set ALLOWED_ORIGINS env var "
        "or enable MATILDA_DEV_MODE=1 for development."
    )
    return []


def is_origin_allowed(origin: str, allowed_origins: List[str]) -> bool:
    """
    Check if an origin is in the allowed origins list.

    Args:
        origin: The origin to check
        allowed_origins: List of allowed origins

    Returns:
        True if origin is allowed, False otherwise
    """
    return origin in allowed_origins
