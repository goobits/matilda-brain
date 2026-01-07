"""Logging utilities using rich for beautiful terminal output."""

import logging

# Check for JSON mode early and configure accordingly
import os
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install

_json_mode = os.environ.get("TTT_JSON_MODE", "").lower() == "true"

if not _json_mode:
    # Only install rich traceback handler if not in JSON mode
    # Respect the RICH_TRACEBACK_SHOW_LOCALS environment variable
    show_locals = os.environ.get("RICH_TRACEBACK_SHOW_LOCALS", "false").lower() == "true"
    install(show_locals=show_locals)

# Create console instance
console = Console()

# Configure root logger for JSON mode if needed
if _json_mode:
    import logging

    # Completely disable all logging
    logging.disable(logging.CRITICAL)
    # Also configure root logger to suppress everything
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    # Add a null handler to suppress all output
    root_logger.addHandler(logging.NullHandler())
    # Ensure no propagation
    root_logger.propagate = False
    # Set high level to suppress everything
    root_logger.setLevel(logging.CRITICAL + 1)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with rich formatting.

    Args:
        name: Logger name. If None, uses the calling module's name.

    Returns:
        Configured logger instance.
    """
    if name is None:
        # Get the calling module's name
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "ai")
        else:
            name = "ai"

    logger = logging.getLogger(name)

    # Configure logger for JSON mode if not already configured
    import os

    if os.environ.get("TTT_JSON_MODE", "").lower() == "true" and not logger.handlers:
        # In JSON mode, use a null handler to suppress all output
        logger.addHandler(logging.NullHandler())
        logger.propagate = False

    return logger


def set_log_level(level: str) -> None:
    """
    Set the global log level.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    if level.upper() in level_map:
        logging.getLogger().setLevel(level_map[level.upper()])
        console.print(f"[blue]Log level set to {level.upper()}[/blue]")
    else:
        console.print(f"[red]Invalid log level: {level}[/red]")


def setup_logging(
    level: Optional[int] = None,
    format: Optional[str] = None,
    handlers: Optional[list] = None,
) -> None:
    """
    Setup logging configuration.

    Args:
        level: Logging level (defaults to INFO, or DEBUG if DEBUG env var is set)
        format: Log format string
        handlers: List of logging handlers
    """
    import os

    # Determine log level
    if level is None:
        # Check environment variables
        if os.environ.get("LOG_LEVEL"):
            level_name = os.environ["LOG_LEVEL"].upper()
            level = getattr(logging, level_name, logging.INFO)
        elif os.environ.get("DEBUG", "").lower() in ("true", "1", "yes", "on"):
            level = logging.DEBUG
        else:
            level = logging.INFO

    # Use default format if not provided
    if format is None:
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Use RichHandler if no handlers provided
    if handlers is None:
        handlers = [RichHandler(console=console, rich_tracebacks=True)]

    # Configure logging
    logging.basicConfig(level=level, format=format, handlers=handlers)


# Export console for direct use
__all__ = ["get_logger", "set_log_level", "console", "setup_logging"]
