"""Provider utilities for API key management and availability checking."""

import os
from typing import Dict, Optional


# Centralized mapping of provider names to environment variable names
PROVIDER_ENV_VARS: Dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
}

# Centralized mapping of config keys to environment variable names
CONFIG_KEY_TO_ENV_VAR: Dict[str, str] = {
    "openai_api_key": "OPENAI_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "google_api_key": "GOOGLE_API_KEY",
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "cerebras_api_key": "CEREBRAS_API_KEY",
}


def get_env_var_for_provider(provider: str) -> Optional[str]:
    """
    Get the environment variable name for a provider's API key.

    Args:
        provider: Provider name (openai, anthropic, google, openrouter)

    Returns:
        Environment variable name or None if provider is unknown
    """
    return PROVIDER_ENV_VARS.get(provider.lower())


def has_api_key(provider: str) -> bool:
    """
    Check if an API key is configured for a provider.

    Args:
        provider: Provider name (openai, anthropic, google, openrouter)

    Returns:
        True if the API key environment variable is set and non-empty
    """
    env_var = get_env_var_for_provider(provider)
    if not env_var:
        return False
    return bool(os.getenv(env_var))


def get_api_key(provider: str) -> Optional[str]:
    """
    Get the API key for a provider.

    Args:
        provider: Provider name (openai, anthropic, google, openrouter)

    Returns:
        The API key value or None if not set
    """
    env_var = get_env_var_for_provider(provider)
    if not env_var:
        return None
    return os.getenv(env_var)


def get_available_providers() -> Dict[str, bool]:
    """
    Get availability status for all known providers.

    Returns:
        Dictionary mapping provider names to their availability status
    """
    return {provider: has_api_key(provider) for provider in PROVIDER_ENV_VARS}


def get_configured_providers() -> list[str]:
    """
    Get a list of providers that have API keys configured.

    Returns:
        List of provider names with configured API keys
    """
    return [provider for provider, available in get_available_providers().items() if available]


def set_api_key_from_config(provider: str, config_value: Optional[str]) -> bool:
    """
    Set environment variable for a provider's API key from config.

    This is useful when loading API keys from configuration files
    and setting them in the environment for libraries like LiteLLM.

    Args:
        provider: Provider name
        config_value: API key value from configuration (may be None)

    Returns:
        True if the environment variable was set, False otherwise
    """
    if not config_value:
        return False

    env_var = get_env_var_for_provider(provider)
    if not env_var:
        return False

    # Only set if not already in environment (env takes precedence)
    existing = os.getenv(env_var)
    if not existing:
        os.environ[env_var] = config_value
        return True

    return False


def configure_api_keys_from_config(config: Dict[str, str]) -> int:
    """
    Configure API keys from a config dictionary.

    Sets environment variables for any API keys found in the config
    that aren't already set in the environment.

    Args:
        config: Configuration dictionary with keys like 'openai_api_key'

    Returns:
        Number of API keys that were configured
    """
    count = 0
    for config_key, env_var in CONFIG_KEY_TO_ENV_VAR.items():
        if config_key in config and config[config_key]:
            # Check if key is present but not the placeholder value
            value = config[config_key]
            if value and value != env_var:  # Avoid setting the env var name as the value
                if not os.getenv(env_var):
                    os.environ[env_var] = value
                    count += 1
    return count
