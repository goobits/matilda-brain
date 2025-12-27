"""Configuration management for TTT CLI."""

import os
import shutil
from pathlib import Path
from typing import Any, Dict

import yaml
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

console = Console()


class ConfigManager:
    """Manages TTT configuration with read/write capabilities."""

    def __init__(self) -> None:
        """Initialize the config manager."""
        self.user_config_path = Path.home() / ".config" / "brain" / "config.yaml"

        # Try multiple locations for default config
        possible_config_paths = [
            Path(__file__).parent / "defaults.yaml",  # Installed in ttt package (preferred)
            Path(__file__).parent / "defaults.yaml",  # Same directory
            Path(__file__).parent.parent / "config.yaml",  # Development fallback
        ]

        self.default_config_path = None
        for path in possible_config_paths:
            if path.exists():
                self.default_config_path = path
                break

        # If no config found, use empty dict
        if self.default_config_path is None:
            # Only show warning in verbose mode and not in JSON mode
            import os

            is_json_mode = os.environ.get("TTT_JSON_MODE", "").lower() == "true"
            is_verbose = (
                os.environ.get("TTT_VERBOSE", "").lower() == "true" or os.environ.get("TTT_DEBUG", "").lower() == "true"
            )

            # Try to get debug flag from click context if available
            if not is_verbose:
                try:
                    import click

                    ctx = click.get_current_context(silent=True)
                    if ctx and hasattr(ctx, "obj") and ctx.obj and ctx.obj.get("debug"):
                        is_verbose = True
                except (RuntimeError, AttributeError):
                    pass

            if not is_json_mode and is_verbose:
                console.print("[yellow]Warning: Default config.yaml not found, using minimal defaults[/yellow]")

        # Ensure user config directory exists
        self.user_config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load API keys from config into environment variables if not already set
        self._load_api_keys_from_config()

    def _load_api_keys_from_config(self) -> None:
        """Load API keys from config file into environment variables if not already set."""
        try:
            user_config = self.get_user_config()
            api_keys = user_config.get("api_keys", {})

            for key, value in api_keys.items():
                env_key = key.upper()
                if not os.environ.get(env_key):
                    os.environ[env_key] = value
        except (OSError, IOError, yaml.YAMLError, KeyError, ValueError, TypeError):
            # Silently fail if config loading fails during initialization
            pass

    def get_user_config(self) -> Dict[str, Any]:
        """Load user configuration if it exists."""
        if self.user_config_path.exists():
            try:
                with open(self.user_config_path) as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                console.print(f"[red]Error loading user config: {e}[/red]")
                return {}
        return {}

    def get_default_config(self) -> Dict[str, Any]:
        """Load default configuration."""
        if self.default_config_path and self.default_config_path.exists():
            try:
                with open(self.default_config_path) as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                console.print(f"[red]Error loading default config: {e}[/red]")
                return self._get_minimal_defaults()
        return self._get_minimal_defaults()

    def _get_minimal_defaults(self) -> Dict[str, Any]:
        """Provide minimal default configuration when config.yaml is not available."""
        return {
            "models": {
                "default": "openrouter/google/gemini-flash-1.5",
                "aliases": {
                    "fast": "openrouter/openai/gpt-3.5-turbo",
                    "best": "openrouter/openai/gpt-4",
                    "coding": "openrouter/anthropic/claude-3-sonnet-20240229",
                    "local": "llama2",
                    "claude": "openrouter/anthropic/claude-3-sonnet-20240229",
                    "gpt4": "openrouter/openai/gpt-4",
                    "gpt3": "openrouter/openai/gpt-3.5-turbo",
                    "gemini": "openrouter/google/gemini-pro",
                    "mixtral": "openrouter/mistralai/mixtral-8x7b-instruct",
                    "flash": "openrouter/google/gemini-2.5-flash",
                },
            },
            "backends": {"default": "cloud"},
        }

    def get_merged_config(self) -> Dict[str, Any]:
        """Get configuration with user settings overriding defaults."""
        default_config = self.get_default_config()
        user_config = self.get_user_config()

        # Deep merge configs
        def deep_merge(base: Dict, override: Dict) -> Dict:
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        return deep_merge(default_config, user_config)

    def display_config(self) -> None:
        """Display current configuration in a nice format."""
        config = self.get_merged_config()
        user_config = self.get_user_config()

        console.print("[bold blue]Current Configuration[/bold blue]")
        console.print()

        # Basic settings
        console.print("[bold green]Basic Settings:[/bold green]")

        # Default model
        default_model = config.get("models", {}).get("default", "Not set")
        is_user_set = "models" in user_config and "default" in user_config.get("models", {})
        console.print(
            f"  Default Model: {default_model} {'[dim](user)[/dim]' if is_user_set else '[dim](default)[/dim]'}"
        )

        # Default backend
        default_backend = config.get("backends", {}).get("default", "Not set")
        is_user_set = "backends" in user_config and "default" in user_config.get("backends", {})
        console.print(
            f"  Default Backend: {default_backend} {'[dim](user)[/dim]' if is_user_set else '[dim](default)[/dim]'}"
        )

        console.print()

        # Model aliases
        console.print("[bold green]Model Aliases:[/bold green]")
        aliases = config.get("models", {}).get("aliases", {})
        user_aliases = user_config.get("models", {}).get("aliases", {})

        # Combine all aliases
        all_aliases = {}
        for alias, model in aliases.items():
            all_aliases[alias] = (model, False)  # False = default
        for alias, model in user_aliases.items():
            all_aliases[alias] = (model, True)  # True = user

        # Display aliases in a table
        if all_aliases:
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Alias", style="cyan")
            table.add_column("Model", style="yellow")
            table.add_column("Source", style="dim")

            for alias, (model, is_user) in sorted(all_aliases.items()):
                table.add_row(f"@{alias}", model, "user" if is_user else "default")

            console.print(table)
        else:
            console.print("  No aliases configured")

        console.print()

        # API Keys (show configured status only)
        console.print("[bold green]API Keys:[/bold green]")
        for key_name in [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
            "OPENROUTER_API_KEY",
        ]:
            is_set = bool(os.getenv(key_name))
            console.print(f"  {key_name}: {'[green]Configured[/green]' if is_set else '[red]Not set[/red]'}")

        console.print()
        console.print("[dim]User config location: " + str(self.user_config_path) + "[/dim]")

    def set_value(self, key: str, value: str) -> None:
        """Set a configuration value."""
        user_config = self.get_user_config()

        # Parse the key path (e.g., "models.default" or "alias.work")
        parts = key.split(".")

        # Special handling for API keys - set both config and environment variable
        if key.endswith("_api_key"):
            env_key = key.upper()
            os.environ[env_key] = value
            console.print(f"[green]Set {env_key} environment variable[/green]")

            # Also store in config for persistence
            if "api_keys" not in user_config:
                user_config["api_keys"] = {}
            user_config["api_keys"][key] = value
            self._save_user_config(user_config)
            console.print(f"[green]Saved {key} to config file[/green]")
            return

        # Special handling for aliases
        if parts[0] == "alias" and len(parts) == 2:
            # Setting a model alias
            if "models" not in user_config:
                user_config["models"] = {}
            if "aliases" not in user_config["models"]:
                user_config["models"]["aliases"] = {}

            alias_name = parts[1]
            user_config["models"]["aliases"][alias_name] = value

            # Save config
            self._save_user_config(user_config)
            console.print(f"[green]Set alias @{alias_name} → {value}[/green]")

        else:
            # Regular nested key setting
            current = user_config
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    console.print(
                        f"[red]Error: Cannot set {key} - {'.'.join(parts[: i + 1])} is not a dictionary[/red]"
                    )
                    return
                current = current[part]

            # Set the final value
            old_value = current.get(parts[-1], "[not set]")
            current[parts[-1]] = value

            # Save config
            self._save_user_config(user_config)
            console.print(f"[green]Set {key} = {value}[/green]")
            if old_value != "[not set]":
                console.print(f"[dim]Previous value: {old_value}[/dim]")

    def reset_config(self) -> None:
        """Reset configuration to defaults."""
        if self.user_config_path.exists():
            # Backup current config
            backup_path = self.user_config_path.with_suffix(".yaml.bak")
            shutil.copy(self.user_config_path, backup_path)
            console.print(f"[dim]Backed up current config to {backup_path}[/dim]")

            # Remove user config
            self.user_config_path.unlink()
            console.print("[green]Configuration reset to defaults[/green]")
        else:
            console.print("[yellow]No user configuration to reset[/yellow]")

    def _save_user_config(self, config: Dict[str, Any]) -> None:
        """Save user configuration to file."""
        try:
            with open(self.user_config_path, "w") as f:
                yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
            console.print(f"[dim]Saved to {self.user_config_path}[/dim]")
        except PermissionError:
            console.print(f"[red]Error: Permission denied saving config to {self.user_config_path}[/red]")
        except OSError as e:
            console.print(f"[red]Error: Cannot save config to {self.user_config_path}: {e}[/red]")
        except yaml.YAMLError as e:
            console.print(f"[red]Error: YAML serialization failed: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error saving config: {e}[/red]")

    def show_value(self, key: str) -> None:
        """Show a specific configuration value."""
        config = self.get_merged_config()
        user_config = self.get_user_config()

        # Navigate through the config
        parts = key.split(".")
        current = config
        user_current = user_config

        try:
            for part in parts:
                current = current[part]
                user_current = user_current.get(part, {}) if isinstance(user_current, dict) else {}

            # Check if this value is from user config
            is_user_set = user_current == current if not isinstance(current, dict) else bool(user_current)

            if isinstance(current, dict):
                # Display as YAML
                console.print(f"[bold blue]{key}:[/bold blue]")
                yaml_str = yaml.safe_dump(current, default_flow_style=False, sort_keys=False)
                syntax = Syntax(yaml_str, "yaml", theme="monokai")
                console.print(syntax)
            else:
                console.print(
                    f"[bold blue]{key}:[/bold blue] {current} {'[dim](user)[/dim]' if is_user_set else '[dim](default)[/dim]'}"
                )

        except KeyError:
            console.print(f"[red]Configuration key '{key}' not found[/red]")

            # Suggest similar keys
            all_keys = self._get_all_keys(config)
            similar = [k for k in all_keys if key.lower() in k.lower()]
            if similar:
                console.print("[yellow]Did you mean one of these?[/yellow]")
                for k in similar[:5]:
                    console.print(f"  • {k}")

    def _get_all_keys(self, config: Dict, prefix: str = "") -> list:
        """Get all configuration keys recursively."""
        keys = []
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.append(full_key)
            if isinstance(value, dict):
                keys.extend(self._get_all_keys(value, full_key))
        return keys
