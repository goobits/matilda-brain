#!/usr/bin/env python3
"""Hook handlers for TTT CLI."""

import json as json_module
import sys
from typing import Any, Dict, List, Optional, Tuple

import rich_click as click
from rich.console import Console

console = Console()

from matilda_brain.core.api import ask as ttt_ask
from matilda_brain.core.api import chat as ttt_chat
from matilda_brain.core.api import stream as ttt_stream
from matilda_brain.session.manager import ChatSessionManager
from .error_handlers import handle_error
from .utils import (
    setup_logging_level,
    resolve_model_alias,
    resolve_tools,
)

def on_ask(
    command_name: str,
    prompt: Tuple[str, ...],
    model: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
    tools: bool,
    session: Optional[str],
    system: Optional[str],
    stream: bool,
    json: bool,
    **kwargs,
) -> None:
    """Hook for 'ask' command.

    Handles the main ask command that sends a prompt to an AI model and returns
    the response. Supports various output formats, model selection, tool usage,
    and session management.

    Args:
        prompt: Tuple of prompt arguments to join into query text
        model: AI model to use (can be alias like @fast)
        temperature: Sampling temperature for response generation
        max_tokens: Maximum tokens in response
        tools: Whether to enable tool usage
        session: Session ID for conversation continuity
        system: System prompt to set context
        stream: Whether to stream response in real-time
        json: Whether to output response in JSON format

    Note:
        Handles stdin input, model alias resolution, and various error conditions.
        Exits with status code 1 on errors.
    """
    # Parse provider shortcuts from prompt arguments
    prompt_list = list(prompt) if prompt else []

    # Check if first argument is a provider shortcut
    if prompt_list and prompt_list[0].startswith("@") and not model:
        potential_model = prompt_list[0]
        # Remove the @ prefix to get the alias
        model_alias = potential_model[1:]

        # Resolve the alias and set as model if valid
        resolved_model = resolve_model_alias(f"@{model_alias}")
        # If resolve_model_alias changed it, it's valid
        if resolved_model != f"@{model_alias}":
            model = resolved_model
            prompt_list = prompt_list[1:]  # Remove the @provider from prompt
        # If not a valid alias, leave it as part of the prompt

    # Join remaining prompt tuple into a single string
    prompt_text = " ".join(prompt_list) if prompt_list else None

    # Setup logging
    setup_logging_level(json_output=json)

    # Handle missing prompt
    if prompt_text is None and sys.stdin.isatty():
        click.echo("Error: Missing argument 'prompt'", err=True)
        sys.exit(1)

    # Handle stdin input
    stdin_content = None
    if not sys.stdin.isatty():
        try:
            stdin_content = sys.stdin.read().strip()
        except EOFError:
            stdin_content = ""

    if prompt_text == "-" or (prompt_text is None and stdin_content):
        if not stdin_content:
            click.echo("Error: No input provided", err=True)
            sys.exit(1)

        try:
            json_input = json_module.loads(stdin_content)
            prompt_text = (
                json_input.get("prompt")
                or json_input.get("query")
                or json_input.get("message")
                or json_input.get("text")
                or json_input.get("content")
            )

            if not prompt_text:
                prompt_text = stdin_content
            else:
                if not model and json_input.get("model"):
                    model = json_input.get("model")
                if temperature is None and json_input.get("temperature") is not None:
                    temperature = json_input.get("temperature")
                if not max_tokens and json_input.get("max_tokens"):
                    max_tokens = json_input.get("max_tokens")
        except json_module.JSONDecodeError:
            prompt_text = stdin_content
    elif prompt_text and stdin_content:
        prompt_text = f"{prompt_text}\n\nInput data:\n{stdin_content}"

    elif prompt_text is None:
        click.echo("Error: Missing argument 'prompt'", err=True)
        sys.exit(1)

    # Get configured default model if not specified via CLI
    if not model:
        from matilda_brain.config.schema import get_config
        config = get_config()
        if config.model:
            model = config.model

    # Resolve model alias
    if model:
        model = resolve_model_alias(model)

    # Build request parameters
    api_params: Dict[str, Any] = {}
    if model:
        api_params["model"] = model
    if temperature is not None:
        api_params["temperature"] = temperature
    if max_tokens:
        api_params["max_tokens"] = max_tokens
    if tools:
        api_params["tools"] = None  # Enable all tools
    if session:
        api_params["session_id"] = session
    if system:
        api_params["system"] = system

    try:
        if json:
            # JSON output mode - collect response and format as JSON
            response = ttt_ask(prompt_text, **api_params)
            output = {
                "response": str(response).strip(),
                "model": api_params.get("model"),
                "temperature": api_params.get("temperature"),
                "max_tokens": api_params.get("max_tokens"),
                "tools_enabled": api_params.get("tools") is not None,
                "session_id": api_params.get("session_id"),
                "system": api_params.get("system"),
            }
            click.echo(json_module.dumps(output, indent=2))
        elif stream:
            chunks = list(ttt_stream(prompt_text, **api_params))
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:  # Last chunk
                    click.echo(chunk.rstrip("\n"), nl=False)
                else:
                    click.echo(chunk, nl=False)
            click.echo()  # Always add exactly one newline at the end
        else:
            response = ttt_ask(prompt_text, **api_params)
            click.echo(str(response).strip())
    except Exception as e:
        handle_error(
            error=e,
            api_params=api_params,
            json_mode=json,
            debug=kwargs.get("debug", False),
            context="ask",
        )



def on_chat(
    command_name: str, model: Optional[str], session: Optional[str], tools: bool, **kwargs
) -> None:
    """Hook for 'chat' command.

    Starts an interactive chat session with an AI model. Supports session
    persistence, tool usage, and various chat commands like /clear and /exit.

    Args:
        model: AI model to use for the chat session
        session: Existing session ID to resume, or None for new session
        tools: Whether to enable tool usage in the chat

    Note:
        Creates an interactive loop that continues until user types /exit
        or interrupts with Ctrl+C. Session state is automatically saved.
    """

    # Setup logging
    setup_logging_level()

    # Initialize session manager
    session_manager = ChatSessionManager()

    # Resolve model alias if provided
    if model:
        model = resolve_model_alias(model)

    # Parse tools
    parsed_tools: Optional[List[str]] = None
    if tools:
        parsed_tools = None  # Enable all tools

    # Load or create session
    if session:
        chat_session = session_manager.load_session(session)
        if not chat_session:
            console.print(f"[yellow]Session '{session}' not found. Creating new session.[/yellow]")
            chat_session = session_manager.create_session(model=model, tools=parsed_tools)
            chat_session.id = session
    else:
        chat_session = session_manager.create_session(model=model, tools=parsed_tools)

    # Build kwargs for chat session
    chat_kwargs: Dict[str, Any] = {}
    if chat_session.model:
        chat_kwargs["model"] = chat_session.model
    if chat_session.system_prompt:
        chat_kwargs["system"] = chat_session.system_prompt
    if chat_session.tools:
        chat_kwargs["tools"] = resolve_tools(chat_session.tools)
    chat_kwargs["stream"] = True

    # Create chat session with context from previous messages
    messages: List[Dict[str, str]] = []
    if chat_session.system_prompt:
        messages.append({"role": "system", "content": chat_session.system_prompt})
    for msg in chat_session.messages:
        messages.append({"role": msg.role, "content": msg.content})

    # Start chat loop
    try:
        # Use the chat API
        with ttt_chat(**chat_kwargs) as api_chat_session:
            # Restore message history
            if messages:
                api_chat_session.history = messages

            console.print("[bold blue]AI Chat Session[/bold blue]")
            if chat_session.model:
                console.print(f"Model: {chat_session.model}")
            if chat_session.system_prompt:
                console.print(f"System: {chat_session.system_prompt[:50]}...")
            console.print("Type /exit to quit, /clear to clear history, /help for commands")
            console.print()

            # Show previous messages if any
            if chat_session.messages:
                console.print("[dim]--- Previous conversation ---[/dim]")
                for msg in chat_session.messages[-10:]:  # Show last 10 messages
                    if msg.role == "user":
                        console.print(f"[bold cyan]You:[/bold cyan] {msg.content}")
                    else:
                        console.print(f"[bold green]AI:[/bold green] {msg.content}")
                console.print("[dim]--- Continue conversation ---[/dim]")
                console.print()

            while True:
                try:
                    user_input = click.prompt("You", type=str, prompt_suffix=": ")
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[yellow]Chat session ended.[/yellow]")
                    break

                if not user_input.strip():
                    continue

                # Handle chat commands
                if user_input.startswith("/"):
                    if user_input in ["/exit", "/quit"]:
                        console.print("[yellow]Chat session ended.[/yellow]")
                        break
                    elif user_input == "/clear":
                        chat_session.messages = []
                        session_manager.save_session(chat_session)
                        console.print("[yellow]Chat history cleared.[/yellow]")
                        # Reset chat session messages
                        api_chat_session.history = (
                            [{"role": "system", "content": chat_session.system_prompt}]
                            if chat_session.system_prompt
                            else []
                        )
                        continue
                    elif user_input == "/help":
                        console.print("Commands:")
                        console.print("  /exit, /quit - End the chat session")
                        console.print("  /clear - Clear chat history")
                        console.print("  /help - Show this help message")
                        continue
                    else:
                        console.print(f"[red]Unknown command: {user_input}[/red]")
                        continue

                # Add user message to session
                session_manager.add_message(chat_session, "user", user_input)

                try:
                    # Get AI response
                    response = api_chat_session.ask(user_input)

                    # Display response
                    console.print(f"[bold green]AI:[/bold green] {response}")

                    # Add AI response to session
                    session_manager.add_message(
                        chat_session,
                        "assistant",
                        str(response),
                        model=response.model if hasattr(response, "model") else None,
                    )

                except Exception as e:
                    handle_error(
                        error=e,
                        api_params=chat_kwargs,
                        json_mode=False,
                        debug=kwargs.get("debug", False),
                        context="chat",
                    )

    except (EOFError, KeyboardInterrupt):
        # Normal exit, don't show error
        pass
    except (ValueError, RuntimeError, ConnectionError, ImportError) as e:
        # Only show error if it's not an empty exception
        if str(e).strip():
            console.print(f"[red]Error starting chat session: {e}[/red]")

