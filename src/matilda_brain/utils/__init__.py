"""Utility modules for the AI library."""

from typing import TypeVar

from rich.console import Console

from .async_utils import optimized_run_async, run_coro_in_background
from .logger import get_logger
from .messages import build_message_list, extract_messages_from_kwargs
from .providers import (
    PROVIDER_ENV_VARS,
    get_api_key,
    get_available_providers,
    get_configured_providers,
    get_env_var_for_provider,
    has_api_key,
)

console = Console()

T = TypeVar("T")

# Use the optimized version by default
run_async = optimized_run_async


__all__ = [
    "get_logger",
    "console",
    "run_async",
    "run_coro_in_background",
    "optimized_run_async",
    # Message building utilities
    "build_message_list",
    "extract_messages_from_kwargs",
    # Provider utilities
    "PROVIDER_ENV_VARS",
    "get_env_var_for_provider",
    "has_api_key",
    "get_api_key",
    "get_available_providers",
    "get_configured_providers",
]
