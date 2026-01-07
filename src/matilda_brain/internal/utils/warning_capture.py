"""Simple warning capture utility for JSON output mode."""

import logging
import sys
from io import StringIO
from typing import Any, List, Optional, TextIO


class WarningCapture:
    """Simple context manager to capture warnings during execution."""

    def __init__(self) -> None:
        self.buffer = StringIO()
        self.handler = logging.StreamHandler(self.buffer)
        self.handler.setLevel(logging.WARNING)
        # Simple format - just the message, no timestamp or level prefix
        formatter = logging.Formatter("%(message)s")
        self.handler.setFormatter(formatter)

    def __enter__(self) -> "WarningCapture":
        logging.getLogger().addHandler(self.handler)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        logging.getLogger().removeHandler(self.handler)

    def get_warnings(self) -> List[str]:
        """Get captured warnings as a list."""
        content = self.buffer.getvalue()
        if not content:
            return []
        # Split by newlines and filter empty lines
        return [line.strip() for line in content.splitlines() if line.strip()]


class EarlyWarningCapture:
    """Capture warnings that happen at import time by redirecting stderr."""

    def __init__(self) -> None:
        self.original_stderr: Optional[TextIO] = None
        self.buffer = StringIO()
        self.warnings: List[str] = []

    def start(self) -> None:
        """Start capturing stderr."""
        self.original_stderr = sys.stderr
        sys.stderr = self.buffer

    def stop(self) -> None:
        """Stop capturing and extract warnings."""
        if self.original_stderr:
            sys.stderr = self.original_stderr

        # Extract warning messages from captured stderr
        content = self.buffer.getvalue()
        if content:
            for line in content.splitlines():
                line = line.strip()
                # Common warning patterns from config loading
                if any(
                    pattern in line
                    for pattern in [
                        "config.yaml not found",
                        "No models loaded from config",
                        "using minimal defaults",
                    ]
                ):
                    if line not in self.warnings:  # Avoid duplicates
                        self.warnings.append(line)

    def get_warnings(self) -> List[str]:
        """Get captured warnings."""
        return self.warnings
