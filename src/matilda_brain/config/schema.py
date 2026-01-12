"""Configuration system for the AI library."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import tomllib
import toml
from dotenv import load_dotenv

from ..core.exceptions import ConfigFileError
from ..core.models import ConfigModel, ModelInfo
from ..internal.utils import get_logger

logger = get_logger(__name__)

# Global configuration instance
_config: Optional[ConfigModel] = None
# Cache for project defaults to avoid multiple warnings
_project_defaults_cache: Optional[Dict[str, Any]] = None


def _default_config_path() -> Path:
    env_path = os.environ.get("MATILDA_CONFIG")
    if env_path:
        return Path(env_path)
    return Path.home() / ".matilda" / "config.toml"


def load_project_defaults() -> Dict[str, Any]:
    """
    Load default configuration from the shared TOML config.

    Returns:
        Dictionary containing default configuration values
    """
    global _project_defaults_cache

    # Return cached value if available
    if _project_defaults_cache is not None:
        return _project_defaults_cache

    # Use the centralized config loader to avoid duplicate warnings
    from .loader import get_project_config

    config = get_project_config()
    if config:
        _project_defaults_cache = config
        return config

    # Fallback to minimal defaults if config.toml not found
    # No need to warn again - get_project_config already warned
    # Note: These values should match the defaults in config.toml
    _project_defaults_cache = {
        "models": {"default": "openrouter/google/gemini-flash-1.5", "available": {}},
        "backends": {
            "default": "cloud",
            "cloud": {"timeout": 30, "max_retries": 3, "retry_delay": 1.0},
            "local": {
                "base_url": "http://localhost:11434",  # constants.urls.ollama_default
                "timeout": 60,
                "default_model": "llama2",
            },
        },
        "tools": {
            "max_file_size": 10485760,  # constants.file_sizes.max_file_size (10MB)
            "code_execution_timeout": 30,  # constants.tool_bounds.default_code_timeout
            "web_request_timeout": 10,  # constants.tool_bounds.default_web_timeout
            "math_max_iterations": 1000,  # constants.tool_bounds.math_max_iterations
        },
        "chat": {
            "default_system_prompt": None,
            "max_history_length": 100,
            "auto_save": True,
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "constants": {
            "timeouts": {
                "availability_check": 5,
                "model_list": 10,
                "backend_health_check": 3,
                "async_thread_join": 2.0,
            },
            "file_sizes": {
                "max_file_size": 10485760,
                "kb_threshold": 1024,
                "mb_threshold": 1048576,
            },
            "tool_bounds": {
                "min_timeout": 1,
                "max_timeout": 30,
                "default_code_timeout": 30,
                "default_web_timeout": 10,
                "math_max_iterations": 1000,
            },
            "urls": {
                "ollama_default": "http://localhost:11434",
            },
            "retries": {
                "default_max_retries": 3,
                "default_retry_delay": 1.0,
                "rate_limit_min_delay": 5.0,
            },
        },
    }
    return _project_defaults_cache


def get_config() -> ConfigModel:
    """
    Get the global configuration, loading it if necessary.

    Returns:
        ConfigModel instance with current configuration
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def load_config(config_file: Optional[Union[str, Path]] = None) -> ConfigModel:
    """
    Load configuration from multiple sources with precedence:
    1. Programmatic overrides (highest)
    2. Environment variables
    3. Config file
    4. Defaults (lowest)

    Args:
        config_file: Path to config file. If None, searches standard locations.

    Returns:
        ConfigModel instance with loaded configuration
    """
    # Load .env file if it exists, searching in project directories
    env_paths = [
        Path(__file__).parent.parent / ".env",  # Relative to ttt package (installed location)
        Path.cwd() / ".env",  # Current working directory
    ]

    # Also search up the directory tree from current working directory
    current_path = Path.cwd()
    for parent in [current_path] + list(current_path.parents):
        env_path = parent / ".env"
        if env_path not in env_paths:
            env_paths.append(env_path)

    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug(f"Loaded environment from {env_path}")
            break

    # Load defaults from shared TOML config
    defaults = load_project_defaults()
    config_data = {}
    models_data = []

    # Load from config file if specified or found
    if config_file:
        config_path: Optional[Path] = Path(config_file)
    else:
        config_path = find_config_file()

    if config_path and config_path.exists():
        try:
            with open(config_path, "rb") as f:
                if config_path.suffix.lower() != ".toml":
                    raise ConfigFileError(
                        str(config_path),
                        f"Unsupported config file format: {config_path.suffix}",
                    )
                full_config = tomllib.load(f)
                file_config = full_config.get("brain")
                if file_config is None:
                    raise ConfigFileError(str(config_path), "Missing [brain] section in matilda config")

            if file_config:
                # Extract models separately - the models section has subsections
                if "models" in file_config:
                    models_dict = file_config.pop("models", {})
                    # Handle both formats: models as list or models.available as dict
                    if isinstance(models_dict, list):
                        # Direct list format (as used in tests)
                        models_data.extend(models_dict)
                    elif isinstance(models_dict, dict) and "available" in models_dict:
                        # Dict format with 'available' section
                        available_models = models_dict.get("available", {})
                        # Convert dict format to list format
                        for model_name, model_info in available_models.items():
                            if isinstance(model_info, dict):
                                model_info["name"] = model_name
                                models_data.append(model_info)

                config_data.update(file_config)
                logger.debug(f"Loaded config from {config_path}")
        except tomllib.TOMLDecodeError as e:
            raise ConfigFileError(str(config_path), f"TOML parsing error: {e}") from e
        except Exception as e:
            raise ConfigFileError(str(config_path), str(e)) from e

    # Override with environment variables

    # Get environment variable mappings from defaults
    env_mappings = defaults.get(
        "env_mappings",
        {
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
        },
    )

    for config_key, env_key in env_mappings.items():
        env_value = os.getenv(env_key)
        if env_value is not None:
            # Handle type conversion for non-string values
            if config_key in ["timeout", "max_retries"]:
                try:
                    config_data[config_key] = int(env_value)
                except ValueError:
                    logger.warning(f"Invalid integer value for {env_key}: {env_value}")
            elif config_key == "enable_fallbacks":
                config_data[config_key] = env_value.lower() in (
                    "true",
                    "1",
                    "yes",
                    "on",
                )
            else:
                config_data[config_key] = env_value

    # Merge defaults with loaded config data
    merged_config = {}

    # Deep merge defaults and config_data
    def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    merged_config = deep_merge(defaults, config_data)

    # Populate specific config sections if they exist in defaults
    if "backends" in defaults:
        merged_config["backend_config"] = defaults["backends"]
    if "tools" in defaults:
        merged_config["tools_config"] = defaults["tools"]
    if "chat" in defaults:
        merged_config["chat_config"] = defaults["chat"]
    if "models" in defaults and "aliases" in defaults["models"]:
        merged_config["model_aliases"] = defaults["models"]["aliases"]
    if "backends" in defaults and "enable_fallbacks" in defaults["backends"]:
        merged_config["enable_fallbacks"] = defaults["backends"]["enable_fallbacks"]
    if "backends" in defaults and "fallback_order" in defaults["backends"]:
        merged_config["fallback_order"] = defaults["backends"]["fallback_order"]

    # Create ConfigModel with merged configuration
    config = ConfigModel(**merged_config)

    # Load custom models into registry
    if models_data:
        for model_data in models_data:
            try:
                model = ModelInfo(**model_data)
                model_registry.add_model(model)
                logger.debug(f"Loaded custom model: {model.name}")
            except Exception as e:
                logger.warning(f"Failed to load model definition: {e}")

    return config


def find_config_file() -> Optional[Path]:
    """
    Find configuration file in standard locations.

    Returns:
        Path to config file if found, None otherwise
    """
    config_path = _default_config_path()
    if config_path.exists():
        logger.debug(f"Found config file: {config_path}")
        return config_path
    logger.debug("No config file found")
    return None


def save_config(config: ConfigModel, config_file: Optional[Union[str, Path]] = None) -> None:
    """
    Save configuration to file.

    Args:
        config: ConfigModel instance to save
        config_file: Path to save to. If None, uses default location.
    """
    if config_file:
        config_path = Path(config_file)
    else:
        # Get default save path from project config
        config_path = _default_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert config to dict, excluding sensitive data
    config_dict = config.model_dump(
        exclude={
            "openai_api_key",
            "anthropic_api_key",
            "google_api_key",
            "openrouter_api_key",
        }
    )

    try:
        if config_path.exists():
            with open(config_path, "rb") as f:
                full_config = tomllib.load(f)
        else:
            full_config = {}

        full_config["brain"] = config_dict
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(toml.dumps(full_config))
        logger.info(f"Saved config to {config_path}")
    except Exception as e:
        raise ConfigFileError(str(config_path), f"Failed to save: {e}") from e


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
    """
    Configure the AI library programmatically.

    This function allows you to set configuration options at runtime,
    overriding any file or environment-based configuration.

    Args:
        openai_api_key: OpenAI API key
        anthropic_api_key: Anthropic API key
        google_api_key: Google API key
        openrouter_api_key: OpenRouter API key
        ollama_base_url: Ollama base URL
        default_backend: Default backend to use
        default_model: Default model to use
        timeout: Request timeout in seconds
        max_retries: Maximum number of retries
        **kwargs: Additional configuration options
    """
    global _config

    # Load current config
    current_config = get_config()

    # Build update dict
    updates: Dict[str, Any] = {}

    if openai_api_key is not None:
        updates["openai_api_key"] = openai_api_key
    if anthropic_api_key is not None:
        updates["anthropic_api_key"] = anthropic_api_key
    if google_api_key is not None:
        updates["google_api_key"] = google_api_key
    if openrouter_api_key is not None:
        updates["openrouter_api_key"] = openrouter_api_key
    if ollama_base_url is not None:
        updates["ollama_base_url"] = ollama_base_url
    if default_backend is not None:
        updates["default_backend"] = default_backend
    if default_model is not None:
        updates["default_model"] = default_model
    if timeout is not None:
        updates["timeout"] = timeout
    if max_retries is not None:
        updates["max_retries"] = max_retries

    # Add any additional kwargs
    updates.update(kwargs)

    # Create new config with updates
    config_dict = current_config.model_dump()
    config_dict.update(updates)

    _config = ConfigModel(**config_dict)
    logger.debug("Configuration updated programmatically")


class ModelRegistry:
    """
    Registry for managing model information and aliases.
    """

    def __init__(self) -> None:
        self.models: Dict[str, ModelInfo] = {}
        self.aliases: Dict[str, str] = {}
        self._load_default_models()

    def _load_default_models(self) -> None:
        """Load default model configurations from config."""
        # Load project defaults
        project_defaults = load_project_defaults()
        model_configs = project_defaults.get("models", {}).get("available", {})

        # Load each model from config
        for model_name, model_config in model_configs.items():
            try:
                model_info = ModelInfo(
                    name=model_name,
                    provider=model_config.get("provider", ""),
                    provider_name=model_config.get("provider_name", model_name),
                    aliases=model_config.get("aliases", []),
                    speed=model_config.get("speed", "medium"),
                    quality=model_config.get("quality", "medium"),
                    capabilities=model_config.get("capabilities", []),
                    context_length=model_config.get("context_length"),
                    cost_per_token=model_config.get("cost_per_token"),
                )
                self.add_model(model_info)
                logger.debug(f"Loaded model from config: {model_name}")
            except Exception as e:
                import os

                if os.environ.get("TTT_JSON_MODE", "").lower() != "true":
                    logger.warning(f"Failed to load model {model_name} from config: {e}")

        # If no models loaded from config, use minimal hardcoded defaults
        if not self.models:
            # Check if warnings are suppressed (JSON mode) - double check environment
            import os

            if os.environ.get("TTT_JSON_MODE", "").lower() != "true":
                logger.warning("No models loaded from config, using minimal defaults")
            # Minimal fallback models
            self.add_model(
                ModelInfo(
                    name="gpt-3.5-turbo",
                    provider="openai",
                    provider_name="gpt-3.5-turbo",
                    aliases=["fast", "cheap"],
                    speed="fast",
                    quality="medium",
                    capabilities=["text", "chat"],
                    context_length=4096,
                )
            )
            self.add_model(
                ModelInfo(
                    name="llama2",
                    provider="local",
                    provider_name="llama2",
                    aliases=["local", "private"],
                    speed="medium",
                    quality="medium",
                    capabilities=["text", "chat"],
                    context_length=4096,
                )
            )

    def add_model(self, model: ModelInfo) -> None:
        """Add a model to the registry."""
        self.models[model.name] = model

        # Register aliases
        for alias in model.aliases or []:
            self.aliases[alias] = model.name

    def get_model(self, name_or_alias: str) -> Optional[ModelInfo]:
        """Get model info by name or alias."""
        # Try direct name first
        if name_or_alias in self.models:
            return self.models[name_or_alias]

        # Try alias
        if name_or_alias in self.aliases:
            real_name = self.aliases[name_or_alias]
            return self.models.get(real_name)

        return None

    def resolve_model_name(self, name_or_alias: str) -> str:
        """Resolve an alias to the actual model name."""
        if name_or_alias in self.aliases:
            return self.aliases[name_or_alias]
        return name_or_alias

    def list_models(self, provider: Optional[str] = None) -> List[str]:
        """List available models, optionally filtered by provider."""
        models = []
        for name, model in self.models.items():
            if provider is None or model.provider == provider:
                models.append(name)
        return sorted(models)

    def list_aliases(self) -> Dict[str, str]:
        """List all aliases and their target models."""
        return dict(self.aliases)


# Global model registry - lazy initialization
_model_registry: Optional[ModelRegistry] = None


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two configuration dictionaries, with override taking precedence.

    Args:
        base: Base configuration dictionary
        override: Override configuration dictionary

    Returns:
        Merged configuration dictionary
    """
    import copy

    result = copy.deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value

    return result


def set_config(config: ConfigModel) -> None:
    """
    Set the global configuration.

    Args:
        config: Configuration model to set
    """
    global _config
    _config = config


def get_model_registry() -> ModelRegistry:
    """Get the global model registry, creating it if needed."""
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
    return _model_registry


# Lazy initialization - avoids import-time overhead
class LazyModelRegistry:
    def __getattr__(self, name):
        return getattr(get_model_registry(), name)


model_registry = LazyModelRegistry()
