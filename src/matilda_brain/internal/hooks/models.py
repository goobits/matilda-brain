#!/usr/bin/env python3
"""Hook handlers for TTT CLI."""

import json as json_module
import os
from typing import Any, Dict, Optional

import rich_click as click
from rich.console import Console

console = Console()


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
    from matilda_brain.config.schema import get_model_registry

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
    from matilda_brain.config.schema import get_model_registry

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
        import matilda_brain.backends.local as local_module

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

