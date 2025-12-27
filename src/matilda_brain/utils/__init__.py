"""Utility modules for the AI library."""

from typing import TypeVar

from rich.console import Console

from .async_utils import optimized_run_async, run_coro_in_background
from .logger import get_logger

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
]
