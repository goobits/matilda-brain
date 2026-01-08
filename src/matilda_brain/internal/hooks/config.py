#!/usr/bin/env python3
"""Hook handlers for TTT CLI."""

import json as json_module
from pathlib import Path
from typing import Any, Dict, Optional

import rich_click as click
from rich.console import Console

console = Console()

from matilda_brain.config.manager import ConfigManager
from matilda_brain.session.manager import ChatSessionManager
from .models import show_models_list

def on_list(
    command_name: str, resource: Optional[str] = None, format: str = "table", **kwargs
) -> None:
    """Hook for 'list' command.

    Lists various TTT resources like models, sessions, or tools in either
    tabular or JSON format. If no resource is specified, shows a summary
    of all available resources.

    Args:
        resource: Type of resource to list ('models', 'sessions', 'tools'), or None for summary
        format: Output format ('table', 'json')
    """
    if resource is None:
        # No resource specified, show summary of all resources
        if format == "json":
            from matilda_brain.config.schema import get_model_registry
            from matilda_brain.tools import list_tools

            session_manager = ChatSessionManager()
            model_registry = get_model_registry()
            tools = list_tools()

            summary = {
                "models": {
                    "count": len(model_registry.models),
                    "available": list(model_registry.models.keys())[:5],  # First 5 models
                },
                "sessions": {
                    "count": len(session_manager.list_sessions()),
                    "recent": session_manager.list_sessions()[:3],  # 3 most recent
                },
                "tools": {"count": len(tools), "available": [t.name for t in tools[:5]]},  # First 5 tools
            }
            click.echo(json_module.dumps(summary, indent=2))
        else:
            console.print("\n[bold]TTT Resources Summary[/bold]\n")

            # Models count
            from matilda_brain.config.schema import get_model_registry

            model_registry = get_model_registry()
            console.print(f"[cyan]Models:[/cyan] {len(model_registry.models)} available")
            console.print("  Run [green]ttt list models[/green] to see all models\n")

            # Sessions count
            session_manager = ChatSessionManager()
            sessions = session_manager.list_sessions()
            console.print(f"[cyan]Sessions:[/cyan] {len(sessions)} saved")
            console.print("  Run [green]ttt list sessions[/green] to see all sessions\n")

            # Tools count
            from matilda_brain.tools import list_tools

            tools = list_tools()
            console.print(f"[cyan]Tools:[/cyan] {len(tools)} available")
            console.print("  Run [green]ttt list tools[/green] to see all tools\n")
        return

    if resource == "models":
        show_models_list(json_output=(format == "json"))
    elif resource == "sessions":
        session_manager = ChatSessionManager()
        if format == "json":
            sessions = session_manager.list_sessions()
            click.echo(json_module.dumps(sessions))
        else:
            session_manager.display_sessions_table()
    elif resource == "tools":
        from matilda_brain.tools import list_tools

        tools = list_tools()
        if format == "json":
            tools_data = [{"name": t.name, "description": t.description} for t in tools]
            click.echo(json_module.dumps(tools_data))
        else:
            console.print("\n[bold]Available Tools:[/bold]")
            for tool in tools:
                console.print(f"  • [cyan]{tool.name}[/cyan]: {tool.description}")



def on_config_get(command_name: str, key: str, **kwargs) -> None:
    """Hook for 'config get' subcommand.

    Retrieves and displays a specific configuration value using dot notation.

    Args:
        key: Configuration key in dot notation (e.g., 'models.default')
    """
    config_manager = ConfigManager()
    config_manager.show_value(key)



def on_config_set(command_name: str, key: str, value: str, **kwargs) -> None:
    """Hook for 'config set' subcommand.

    Sets a configuration value using dot notation. Creates nested
    structure as needed and persists to user configuration file.

    Args:
        key: Configuration key in dot notation (e.g., 'models.default')
        value: String value to set (will be parsed as appropriate type)
    """
    config_manager = ConfigManager()
    config_manager.set_value(key, value)



def on_config_list(command_name: str, show_secrets: bool, **kwargs) -> None:
    """Hook for 'config list' subcommand.

    Displays the complete merged configuration from all sources.
    Sensitive values like API keys are masked unless explicitly requested.

    Args:
        show_secrets: If True, shows actual API keys; otherwise masks them
    """
    config_manager = ConfigManager()
    merged_config = config_manager.get_merged_config()

    # Mask sensitive values unless show_secrets is True
    if not show_secrets:

        def mask_sensitive(obj: Any, key: Optional[str] = None) -> Any:
            if isinstance(obj, dict):
                return {k: mask_sensitive(v, k) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [mask_sensitive(item) for item in obj]
            elif key and ("key" in key.lower() or "secret" in key.lower() or "token" in key.lower()):
                return "***" if obj else None
            else:
                return obj

        merged_config = mask_sensitive(merged_config)

    click.echo(json_module.dumps(merged_config, indent=2))



def on_export(
    command_name: str,
    session: Optional[str] = None,
    format: str = "markdown",
    output: Optional[str] = None,
    include_metadata: bool = False,
    **kwargs,
) -> None:
    """Hook for 'export' command.

    Exports a chat session to various formats (JSON, YAML, Markdown).
    Can output to file or stdout with optional metadata inclusion.
    If no session is specified, shows the list of available sessions.

    Args:
        session: Session ID to export
        format: Output format ('json', 'yaml', 'markdown')
        output: Output file path, or None to print to stdout
        include_metadata: Whether to include session metadata in export

    Raises:
        SystemExit: If session not found or PyYAML missing for YAML format
    """
    if session is None:
        # No session specified, show available sessions
        on_list(command_name="list", resource="sessions", format="table", verbose=False)
        return

    session_manager = ChatSessionManager()

    # Load session
    chat_session = session_manager.load_session(session)
    if not chat_session:
        click.echo(f"Error: Session '{session}' not found", err=True)
        raise ValueError(f"Session '{session}' not found")

    # Export data
    export_data: Dict[str, Any] = {
        "session_id": chat_session.id,
        "created_at": (
            chat_session.created_at if hasattr(chat_session, "created_at") and chat_session.created_at else None
        ),
        "messages": chat_session.messages,
    }

    if include_metadata:
        export_data["metadata"] = {
            "model": getattr(chat_session, "model", None),
            "system_prompt": getattr(chat_session, "system_prompt", None),
            "tools": getattr(chat_session, "tools", None),
        }

    # Format output
    if format == "json":
        output_text = json_module.dumps(export_data, indent=2)
    elif format == "yaml":
        try:
            import yaml

            output_text = yaml.dump(export_data, default_flow_style=False)
        except ImportError:
            click.echo("Error: PyYAML is not installed. Use 'pip install pyyaml'", err=True)
            raise ImportError("PyYAML is not installed") from None
    else:  # markdown
        output_text = f"# Chat Session: {session}\n\n"
        if include_metadata:
            metadata = export_data.get("metadata")
            if metadata and isinstance(metadata, dict):
                model_info = metadata.get("model", "Unknown")
                output_text += f"**Model**: {model_info}\n\n"

        messages = export_data.get("messages")
        if messages and isinstance(messages, list):
            for msg in messages:
                if hasattr(msg, "role") and hasattr(msg, "content"):
                    output_text += f"## {msg.role.capitalize()}\n\n{msg.content}\n\n"
                elif isinstance(msg, dict) and "role" in msg and "content" in msg:
                    output_text += f"## {msg['role'].capitalize()}\n\n{msg['content']}\n\n"

    # Write output
    if output:
        Path(output).write_text(output_text)
        click.echo(f"Session exported to {output}")
    else:
        click.echo(output_text)
