#!/usr/bin/env python3
"""Hook handlers for TTT CLI."""

import json as json_module
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import rich_click as click
from rich.console import Console

console = Console()

from matilda_brain.config.manager import ConfigManager
from .utils import setup_logging_level

def on_tools_enable(command_name: str, tool_name: str, **kwargs) -> None:
    """Hook for 'tools enable' subcommand.

    Removes a tool from the disabled list, making it available for use.

    Args:
        tool_name: Name of the tool to enable
    """
    config_manager = ConfigManager()
    merged_config = config_manager.get_merged_config()
    disabled_tools = merged_config.get("tools", {}).get("disabled", [])

    if tool_name in disabled_tools:
        disabled_tools.remove(tool_name)
        config_manager.set_value("tools.disabled", disabled_tools)
        click.echo(f"Tool '{tool_name}' has been enabled")
    else:
        click.echo(f"Tool '{tool_name}' is already enabled")



def on_tools_disable(command_name: str, tool_name: str, **kwargs) -> None:
    """Hook for 'tools disable' subcommand.

    Adds a tool to the disabled list, preventing it from being used.

    Args:
        tool_name: Name of the tool to disable
    """
    config_manager = ConfigManager()
    merged_config = config_manager.get_merged_config()
    disabled_tools = merged_config.get("tools", {}).get("disabled", [])

    if tool_name not in disabled_tools:
        disabled_tools.append(tool_name)
        config_manager.set_value("tools.disabled", disabled_tools)
        click.echo(f"Tool '{tool_name}' has been disabled")
    else:
        click.echo(f"Tool '{tool_name}' is already disabled")



def on_tools_list(command_name: str, show_disabled: bool, **kwargs) -> None:
    """Hook for 'tools list' subcommand.

    Lists all available tools with their status (enabled/disabled).

    Args:
        show_disabled: Whether to include disabled tools in the output
    """
    from matilda_brain.tools import list_tools

    config_manager = ConfigManager()
    merged_config = config_manager.get_merged_config()
    disabled_tools = merged_config.get("tools", {}).get("disabled", [])

    tools = list_tools()

    console.print("\n[bold]Available Tools:[/bold]")
    for tool in tools:
        status = "[red]disabled[/red]" if tool.name in disabled_tools else "[green]enabled[/green]"
        if show_disabled or tool.name not in disabled_tools:
            console.print(f"  • [cyan]{tool.name}[/cyan] ({status}): {tool.description}")


# Additional helper functions needed by hooks

