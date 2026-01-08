#!/usr/bin/env python3
"""Error handling utilities for CLI hooks.

This module provides centralized error display and smart suggestions
for various exception types encountered during CLI operations.
"""

import json as json_module
import os
import traceback
from typing import Any, Dict

import rich_click as click
from rich.console import Console

console = Console()


def display_error_json(
    error: Exception,
    api_params: Dict[str, Any],
) -> None:
    """Display error in JSON format for machine consumption.

    Args:
        error: The exception that occurred
        api_params: API parameters used in the request
    """
    error_output = {
        "error": str(error),
        "error_type": error.__class__.__name__,
        "model": api_params.get("model"),
        "parameters": api_params,
    }
    click.echo(json_module.dumps(error_output, indent=2), err=True)


def display_error_rich(
    error: Exception,
    api_params: Dict[str, Any],
    debug: bool = False,
    context: str = "ask",
) -> None:
    """Display error with rich formatting and smart suggestions.

    Args:
        error: The exception that occurred
        api_params: API parameters used in the request
        debug: Whether to show full traceback
        context: Context of the error ("ask" or "chat")
    """
    # Import exception types for better error handling
    from matilda_brain.core.exceptions import (
        APIKeyError,
        BackendConnectionError,
        BackendTimeoutError,
        ModelNotFoundError,
        RateLimitError,
        QuotaExceededError,
    )
    from matilda_brain.internal.utils.smart_suggestions import (
        suggest_model_alternatives,
        suggest_provider_alternatives,
        suggest_troubleshooting_steps,
    )

    is_chat = context == "chat"
    output_fn = console.print if is_chat else lambda msg, **kw: click.echo(msg, err=True)

    if isinstance(error, APIKeyError):
        output_fn(f"[red]❌ API key error: {error.message}[/red]" if is_chat else f"❌ API key error: {error.message}")
        provider_suggestions = suggest_provider_alternatives(str(error), api_params.get("model"))
        if provider_suggestions:
            output_fn(
                "[cyan]💡 Try these alternatives:[/cyan]" if is_chat else "\n[cyan]💡 Try these alternatives:[/cyan]"
            )
            limit = 2 if is_chat else 3
            for suggestion in provider_suggestions[:limit]:
                output_fn(f"   • [bold]{suggestion['provider']}[/bold]: {suggestion['description']}")
                if not is_chat:
                    output_fn(f"     Example: {suggestion['example']}")

    elif isinstance(error, BackendConnectionError):
        error_msg = str(error.details.get("original_error", str(error)))
        if "Model temporarily overloaded" in error_msg or "Service temporarily unavailable" in error_msg:
            output_fn(f"[yellow]⚠️  {error_msg}[/yellow]" if is_chat else f"⚠️  {error_msg}")
        else:
            output_fn(
                f"[red]❌ Connection error: {error.message}[/red]"
                if is_chat
                else f"❌ Connection error: {error.message}"
            )

        provider_suggestions = suggest_provider_alternatives(error_msg, api_params.get("model"))
        if provider_suggestions:
            if is_chat and provider_suggestions[0]["provider"] != "Local (Ollama)":
                suggestion = provider_suggestions[0]
                output_fn(f"[dim]💡 Try: {suggestion['example']}[/dim]")
            elif not is_chat:
                output_fn("\n[cyan]💡 Try these alternatives:[/cyan]")
                for suggestion in provider_suggestions[:2]:
                    output_fn(f"   • [bold]{suggestion['provider']}[/bold]: {suggestion['description']}")
                    output_fn(f"     {suggestion['example']}")

        if not is_chat:
            steps = suggest_troubleshooting_steps("connection", error_msg)
            if steps:
                output_fn("\n[dim]Troubleshooting steps:[/dim]")
                for i, step in enumerate(steps[:3], 1):
                    output_fn(f"   {i}. {step}")

    elif isinstance(error, BackendTimeoutError):
        timeout_val = error.details.get("timeout", "unknown")
        output_fn(
            f"[yellow]⏱️  Request timed out after {timeout_val}s[/yellow]"
            if is_chat
            else f"⏱️  Request timed out after {timeout_val}s"
        )
        if not is_chat:
            steps = suggest_troubleshooting_steps("timeout", str(error))
            if steps:
                output_fn("\n[dim]Try these solutions:[/dim]")
                for i, step in enumerate(steps[:3], 1):
                    output_fn(f"   {i}. {step}")

    elif isinstance(error, ModelNotFoundError):
        output_fn(
            f"[red]❌ Model not found: {error.message}[/red]" if is_chat else f"❌ Model not found: {error.message}"
        )

        if not is_chat:
            failed_model = error.details.get("model", "")
            if failed_model:
                model_suggestions = suggest_model_alternatives(failed_model, limit=3)
                if model_suggestions:
                    output_fn("\n[cyan]💡 Similar models you can try:[/cyan]")
                    for model_suggestion in model_suggestions:
                        available = model_suggestion.get("available", False)
                        status = "[green]✓[/green]" if available else "[red]✗[/red]"
                        alias = str(model_suggestion.get("alias", ""))
                        description = str(model_suggestion.get("description", ""))
                        output_fn(f"   {status} [bold]{alias}[/bold]  {description}")

            output_fn("\n[dim]Run 'ttt models' to see all available models[/dim]")

    elif isinstance(error, RateLimitError):
        output_fn(
            f"[yellow]⚠️  Rate limit exceeded: {error.message}[/yellow]"
            if is_chat
            else f"⚠️  Rate limit exceeded: {error.message}"
        )
        if error.details.get("retry_after") and not is_chat:
            output_fn(f"  Retry after {error.details['retry_after']} seconds")

        provider_suggestions = suggest_provider_alternatives(str(error))
        if provider_suggestions and not is_chat:
            output_fn("\n[cyan]💡 Try a different provider:[/cyan]")
            for suggestion in provider_suggestions[:2]:
                if suggestion["provider"] != error.details.get("provider"):
                    output_fn(f"   • [bold]{suggestion['provider']}[/bold]: {suggestion['description']}")

    elif isinstance(error, QuotaExceededError):
        output_fn(
            f"[red]❌ Quota exceeded: {error.message}[/red]" if is_chat else f"❌ Quota exceeded: {error.message}"
        )
        provider_suggestions = suggest_provider_alternatives(str(error))
        if provider_suggestions and not is_chat:
            output_fn("\n[cyan]💡 Alternative providers:[/cyan]")
            for suggestion in provider_suggestions[:2]:
                output_fn(f"   • [bold]{suggestion['provider']}[/bold]: {suggestion['description']}")

    else:
        output_fn(f"[red]Error: {str(error)}[/red]" if is_chat else f"Error: {str(error)}")

        if not is_chat:
            steps = suggest_troubleshooting_steps("generic", str(error))
            if steps:
                output_fn("\n[dim]Troubleshooting steps:[/dim]")
                for i, step in enumerate(steps[:3], 1):
                    output_fn(f"   {i}. {step}")

    # Show full traceback in debug mode
    if debug:
        traceback.print_exc()


def handle_error(
    error: Exception,
    api_params: Dict[str, Any],
    json_mode: bool = False,
    debug: bool = False,
    context: str = "ask",
    exit_on_error: bool = True,
) -> None:
    """Handle an error with appropriate output format.

    Args:
        error: The exception that occurred
        api_params: API parameters used in the request
        json_mode: Whether to output in JSON format
        debug: Whether to show full traceback
        context: Context of the error ("ask" or "chat")
        exit_on_error: Whether to exit with status code 1
    """
    debug = debug or os.getenv("TTT_DEBUG", "").lower() == "true"

    if json_mode:
        display_error_json(error, api_params)
    else:
        display_error_rich(error, api_params, debug=debug, context=context)

    if exit_on_error:
        raise error
