#!/usr/bin/env python3
"""Hook handlers for TTT CLI."""

import json as json_module
import sys
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console

console = Console()

from .utils import setup_logging_level, resolve_model_alias, parse_tools_arg

def on_stateless(
    command_name: str,
    message: Tuple[str, ...],
    system: Optional[str],
    history: Optional[str],
    tools: Optional[str],
    model: Optional[str],
    temperature: float,
    max_tokens: int,
    **kwargs,
) -> None:
    """Hook for 'stateless' command.

    Execute a stateless AI request without creating any session files.
    Accepts message, system prompt, conversation history, and tools.

    Args:
        command_name: Name of the command (stateless)
        message: Tuple of message arguments to join
        system: System prompt to set context
        history: Path to JSON file containing conversation history
        tools: Comma-separated list of tool names
        model: AI model to use (can be alias like @fast)
        temperature: Sampling temperature for response generation
        max_tokens: Maximum tokens in response
        **kwargs: Additional parameters
    """
    from matilda_brain.stateless import execute_stateless, StatelessRequest

    # Setup logging (JSON mode to avoid noise)
    setup_logging_level(json_output=True)

    # Join message tuple into a single string
    message_text = " ".join(message) if message else None

    # Handle missing message
    if not message_text:
        # Instead of printing error, return Protocol Error
        error = {
            "version": "v1",
            "kind": "error",
            "code": "missing_message",
            "message": "Missing argument 'message'"
        }
        print(json_module.dumps(error))
        sys.exit(1)

    # Resolve model alias if needed
    if model:
        model = resolve_model_alias(model)

    # Load history from JSON file if provided
    history_messages = []
    if history:
        try:
            history_path = Path(history)
            if not history_path.exists():
                # We can't use console.print because we must output valid JSON for the Switchboard
                error = {
                    "version": "v1",
                    "kind": "error", 
                    "code": "history_not_found",
                    "message": f"History file not found: {history}"
                }
                print(json_module.dumps(error))
                sys.exit(1)

            with open(history_path) as f:
                history_data = json_module.load(f)
            
            # Support multiple formats
            if isinstance(history_data, list):
                history_messages = history_data
            elif isinstance(history_data, dict) and "messages" in history_data:
                history_messages = history_data["messages"]
            
        except Exception as e:
            error = {
                "version": "v1",
                "kind": "error",
                "code": "history_error",
                "message": str(e)
            }
            print(json_module.dumps(error))
            sys.exit(1)

    # Parse tools if provided
    tools_list = None
    if tools:
        tools_expanded = parse_tools_arg(tools)
        if tools_expanded and tools_expanded != "all":
            tools_list = tools_expanded.split(",")
        elif tools_expanded == "all":
            from matilda_brain.tools import list_tools
            available_tools = list_tools()
            tools_list = [tool.name for tool in available_tools]

    # Build request
    req = StatelessRequest(
        message=message_text,
        system=system,
        history=history_messages,
        tools=tools_list,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Execute stateless request
    try:
        # Returns JSON string (Matilda Protocol)
        result_json = execute_stateless(req)
        print(result_json)

    except Exception as e:
        error = {
            "version": "v1",
            "kind": "error",
            "code": "execution_failed",
            "message": str(e)
        }
        print(json_module.dumps(error))
        sys.exit(1)



def on_serve(
    command_name: str,
    host: str = "0.0.0.0",
    port: int = 8772,
    **kwargs,
) -> None:
    """Hook for 'serve' command.

    Starts the TTT HTTP server for browser-based clients.
    Exposes TTT functionality over HTTP with CORS support.

    Args:
        host: Host address to bind to (default: 0.0.0.0)
        port: Port to listen on (default: 8772)
    """
    from matilda_brain.server import run_server

    run_server(host=host, port=port)
