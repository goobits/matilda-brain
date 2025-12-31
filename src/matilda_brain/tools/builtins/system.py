"""System-related built-in tools.

This module provides tools for system operations like getting current time.
"""

import datetime

import zoneinfo

from matilda_brain.tools import tool


@tool(category="time", description="Get the current time in a specified timezone")
def get_current_time(timezone: str = "UTC", format: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """Get current time in specified timezone.

    Args:
        timezone: Timezone name (e.g., 'UTC', 'US/Eastern', 'Europe/London')
        format: Time format string (default: '%Y-%m-%d %H:%M:%S %Z')

    Returns:
        Formatted time string or error message
    """
    try:
        # Get timezone
        tz = zoneinfo.ZoneInfo(timezone)

        # Get current time
        now = datetime.datetime.now(tz)

        # Format time
        return now.strftime(format)

    except zoneinfo.ZoneInfoNotFoundError:
        available = ", ".join(sorted(zoneinfo.available_timezones())[:10])
        return f"Error: Unknown timezone '{timezone}'. Examples: {available}..."
    except Exception:
        from matilda_brain.utils import get_logger

        get_logger(__name__).exception("Error getting time")
        return "Error getting time - see logs for details"


__all__ = ["get_current_time"]
