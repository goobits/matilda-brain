"""Canonical configuration management for Matilda Brain."""

from __future__ import annotations

import copy
import logging
import os
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional, Union, cast

import toml
from dotenv import load_dotenv
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from ..core.exceptions import ConfigFileError
from ..core.models import ConfigModel, ModelInfo

console = Console()
logger = logging.getLogger(__name__)

ConfigPath = Union[str, Path]

DEFAULT_ENV_MAPPINGS: Dict[str, str] = {
    "openai_api_key": "OPENAI_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "google_api_key": "GOOGLE_API_KEY",
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "ollama_base_url": "OLLAMA_BASE_URL",
    "default_backend": "AI_DEFAULT_BACKEND",
    "default_model": "AI_DEFAULT_MODEL",
    "timeout": "AI_TIMEOUT",
    "max_retries": "AI_MAX_RETRIES",
    "enable_fallbacks": "AI_ENABLE_FALLBACKS",
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "models": {
        "default": "openrouter/google/gemini-flash-1.5",
        "available": {},
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
    "backends": {
        "default": "cloud",
        "enable_fallbacks": True,
        "fallback_order": ["cloud", "local"],
        "cloud": {"timeout": 30, "max_retries": 3, "retry_delay": 1.0},
        "local": {"base_url": "http://localhost:11434", "timeout": 60, "default_model": "llama2"},
    },
    "tools": {
        "max_file_size": 10_485_760,
        "code_execution_timeout": 30,
        "web_request_timeout": 10,
        "math_max_iterations": 1000,
        "retry": {"max_attempts": 3, "base_delay": 1.0, "max_delay": 60.0, "rate_limit_min_delay": 5.0},
        "executor": {"max_retries": 3, "timeout_seconds": 30.0},
        "policy": {"allow_private_networks": False, "file_roots": [], "require_approval": False},
    },
    "chat": {"default_system_prompt": None, "max_history_length": 100, "auto_save": True},
    "logging": {"level": "INFO", "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"},
    "env_mappings": DEFAULT_ENV_MAPPINGS,
    "constants": {
        "timeouts": {
            "availability_check": 5,
            "model_list": 10,
            "backend_health_check": 3,
            "async_thread_join": 2.0,
            "cache_ttl": 30,
        },
        "file_sizes": {"max_file_size": 10_485_760, "kb_threshold": 1024, "mb_threshold": 1_048_576},
        "tool_bounds": {
            "min_timeout": 1,
            "max_timeout": 30,
            "default_code_timeout": 30,
            "default_web_timeout": 10,
            "math_max_iterations": 1000,
        },
        "urls": {"ollama_default": "http://localhost:11434"},
        "retries": {"default_max_retries": 3, "default_retry_delay": 1.0, "rate_limit_min_delay": 5.0},
    },
}

_config: Optional[ConfigModel] = None
_config_path: Optional[Path] = None
_suppress_warnings = False
_warned_paths: set[Path] = set()


def default_config_path() -> Path:
    """Return the configured shared Matilda TOML path."""
    env_path = os.environ.get("MATILDA_CONFIG")
    return Path(env_path).expanduser() if env_path else Path.home() / ".matilda" / "config.toml"


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge dictionaries without mutating either input."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _is_pipe_mode() -> bool:
    try:
        return not sys.stdin.isatty()
    except (OSError, AttributeError):
        return False


def set_suppress_warnings(suppress: bool) -> None:
    """Control missing-config warnings for machine-readable output."""
    global _suppress_warnings
    _suppress_warnings = suppress


def _reset_dependents() -> None:
    routing_module = sys.modules.get("matilda_brain.core.routing")
    if routing_module is not None:
        reset_router = getattr(routing_module, "reset_router", None)
        if reset_router is not None:
            reset_router()

    schema_module = sys.modules.get("matilda_brain.config.schema")
    if schema_module is not None:
        reset_registry = getattr(schema_module, "reset_model_registry", None)
        if reset_registry is not None:
            reset_registry()


def clear_config_cache() -> None:
    """Invalidate the process-wide model and its configuration dependents."""
    global _config, _config_path
    _config = None
    _config_path = None
    _reset_dependents()


class ConfigManager:
    """Own configuration discovery, precedence, display, and persistence."""

    def __init__(self, config_file: Optional[ConfigPath] = None) -> None:
        self.user_config_path = Path(config_file).expanduser() if config_file else default_config_path()
        self.config_file = self.user_config_path
        self.model_definitions: list[Dict[str, Any]] = []
        self._load_api_keys_from_config()

    @classmethod
    def activate_cli_context(cls, ctx: Any) -> None:
        """Bridge the generated CLI's explicit config path into the library."""
        embedded_manager = getattr(ctx, "config", None) or getattr(ctx, "config_manager", None)
        config_file = getattr(embedded_manager, "config_file", None)
        if config_file is None:
            return

        path = str(Path(config_file).expanduser())
        if os.environ.get("MATILDA_CONFIG") != path:
            os.environ["MATILDA_CONFIG"] = path
            clear_config_cache()

    def _read_full_config(self) -> Dict[str, Any]:
        if self.user_config_path.suffix.lower() != ".toml":
            raise ConfigFileError(
                str(self.user_config_path),
                f"Unsupported config file format: {self.user_config_path.suffix}",
            )
        if not self.user_config_path.exists():
            return {}

        try:
            with self.user_config_path.open("rb") as config_file:
                return cast(Dict[str, Any], tomllib.load(config_file))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigFileError(str(self.user_config_path), f"TOML parsing error: {exc}") from exc
        except OSError as exc:
            raise ConfigFileError(str(self.user_config_path), str(exc)) from exc

    def get_user_config(self, *, require_section: bool = False) -> Dict[str, Any]:
        """Return the Brain section from the shared Matilda configuration."""
        full_config = self._read_full_config()
        brain_config = full_config.get("brain")
        if brain_config is None:
            if require_section and self.user_config_path.exists():
                raise ConfigFileError(str(self.user_config_path), "Missing [brain] section in matilda config")
            return {}
        if not isinstance(brain_config, dict):
            raise ConfigFileError(str(self.user_config_path), "The [brain] section must be a TOML table")
        return copy.deepcopy(brain_config)

    def get_project_config(self) -> Dict[str, Any]:
        """Compatibility name for the unmerged Brain section."""
        try:
            config = self.get_user_config()
        except ConfigFileError as exc:
            self._warn_once(f"Failed to load project config from {self.user_config_path}: {exc}")
            return {}

        if not config and not self.user_config_path.exists():
            self._warn_once(f"Matilda config not found - expected {self.user_config_path}")
        return config

    def _warn_once(self, message: str) -> None:
        json_mode = os.environ.get("TTT_JSON_MODE", "").lower() == "true"
        if _suppress_warnings or json_mode or "--json" in sys.argv or _is_pipe_mode():
            return
        if self.user_config_path not in _warned_paths:
            logger.warning(message)
            _warned_paths.add(self.user_config_path)

    def get_default_config(self) -> Dict[str, Any]:
        return copy.deepcopy(DEFAULT_CONFIG)

    def get_merged_config(self) -> Dict[str, Any]:
        return merge_configs(self.get_default_config(), self.get_user_config())

    def get_config_value(self, path: str, default: Any = None) -> Any:
        value: Any = self.get_merged_config()
        for key in path.split("."):
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def _load_dotenv(self) -> None:
        candidates = [Path(__file__).parent.parent / ".env", Path.cwd() / ".env"]
        candidates.extend(parent / ".env" for parent in [Path.cwd(), *Path.cwd().parents])
        for env_path in dict.fromkeys(candidates):
            if env_path.exists():
                load_dotenv(env_path)
                logger.debug("Loaded environment from %s", env_path)
                return

    def _load_api_keys_from_config(self) -> None:
        try:
            user_config = self.get_user_config()
        except ConfigFileError:
            return

        api_keys = user_config.get("api_keys", {})
        if not isinstance(api_keys, dict):
            return
        for key, value in api_keys.items():
            if not isinstance(value, str):
                continue
            normalized_key = str(key).split(".")[-1].lower()
            env_key = DEFAULT_ENV_MAPPINGS.get(normalized_key, normalized_key.upper())
            os.environ.setdefault(env_key, value)

    def _extract_model_definitions(self, config: Dict[str, Any]) -> None:
        self.model_definitions = []
        models = config.get("models", {})
        if isinstance(models, list):
            self.model_definitions = [dict(model) for model in models if isinstance(model, dict)]
            return
        if not isinstance(models, dict):
            return
        available = models.get("available", {})
        if isinstance(available, dict):
            for name, details in available.items():
                if isinstance(details, dict):
                    self.model_definitions.append({**details, "name": name})

    @staticmethod
    def _convert_env_value(key: str, value: str) -> Any:
        if key in {"timeout", "max_retries"}:
            try:
                return int(value)
            except ValueError:
                logger.warning("Invalid integer value for %s", key)
                return None
        if key == "enable_fallbacks":
            return value.lower() in {"true", "1", "yes", "on"}
        return value

    def load_model(self, *, require_section: bool = False) -> ConfigModel:
        """Build the typed configuration using defaults < file < environment."""
        self._load_dotenv()
        user_config = self.get_user_config(require_section=require_section)
        merged = merge_configs(self.get_default_config(), user_config)
        self._extract_model_definitions(merged)

        sections = {name: merged.get(name) for name in ("models", "backends", "tools", "chat")}
        models: Dict[str, Any] = sections["models"] if isinstance(sections["models"], dict) else {}
        backends: Dict[str, Any] = sections["backends"] if isinstance(sections["backends"], dict) else {}
        tools: Dict[str, Any] = sections["tools"] if isinstance(sections["tools"], dict) else {}
        chat: Dict[str, Any] = sections["chat"] if isinstance(sections["chat"], dict) else {}

        allowed_fields = ConfigModel.model_fields.keys()
        config_data = {key: copy.deepcopy(value) for key, value in merged.items() if key in allowed_fields}
        if not isinstance(config_data.get("models"), dict):
            config_data["models"] = {}

        config_data["backend_config"] = copy.deepcopy(backends)
        config_data["tools_config"] = copy.deepcopy(tools)
        config_data["chat_config"] = copy.deepcopy(chat)
        config_data["model_aliases"] = copy.deepcopy(models.get("aliases", {}))
        config_data["default_backend"] = config_data.get("default_backend") or backends.get("default")
        config_data["default_model"] = config_data.get("default_model") or models.get("default")
        config_data["enable_fallbacks"] = backends.get("enable_fallbacks", config_data.get("enable_fallbacks", True))
        config_data["fallback_order"] = backends.get(
            "fallback_order", config_data.get("fallback_order", ["cloud", "local"])
        )

        env_mappings = merged.get("env_mappings", DEFAULT_ENV_MAPPINGS)
        if not isinstance(env_mappings, dict):
            env_mappings = DEFAULT_ENV_MAPPINGS
        for config_key, env_key in env_mappings.items():
            env_value = os.getenv(str(env_key))
            if env_value is not None and config_key in allowed_fields:
                converted = self._convert_env_value(config_key, env_value)
                if converted is not None:
                    config_data[config_key] = converted

        config = ConfigModel(**config_data)
        if self.model_definitions:
            from .schema import get_model_registry

            registry = get_model_registry()
            for model_data in self.model_definitions:
                try:
                    registry.add_model(ModelInfo(**model_data))
                except (TypeError, ValueError) as exc:
                    logger.warning("Failed to load model definition: %s", exc)
        return config

    @staticmethod
    def _parse_value(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return toml.loads(f"value = {value}")["value"]
        except (toml.TomlDecodeError, KeyError, TypeError):
            return value

    def _write_full_config(self, full_config: Dict[str, Any]) -> None:
        self.user_config_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.user_config_path.name}.",
            suffix=".tmp",
            dir=self.user_config_path.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as config_file:
                config_file.write(toml.dumps(full_config))
                config_file.flush()
                os.fsync(config_file.fileno())
            os.replace(temporary_path, self.user_config_path)
            os.chmod(self.user_config_path, 0o600)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _save_user_config(self, config: Dict[str, Any]) -> None:
        try:
            full_config = self._read_full_config()
            full_config["brain"] = config
            self._write_full_config(full_config)
            clear_config_cache()
            console.print(f"[dim]Saved to {self.user_config_path}[/dim]")
        except (ConfigFileError, OSError, TypeError, ValueError) as exc:
            console.print(f"[red]Error saving config: {exc}[/red]")

    def save_model(self, config: ConfigModel) -> None:
        """Persist a typed configuration without serializing API secrets."""
        config_dict = config.model_dump(
            exclude={
                "openai_api_key",
                "anthropic_api_key",
                "google_api_key",
                "openrouter_api_key",
                "api_keys",
            },
            exclude_none=True,
        )
        try:
            full_config = self._read_full_config()
            full_config["brain"] = config_dict
            self._write_full_config(full_config)
            clear_config_cache()
            logger.info("Saved config to %s", self.user_config_path)
        except (ConfigFileError, OSError, TypeError, ValueError) as exc:
            if isinstance(exc, ConfigFileError):
                raise
            raise ConfigFileError(str(self.user_config_path), f"Failed to save: {exc}") from exc

    def set_value(self, key: str, value: Any) -> None:
        user_config = self.get_user_config()
        parts = key.split(".")

        if key.endswith("_api_key"):
            normalized_key = parts[-1].lower()
            env_key = DEFAULT_ENV_MAPPINGS.get(normalized_key, normalized_key.upper())
            parsed_value = str(value)
            os.environ[env_key] = parsed_value
            api_keys = user_config.setdefault("api_keys", {})
            if not isinstance(api_keys, dict):
                api_keys = {}
                user_config["api_keys"] = api_keys
            api_keys[normalized_key] = parsed_value
            self._save_user_config(user_config)
            console.print(f"[green]Set {env_key} and saved it to config[/green]")
            return

        if parts[0] == "alias" and len(parts) == 2:
            models = user_config.setdefault("models", {})
            if not isinstance(models, dict):
                models = {}
                user_config["models"] = models
            aliases = models.setdefault("aliases", {})
            if not isinstance(aliases, dict):
                aliases = {}
                models["aliases"] = aliases
            aliases[parts[1]] = str(value)
            self._save_user_config(user_config)
            console.print(f"[green]Set alias @{parts[1]} → {value}[/green]")
            return

        current = user_config
        for index, part in enumerate(parts[:-1]):
            nested = current.setdefault(part, {})
            if not isinstance(nested, dict):
                console.print(
                    f"[red]Error: Cannot set {key} - {'.'.join(parts[: index + 1])} is not a dictionary[/red]"
                )
                return
            current = nested

        old_value = current.get(parts[-1], "[not set]")
        current[parts[-1]] = self._parse_value(value)
        self._save_user_config(user_config)
        console.print(f"[green]Set {key} = {value}[/green]")
        if old_value != "[not set]":
            console.print(f"[dim]Previous value: {old_value}[/dim]")

    def reset_config(self) -> None:
        if not self.user_config_path.exists():
            console.print("[yellow]No user configuration to reset[/yellow]")
            return

        backup_path = self.user_config_path.with_suffix(".toml.bak")
        shutil.copy2(self.user_config_path, backup_path)
        os.chmod(backup_path, 0o600)
        self.user_config_path.unlink()
        clear_config_cache()
        console.print(f"[dim]Backed up current config to {backup_path}[/dim]")
        console.print("[green]Configuration reset to defaults[/green]")

    def display_config(self) -> None:
        config = self.get_merged_config()
        user_config = self.get_user_config()
        console.print("[bold blue]Current Configuration[/bold blue]\n")
        console.print("[bold green]Basic Settings:[/bold green]")

        default_model = config.get("models", {}).get("default", "Not set")
        user_model = isinstance(user_config.get("models"), dict) and "default" in user_config["models"]
        console.print(f"  Default Model: {default_model} [dim]({'user' if user_model else 'default'})[/dim]")

        default_backend = config.get("backends", {}).get("default", "Not set")
        user_backend = isinstance(user_config.get("backends"), dict) and "default" in user_config["backends"]
        console.print(f"  Default Backend: {default_backend} [dim]({'user' if user_backend else 'default'})[/dim]\n")

        console.print("[bold green]Model Aliases:[/bold green]")
        aliases = config.get("models", {}).get("aliases", {})
        user_models = user_config.get("models", {}) if isinstance(user_config.get("models"), dict) else {}
        user_aliases = user_models.get("aliases", {}) if isinstance(user_models.get("aliases"), dict) else {}
        if aliases:
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Alias", style="cyan")
            table.add_column("Model", style="yellow")
            table.add_column("Source", style="dim")
            for alias, model in sorted(aliases.items()):
                table.add_row(f"@{alias}", str(model), "user" if alias in user_aliases else "default")
            console.print(table)
        else:
            console.print("  No aliases configured")

        console.print("\n[bold green]API Keys:[/bold green]")
        for env_key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"):
            status = "[green]Configured[/green]" if os.getenv(env_key) else "[red]Not set[/red]"
            console.print(f"  {env_key}: {status}")
        console.print(f"\n[dim]User config location: {self.user_config_path}[/dim]")

    def show_value(self, key: str) -> None:
        config = self.get_merged_config()
        user_config = self.get_user_config()
        current: Any = config
        user_current: Any = user_config
        try:
            for part in key.split("."):
                current = current[part]
                user_current = user_current.get(part, {}) if isinstance(user_current, dict) else {}
        except (KeyError, TypeError):
            console.print(f"[red]Configuration key '{key}' not found[/red]")
            similar = [candidate for candidate in self._get_all_keys(config) if key.lower() in candidate.lower()]
            if similar:
                console.print("[yellow]Did you mean one of these?[/yellow]")
                for candidate in similar[:5]:
                    console.print(f"  • {candidate}")
            return

        is_user_set = user_current == current if not isinstance(current, dict) else bool(user_current)
        if isinstance(current, dict):
            console.print(f"[bold blue]{key}:[/bold blue]")
            console.print(Syntax(toml.dumps(current), "toml", theme="monokai"))
        else:
            source = "user" if is_user_set else "default"
            console.print(f"[bold blue]{key}:[/bold blue] {current} [dim]({source})[/dim]")

    def _get_all_keys(self, config: Dict[str, Any], prefix: str = "") -> list[str]:
        keys: list[str] = []
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.append(full_key)
            if isinstance(value, dict):
                keys.extend(self._get_all_keys(value, full_key))
        return keys


def get_project_config(config_file: Optional[ConfigPath] = None) -> Dict[str, Any]:
    return ConfigManager(config_file).get_project_config()


def get_config_value(path: str, default: Any = None, config_file: Optional[ConfigPath] = None) -> Any:
    return ConfigManager(config_file).get_config_value(path, default)


def load_config(config_file: Optional[ConfigPath] = None) -> ConfigModel:
    manager = ConfigManager(config_file)
    return manager.load_model(require_section=config_file is not None)


def get_config() -> ConfigModel:
    global _config, _config_path
    path = default_config_path()
    if _config is None or _config_path != path:
        _config = ConfigManager(path).load_model()
        _config_path = path
    return _config


def set_config(config: ConfigModel) -> None:
    global _config, _config_path
    _config = config
    _config_path = default_config_path()
    _reset_dependents()


def save_config(config: ConfigModel, config_file: Optional[ConfigPath] = None) -> None:
    ConfigManager(config_file).save_model(config)


def configure(
    *,
    openai_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    google_api_key: Optional[str] = None,
    openrouter_api_key: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
    default_backend: Optional[str] = None,
    default_model: Optional[str] = None,
    timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
    **kwargs: Any,
) -> None:
    updates = {
        key: value
        for key, value in {
            "openai_api_key": openai_api_key,
            "anthropic_api_key": anthropic_api_key,
            "google_api_key": google_api_key,
            "openrouter_api_key": openrouter_api_key,
            "ollama_base_url": ollama_base_url,
            "default_backend": default_backend,
            "default_model": default_model,
            "timeout": timeout,
            "max_retries": max_retries,
        }.items()
        if value is not None
    }
    updates.update(kwargs)
    set_config(ConfigModel(**{**get_config().model_dump(), **updates}))
