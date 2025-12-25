#!/usr/bin/env python3
"""Business logic hooks for the TTT CLI."""

import json as json_module
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import rich_click as click
from rich.console import Console

import ttt
from ttt.config.manager import ConfigManager
from ttt.core.api import ask as ttt_ask
from ttt.core.api import stream as ttt_stream
from ttt.session.manager import ChatSessionManager

# Initialize console
console = Console()


# Import helper functions we'll need


def is_verbose_mode() -> bool:
    """Check if verbose mode is enabled via environment variables or click context."""
    # Check environment variables first
    if os.environ.get("TTT_VERBOSE", "").lower() == "true" or os.environ.get("TTT_DEBUG", "").lower() == "true":
        return True

    # Try to get debug flag from click context if available
    try:
        import click

        ctx = click.get_current_context(silent=True)
        if ctx and hasattr(ctx, "obj") and ctx.obj and ctx.obj.get("debug"):
            return True
    except (RuntimeError, AttributeError):
        pass

    return False


def setup_logging_level(verbose: bool = False, debug: bool = False, json_output: bool = False) -> None:
    """Setup logging level based on verbosity flags."""
    import asyncio
    import logging

    from rich.logging import RichHandler

    # Set environment variables for verbosity to be used by other parts of the system
    if verbose:
        os.environ["TTT_VERBOSE"] = "true"
    if debug:
        os.environ["TTT_DEBUG"] = "true"
    if json_output:
        os.environ["TTT_JSON_MODE"] = "true"

    if json_output:
        level = logging.WARNING
        logging.getLogger().handlers = []
        logging.getLogger().setLevel(level)
    elif debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    if not json_output and not logging.getLogger().handlers:
        console = Console()
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=console, rich_tracebacks=True)],
        )
    elif not json_output:
        logging.getLogger().setLevel(level)

    if not debug:
        logging.getLogger("litellm").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.CRITICAL)

        def custom_exception_handler(loop: Any, context: Dict[str, Any]) -> None:
            exception = context.get("exception")
            if exception:
                if "Task was destroyed but it is pending" in str(exception):
                    return
                if verbose or debug:
                    loop.default_exception_handler(context)

        try:
            loop = asyncio.get_running_loop()
            loop.set_exception_handler(custom_exception_handler)
        except RuntimeError:
            pass


def resolve_model_alias(model: str) -> str:
    """Resolve model alias to full model name.

    Converts model aliases (prefixed with @) to their full model names
    using the configuration system. Also handles automatic routing to
    OpenRouter when only that API key is available.

    Args:
        model: The model name or alias to resolve

    Returns:
        The resolved full model name, or the original if no alias found

    Examples:
        >>> resolve_model_alias("@fast")
        "openrouter/google/gemini-1.5-flash"
        >>> resolve_model_alias("gpt-4")
        "gpt-4"
    """
    if model and model.startswith("@"):
        alias = model[1:]
        try:
            config_manager = ConfigManager()
            merged_config = config_manager.get_merged_config()
            aliases = merged_config.get("models", {}).get("aliases", {})
            if alias in aliases:
                return str(aliases[alias])

            available_models = merged_config.get("models", {}).get("available", {})
            for model_name, model_info in available_models.items():
                if isinstance(model_info, dict):
                    model_aliases = model_info.get("aliases", [])
                    if alias in model_aliases:
                        return str(model_name)

            # Use smart suggestions for unknown aliases
            from ttt.utils.smart_suggestions import suggest_alias_fixes

            console.print(f"[red]Error: Unknown model alias '@{alias}'[/red]")

            suggestions = suggest_alias_fixes(alias, limit=3)
            if suggestions:
                console.print("\n[cyan]💡 Did you mean:[/cyan]")
                for suggestion in suggestions:
                    status = "[green]✓[/green]" if suggestion["available"] else "[red]✗[/red]"
                    console.print(f"   {status} [bold]{suggestion['alias']}[/bold]  {suggestion['description']}")
                console.print()

            # Show some available aliases as fallback
            console.print("[dim]Popular aliases:[/dim]")
            popular_aliases = ["fast", "best", "claude", "gpt4", "gpt3", "local"]
            available_popular = [a for a in popular_aliases if a in aliases]
            if available_popular:
                for available_alias in available_popular[:5]:
                    console.print(f"  @{available_alias}")
            else:
                # Fallback to first few aliases
                sorted_aliases = sorted(aliases.keys())
                for available_alias in sorted_aliases[:5]:
                    console.print(f"  @{available_alias}")

            console.print("\nTip: Use [green]ttt models[/green] to see all available models")

            # Exit with error instead of proceeding
            import sys

            sys.exit(1)
        except (KeyError, ValueError, TypeError) as e:
            if is_verbose_mode():
                console.print(f"[yellow]Warning: Could not resolve model alias: {e}[/yellow]")
            return alias

    if model and not model.startswith("openrouter/"):
        has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
        has_google = bool(os.getenv("GOOGLE_API_KEY"))

        if has_openrouter and not (has_openai or has_anthropic or has_google):
            openrouter_mappings = {
                "gpt-4o": "openrouter/openai/gpt-4o",
                "gpt-4o-mini": "openrouter/openai/gpt-4o-mini",
                "gpt-4": "openrouter/openai/gpt-4",
                "gpt-3.5-turbo": "openrouter/openai/gpt-3.5-turbo",
                "claude-3-5-sonnet-20241022": ("openrouter/anthropic/claude-3-5-sonnet-20241022"),
                "claude-3-5-haiku-20241022": ("openrouter/anthropic/claude-3-5-haiku-20241022"),
                "gemini-1.5-pro": "openrouter/google/gemini-1.5-pro",
                "gemini-1.5-flash": "openrouter/google/gemini-1.5-flash",
            }

            if model in openrouter_mappings:
                if is_verbose_mode():
                    console.print(f"[dim]Routing {model} through OpenRouter...[/dim]")
                return openrouter_mappings[model]

    return model


def parse_tools_arg(tools: Optional[str]) -> Optional[str]:
    """Parse tools argument and expand categories.

    Processes the tools command-line argument, expanding category names
    into their constituent tool lists. For example, "web" might expand
    to "web_search,http_request".

    Args:
        tools: Comma-separated string of tool names and categories

    Returns:
        Expanded comma-separated string of individual tool names,
        or None if no tools specified

    Examples:
        >>> parse_tools_arg("web,file")
        "web_search,http_request,read_file,write_file"
        >>> parse_tools_arg("")
        "all"
    """
    if tools is None:
        return None

    if tools == "":
        return "all"

    from ttt.tools.builtins import TOOL_CATEGORIES

    expanded_tools = []
    for item in tools.split(","):
        item = item.strip()
        if item in TOOL_CATEGORIES:
            category_tools = TOOL_CATEGORIES[item]
            expanded_tools.extend(category_tools)
        else:
            expanded_tools.append(item)

    return ",".join(expanded_tools) if expanded_tools else tools


def resolve_tools(tool_specs: List[str]) -> List[Any]:
    """Resolve tool specifications to actual tool functions.

    Takes a list of tool specifications (names or category:name pairs)
    and returns the corresponding tool function objects. Handles both
    simple tool names and category-scoped lookups.

    Args:
        tool_specs: List of tool specifications to resolve

    Returns:
        List of tool function objects that were successfully resolved

    Examples:
        >>> resolve_tools(["web_search", "file:read_file"])
        [<function web_search>, <function read_file>]
    """
    tools: List[Any] = []

    try:
        from ttt.tools import get_tool, list_tools

        for spec in tool_specs:
            if ":" in spec:
                category, tool_name = spec.split(":", 1)
                tool_list = list_tools(category=category)
                found_tool = None
                for tool_def in tool_list:
                    if tool_def.name == tool_name:
                        found_tool = tool_def.function
                        break
                if found_tool:
                    tools.append(found_tool)
                else:
                    if is_verbose_mode():
                        console.print(f"[yellow]Warning: Tool {tool_name} not found in category {category}[/yellow]")
            else:
                found_tool_def = get_tool(spec)
                if found_tool_def:
                    tools.append(found_tool_def.function)
                else:
                    if is_verbose_mode():
                        console.print(f"[yellow]Warning: Tool {spec} not found[/yellow]")
    except (ImportError, AttributeError, ValueError) as e:
        console.print(f"[red]Error resolving tools: {e}[/red]")

    return tools


def apply_coding_optimization(kwargs: Dict[str, Any]) -> None:
    """Apply optimizations for coding requests.

    Configures request parameters with sensible defaults for coding tasks:
    - Uses a coding-optimized model if none specified
    - Sets low temperature for more deterministic output
    - Adds system prompt with coding best practices

    Args:
        kwargs: Request parameters dictionary to modify in-place

    Note:
        Modifies the kwargs dictionary directly rather than returning a new one.
    """
    if "model" not in kwargs:
        default_coding_model = os.getenv("TTT_CODING_MODEL", "@coding")
        kwargs["model"] = resolve_model_alias(default_coding_model)

    if "temperature" not in kwargs:
        kwargs["temperature"] = 0.1

    if "system" not in kwargs:
        kwargs["system"] = (
            "You are an expert programmer. Provide clean, well-documented code "
            "with clear explanations. Follow best practices and consider edge cases."
        )


# Main hook functions


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
        from ttt.config.schema import get_config
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
        # Import exception types for better error handling
        from ttt.core.exceptions import (
            APIKeyError,
            BackendConnectionError,
            BackendTimeoutError,
            ModelNotFoundError,
            RateLimitError,
            QuotaExceededError,
        )
        from ttt.utils.smart_suggestions import (
            suggest_model_alternatives,
            suggest_provider_alternatives,
            suggest_troubleshooting_steps,
        )

        if json:
            # For JSON mode, return structured error
            error_output = {
                "error": str(e),
                "error_type": e.__class__.__name__,
                "model": api_params.get("model"),
                "parameters": api_params,
            }
            click.echo(json_module.dumps(error_output, indent=2), err=True)
        else:
            # Format error messages with smart suggestions
            debug_mode = kwargs.get("debug", False) or os.getenv("TTT_DEBUG", "").lower() == "true"

            if isinstance(e, APIKeyError):
                click.echo(f"❌ API key error: {e.message}", err=True)
                # Suggest provider alternatives
                provider_suggestions = suggest_provider_alternatives(str(e), api_params.get("model"))
                if provider_suggestions:
                    click.echo("\n[cyan]💡 Try these alternatives:[/cyan]", err=True)
                    for suggestion in provider_suggestions[:3]:
                        click.echo(f"   • [bold]{suggestion['provider']}[/bold]: {suggestion['description']}", err=True)
                        click.echo(f"     Example: {suggestion['example']}", err=True)

            elif isinstance(e, BackendConnectionError):
                # Check for specific patterns in the error message
                error_msg = str(e.details.get("original_error", str(e)))
                if "Model temporarily overloaded" in error_msg or "Service temporarily unavailable" in error_msg:
                    click.echo(f"⚠️  {error_msg}", err=True)
                else:
                    click.echo(f"❌ Connection error: {e.message}", err=True)

                # Suggest alternatives
                provider_suggestions = suggest_provider_alternatives(error_msg, api_params.get("model"))
                if provider_suggestions:
                    click.echo("\n[cyan]💡 Try these alternatives:[/cyan]", err=True)
                    for suggestion in provider_suggestions[:2]:
                        click.echo(f"   • [bold]{suggestion['provider']}[/bold]: {suggestion['description']}", err=True)
                        click.echo(f"     {suggestion['example']}", err=True)

                # Show troubleshooting steps
                steps = suggest_troubleshooting_steps("connection", error_msg)
                if steps:
                    click.echo("\n[dim]Troubleshooting steps:[/dim]", err=True)
                    for i, step in enumerate(steps[:3], 1):
                        click.echo(f"   {i}. {step}", err=True)

                # Show full traceback in debug mode
                debug_mode_local = kwargs.get("debug", False) or os.getenv("TTT_DEBUG", "").lower() == "true"
                if debug_mode_local:
                    import traceback

                    traceback.print_exc()

            elif isinstance(e, BackendTimeoutError):
                click.echo(f"⏱️  Request timed out after {e.details.get('timeout', 'unknown')}s", err=True)
                steps = suggest_troubleshooting_steps("timeout", str(e))
                if steps:
                    click.echo("\n[dim]Try these solutions:[/dim]", err=True)
                    for i, step in enumerate(steps[:3], 1):
                        click.echo(f"   {i}. {step}", err=True)

            elif isinstance(e, ModelNotFoundError):
                click.echo(f"❌ Model not found: {e.message}", err=True)

                # Suggest model alternatives
                failed_model = e.details.get("model", "")
                if failed_model:
                    model_suggestions = suggest_model_alternatives(failed_model, limit=3)
                    if model_suggestions:
                        click.echo("\n[cyan]💡 Similar models you can try:[/cyan]", err=True)
                        for model_suggestion in model_suggestions:
                            available = model_suggestion.get("available", False)
                            status = "[green]✓[/green]" if available else "[red]✗[/red]"
                            alias = str(model_suggestion.get("alias", ""))
                            description = str(model_suggestion.get("description", ""))
                            click.echo(f"   {status} [bold]{alias}[/bold]  {description}", err=True)

                click.echo("\n[dim]Run 'ttt models' to see all available models[/dim]", err=True)

            elif isinstance(e, RateLimitError):
                click.echo(f"⚠️  Rate limit exceeded: {e.message}", err=True)
                if e.details.get("retry_after"):
                    click.echo(f"  Retry after {e.details['retry_after']} seconds", err=True)

                # Suggest alternatives
                provider_suggestions = suggest_provider_alternatives(str(e))
                if provider_suggestions:
                    click.echo("\n[cyan]💡 Try a different provider:[/cyan]", err=True)
                    for suggestion in provider_suggestions[:2]:
                        if suggestion["provider"] != e.details.get("provider"):
                            click.echo(
                                f"   • [bold]{suggestion['provider']}[/bold]: {suggestion['description']}", err=True
                            )

            elif isinstance(e, QuotaExceededError):
                click.echo(f"❌ Quota exceeded: {e.message}", err=True)
                # Suggest alternatives
                provider_suggestions = suggest_provider_alternatives(str(e))
                if provider_suggestions:
                    click.echo("\n[cyan]💡 Alternative providers:[/cyan]", err=True)
                    for suggestion in provider_suggestions[:2]:
                        click.echo(f"   • [bold]{suggestion['provider']}[/bold]: {suggestion['description']}", err=True)

            else:
                # For other exceptions, show simplified message
                click.echo(f"Error: {str(e)}", err=True)

                # Try to provide generic troubleshooting steps
                steps = suggest_troubleshooting_steps("generic", str(e))
                if steps:
                    click.echo("\n[dim]Troubleshooting steps:[/dim]", err=True)
                    for i, step in enumerate(steps[:3], 1):
                        click.echo(f"   {i}. {step}", err=True)

            # Show full traceback in debug mode
            if debug_mode:
                import traceback

                traceback.print_exc()

        sys.exit(1)


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
    from ttt.session.manager import ChatSessionManager

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
        with ttt.chat(**chat_kwargs) as api_chat_session:
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
                    # Import exception types for better error handling
                    from ttt.core.exceptions import (
                        APIKeyError,
                        BackendConnectionError,
                        BackendTimeoutError,
                        ModelNotFoundError,
                        RateLimitError,
                        QuotaExceededError,
                    )
                    from ttt.utils.smart_suggestions import suggest_provider_alternatives

                    # Format error messages with smart suggestions for chat
                    if isinstance(e, APIKeyError):
                        console.print(f"[red]❌ API key error: {e.message}[/red]")
                        # Suggest alternatives inline
                        provider_suggestions = suggest_provider_alternatives(str(e))
                        if provider_suggestions:
                            console.print("[cyan]💡 Try these alternatives:[/cyan]")
                            for suggestion in provider_suggestions[:2]:
                                console.print(
                                    f"   • [bold]{suggestion['provider']}[/bold]: {suggestion['description']}"
                                )
                    elif isinstance(e, BackendConnectionError):
                        # Check for specific patterns in the error message
                        error_msg = str(e.details.get("original_error", str(e)))
                        if "Model temporarily overloaded" in error_msg:
                            console.print(f"[yellow]⚠️  {error_msg}[/yellow]")
                        elif "Service temporarily unavailable" in error_msg:
                            console.print(f"[yellow]⚠️  {error_msg}[/yellow]")
                        else:
                            console.print(f"[red]❌ Connection error: {e.message}[/red]")

                        # Brief suggestion for chat mode
                        provider_suggestions = suggest_provider_alternatives(error_msg)
                        if provider_suggestions and provider_suggestions[0]["provider"] != "Local (Ollama)":
                            suggestion = provider_suggestions[0]
                            console.print(f"[dim]💡 Try: {suggestion['example']}[/dim]")
                    elif isinstance(e, BackendTimeoutError):
                        console.print(
                            f"[yellow]⏱️  Request timed out after {e.details.get('timeout', 'unknown')}s[/yellow]"
                        )
                    elif isinstance(e, ModelNotFoundError):
                        console.print(f"[red]❌ Model not found: {e.message}[/red]")
                    elif isinstance(e, RateLimitError):
                        console.print(f"[yellow]⚠️  Rate limit exceeded: {e.message}[/yellow]")
                    elif isinstance(e, QuotaExceededError):
                        console.print(f"[red]❌ Quota exceeded: {e.message}[/red]")
                    else:
                        console.print(f"[red]Error: {str(e)}[/red]")

                    # Show full traceback in debug mode
                    debug_mode = kwargs.get("debug", False) or os.getenv("TTT_DEBUG", "").lower() == "true"
                    if debug_mode:
                        import traceback

                        traceback.print_exc()

                    # Exit with error code for non-interactive errors
                    import sys

                    sys.exit(1)

    except (EOFError, KeyboardInterrupt):
        # Normal exit, don't show error
        pass
    except (ValueError, RuntimeError, ConnectionError, ImportError) as e:
        # Only show error if it's not an empty exception
        if str(e).strip():
            console.print(f"[red]Error starting chat session: {e}[/red]")


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
            from ttt.config.schema import get_model_registry
            from ttt.tools import list_tools

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
            from ttt.config.schema import get_model_registry

            model_registry = get_model_registry()
            console.print(f"[cyan]Models:[/cyan] {len(model_registry.models)} available")
            console.print("  Run [green]ttt list models[/green] to see all models\n")

            # Sessions count
            session_manager = ChatSessionManager()
            sessions = session_manager.list_sessions()
            console.print(f"[cyan]Sessions:[/cyan] {len(sessions)} saved")
            console.print("  Run [green]ttt list sessions[/green] to see all sessions\n")

            # Tools count
            from ttt.tools import list_tools

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
        from ttt.tools import list_tools

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
        sys.exit(1)

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
            sys.exit(1)
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
    from ttt.tools import list_tools

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


def show_models_list(json_output: bool = False) -> None:
    """Show list of available models.

    Displays all configured AI models with their metadata including provider,
    speed, quality ratings, and context limits. Supports both rich table
    and JSON output formats.

    Args:
        json_output: If True, outputs JSON format; otherwise shows rich table

    Example:
        >>> show_models_list(json_output=True)
        [{"name": "gpt-4", "provider": "openai", ...}]
    """
    from ttt.config.schema import get_model_registry

    try:
        model_registry = get_model_registry()
        model_names = model_registry.list_models()
        models = []
        for name in model_names:
            model = model_registry.get_model(name)
            if model is not None:
                models.append(model)

        if json_output:
            models_data = []
            for model in models:
                model_data = {
                    "name": model.name,
                    "provider": model.provider,
                    "provider_name": model.provider_name,
                    "context_length": model.context_length,
                    "cost_per_token": model.cost_per_token,
                    "speed": model.speed,
                    "quality": model.quality,
                    "aliases": model.aliases,
                }
                models_data.append(model_data)
            click.echo(json_module.dumps(models_data))
        else:
            from rich.table import Table

            table = Table(title="Available Models")
            table.add_column("Model Name", style="cyan")
            table.add_column("Provider", style="magenta")
            table.add_column("Speed", style="green")
            table.add_column("Quality", style="yellow")
            table.add_column("Context", style="blue")

            for model in models:
                context_str = f"{model.context_length:,}" if model.context_length else "N/A"
                table.add_row(
                    model.name,
                    model.provider,
                    model.speed,
                    model.quality,
                    context_str,
                )

            console.print(table)
    except (ImportError, ValueError, AttributeError) as e:
        if json_output:
            error_output = {"error": str(e)}
            click.echo(json_module.dumps(error_output))
        else:
            console.print(f"[red]Error listing models: {e}[/red]")


def show_model_info(model_name: str, json_output: bool = False) -> None:
    """Show detailed information about a specific model.

    Displays comprehensive details about a single AI model including
    capabilities, pricing, context limits, and available aliases.

    Args:
        model_name: Name or alias of the model to show info for
        json_output: If True, outputs JSON format; otherwise shows formatted text

    Raises:
        ValueError: If the specified model is not found in the registry

    Example:
        >>> show_model_info("gpt-4", json_output=False)
        Model Information: gpt-4
        Provider: openai
        ...
    """
    from ttt.config.schema import get_model_registry

    try:
        model_registry = get_model_registry()
        model = model_registry.get_model(model_name)

        if not model:
            raise ValueError(f"Model '{model_name}' not found")

        if json_output:
            model_data = {
                "name": model.name,
                "provider": model.provider,
                "provider_name": model.provider_name,
                "context_length": model.context_length,
                "cost_per_token": model.cost_per_token,
                "speed": model.speed,
                "quality": model.quality,
                "aliases": model.aliases,
                "capabilities": model.capabilities,
            }
            click.echo(json_module.dumps(model_data))
        else:
            console.print(f"\n[bold]Model Information: {model.name}[/bold]")
            console.print(f"Provider: {model.provider}")
            console.print(f"Provider Name: {model.provider_name}")
            console.print(f"Speed: {model.speed}")
            console.print(f"Quality: {model.quality}")

            if model.context_length:
                console.print(f"Context Length: {model.context_length:,} tokens")

            if model.cost_per_token:
                console.print(f"Cost per Token: ${model.cost_per_token:.6f}")

            if model.aliases:
                console.print(f"Aliases: {', '.join(model.aliases)}")

            if model.capabilities:
                console.print(f"Capabilities: {', '.join(model.capabilities)}")
    except (ValueError, KeyError, AttributeError) as e:
        if json_output:
            error_output = {"error": str(e)}
            click.echo(json_module.dumps(error_output))
        else:
            console.print(f"[red]Error getting model info: {e}[/red]")


def show_backend_status(json_output: bool = False) -> None:
    """Show backend status.

    Checks connectivity and availability of all configured backends
    (local Ollama and cloud providers). Shows API key status and
    model counts where available.

    Args:
        json_output: If True, outputs JSON format; otherwise shows formatted status

    Example:
        >>> show_backend_status(json_output=False)
        TTT System Status
        ✅ Local Backend (Ollama): Available
           URL: http://localhost:11434
           Models: 5
    """
    status_data: Dict[str, Any] = {"backends": {}}

    # Check local backend
    try:
        import ttt.backends.local as local_module

        local = local_module.LocalBackend()
        local_status = {
            "available": local.is_available,
            "type": "local",
            "url": local.base_url,
        }
        if local_status["available"]:
            try:
                models = local.list_models()
                local_status["models"] = len(models)
            except (ConnectionError, TimeoutError, ValueError):
                local_status["models"] = 0
        status_data["backends"]["local"] = local_status
    except (ImportError, AttributeError) as e:
        status_data["backends"]["local"] = {
            "available": False,
            "error": str(e),
        }

    # Check cloud backend
    try:
        # Check API keys
        api_keys = {
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "google": bool(os.getenv("GOOGLE_API_KEY")),
        }

        cloud_status = {
            "available": any(api_keys.values()),
            "type": "cloud",
            "api_keys": api_keys,
        }
        status_data["backends"]["cloud"] = cloud_status
    except (ImportError, AttributeError, ValueError) as e:
        status_data["backends"]["cloud"] = {
            "available": False,
            "error": str(e),
        }

    # Add overall status
    status_data["healthy"] = any(backend.get("available", False) for backend in status_data["backends"].values())

    if json_output:
        click.echo(json_module.dumps(status_data))
    else:
        console.print("\n[bold]TTT System Status[/bold]\n")

        # Local backend
        local_status = status_data["backends"]["local"]
        if local_status["available"]:
            console.print("✅ Local Backend (Ollama): [green]Available[/green]")
            console.print(f"   URL: {local_status['url']}")
            console.print(f"   Models: {local_status.get('models', 0)}")
        else:
            console.print("❌ Local Backend (Ollama): [red]Not Available[/red]")
            if "error" in local_status:
                console.print(f"   Error: {local_status['error']}")

        console.print()

        # Cloud backend
        cloud_status = status_data["backends"]["cloud"]
        if cloud_status["available"]:
            console.print("✅ Cloud Backend: [green]Available[/green]")
            console.print("   API Keys:")
            for provider, has_key in cloud_status["api_keys"].items():
                status = "[green]✓[/green]" if has_key else "[red]✗[/red]"
                console.print(f"     {status} {provider}")
        else:
            console.print("❌ Cloud Backend: [red]Not Available[/red]")
            if "error" in cloud_status:
                console.print(f"   Error: {cloud_status['error']}")

        console.print()

        # Overall status
        if status_data["healthy"]:
            console.print("🎉 [bold green]System is ready to use![/bold green]")
        else:
            console.print(
                "⚠️  [bold yellow]No backends available. Please configure API keys or install Ollama.[/bold yellow]"
            )


# Add hook functions for missing commands that need to be added to CLI
def on_status(command_name: str, json: bool, **kwargs) -> None:
    """Hook for 'status' command.

    Shows the overall status of TTT backends and connectivity.

    Args:
        json: If True, outputs JSON format; otherwise shows formatted status
    """
    show_backend_status(json_output=json)


def on_models(command_name: str, json: bool, **kwargs) -> None:
    """Hook for 'models' command.

    Lists all available AI models with their details.

    Args:
        json: If True, outputs JSON format; otherwise shows rich table
    """
    show_models_list(json_output=json)


def on_info(command_name: str, model: Optional[str] = None, json: bool = False, **kwargs) -> None:
    """Hook for 'info' command.

    Shows detailed information about a specific AI model.
    If no model is specified, shows the list of available models.

    Args:
        model: Name or alias of the model to show information for
        json: If True, outputs JSON format; otherwise shows formatted info
    """
    if model is None:
        # No model specified, show available models
        on_models(command_name="models", json=json)
    else:
        show_model_info(model, json_output=json)


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
    import json as json_module
    from ttt.stateless import execute_stateless, StatelessRequest

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
            from ttt.tools import list_tools
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
    port: int = 3213,
    **kwargs,
) -> None:
    """Hook for 'serve' command.

    Starts the TTT HTTP server for browser-based clients.
    Exposes TTT functionality over HTTP with CORS support.

    Args:
        host: Host address to bind to (default: 0.0.0.0)
        port: Port to listen on (default: 3213)
    """
    from ttt.server import run_server

    run_server(host=host, port=port)
