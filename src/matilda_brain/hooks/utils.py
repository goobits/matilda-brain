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

import asyncio
import logging
from rich.logging import RichHandler

import matilda_brain
from matilda_brain.config.manager import ConfigManager

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
            from matilda_brain.utils.smart_suggestions import suggest_alias_fixes

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

    from matilda_brain.tools.builtins import TOOL_CATEGORIES

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
        from matilda_brain.tools import get_tool, list_tools

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

