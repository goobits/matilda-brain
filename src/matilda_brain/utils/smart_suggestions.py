"""
Smart suggestions for TTT CLI errors and user input.

This module provides intelligent, context-aware suggestions when users encounter
errors such as invalid model aliases, failed model connections, or provider issues.
"""

import difflib
import os
from typing import Dict, List, Optional, Union

from matilda_brain.config.manager import ConfigManager
from matilda_brain.config.schema import get_model_registry


def calculate_similarity(input_str: str, target_str: str) -> float:
    """Calculate similarity between two strings using sequence matching.

    Args:
        input_str: The user's input string
        target_str: The target string to compare against

    Returns:
        Similarity ratio between 0.0 and 1.0, where 1.0 is an exact match
    """
    return difflib.SequenceMatcher(None, input_str.lower(), target_str.lower()).ratio()


def suggest_model_alternatives(failed_model: str, limit: int = 3) -> List[Dict[str, Union[str, float, bool]]]:
    """Suggest alternative models when a model fails or is not found.

    Args:
        failed_model: The model that failed or was not found
        limit: Maximum number of suggestions to return

    Returns:
        List of dictionaries with model alternatives and their descriptions
    """
    suggestions = []

    try:
        config_manager = ConfigManager()
        merged_config = config_manager.get_merged_config()
        aliases = merged_config.get("models", {}).get("aliases", {})

        # Get model registry for additional context
        model_registry = get_model_registry()
        available_models = model_registry.list_models()

        # Check API key availability for context
        api_keys = {
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "google": bool(os.getenv("GOOGLE_API_KEY")),
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        }

        # Suggest similar aliases first
        for alias, model_name in aliases.items():
            similarity = calculate_similarity(failed_model, alias)
            if similarity > 0.4:  # 40% similarity threshold
                provider = _get_provider_from_model(model_name)
                provider_available = _is_provider_available(provider, api_keys)

                description = _get_model_description(alias, model_name, provider_available)
                suggestions.append(
                    {
                        "alias": f"@{alias}",
                        "model": model_name,
                        "description": description,
                        "similarity": similarity,
                        "available": provider_available,
                    }
                )

        # Suggest similar model names
        for model_name in available_models:
            similarity = calculate_similarity(failed_model, model_name)
            if similarity > 0.3:  # Lower threshold for full model names
                provider = _get_provider_from_model(model_name)
                provider_available = _is_provider_available(provider, api_keys)

                # Find aliases for this model
                model_aliases = [alias for alias, model in aliases.items() if model == model_name]

                description = _get_model_description(model_name, model_name, provider_available, model_aliases)
                suggestions.append(
                    {
                        "alias": model_aliases[0] if model_aliases else model_name,
                        "model": model_name,
                        "description": description,
                        "similarity": similarity,
                        "available": provider_available,
                    }
                )

        # Sort by similarity and availability, then limit results
        suggestions.sort(key=lambda x: (x["available"], x["similarity"]), reverse=True)
        return suggestions[:limit]

    except (ImportError, AttributeError, KeyError, TypeError):
        # Fallback to basic suggestions if config loading fails
        return _get_fallback_suggestions()


def suggest_alias_fixes(invalid_alias: str, limit: int = 5) -> List[Dict[str, Union[str, float, bool]]]:
    """Suggest correct aliases for typos like @gpt → @gpt4.

    Args:
        invalid_alias: The invalid alias (without @ prefix)
        limit: Maximum number of suggestions to return

    Returns:
        List of dictionaries with alias suggestions and their descriptions
    """
    suggestions = []

    try:
        config_manager = ConfigManager()
        merged_config = config_manager.get_merged_config()
        aliases = merged_config.get("models", {}).get("aliases", {})

        # Check API key availability
        api_keys = {
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "google": bool(os.getenv("GOOGLE_API_KEY")),
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        }

        # Common typo mappings
        typo_mappings = {
            "gpt": ["gpt4", "gpt3"],
            "claude": ["claude"],
            "gemini": ["gemini", "flash"],
            "fast": ["fast"],
            "best": ["best", "gpt4"],
            "local": ["local"],
            "coding": ["coding", "claude"],
        }

        # First check direct typo mappings
        if invalid_alias in typo_mappings:
            for suggested_alias in typo_mappings[invalid_alias]:
                if suggested_alias in aliases:
                    model_name = aliases[suggested_alias]
                    provider = _get_provider_from_model(model_name)
                    provider_available = _is_provider_available(provider, api_keys)

                    description = _get_model_description(suggested_alias, model_name, provider_available)
                    suggestions.append(
                        {
                            "alias": f"@{suggested_alias}",
                            "model": model_name,
                            "description": description,
                            "similarity": 1.0,  # Perfect match for typo mapping
                            "available": provider_available,
                        }
                    )

        # Then use fuzzy matching on all aliases
        for alias, model_name in aliases.items():
            similarity = calculate_similarity(invalid_alias, alias)
            if similarity > 0.4:  # 40% similarity threshold
                provider = _get_provider_from_model(model_name)
                provider_available = _is_provider_available(provider, api_keys)

                description = _get_model_description(alias, model_name, provider_available)
                suggestions.append(
                    {
                        "alias": f"@{alias}",
                        "model": model_name,
                        "description": description,
                        "similarity": similarity,
                        "available": provider_available,
                    }
                )

        # Remove duplicates and sort by availability and similarity
        unique_suggestions = []
        seen_aliases = set()
        for suggestion in suggestions:
            if suggestion["alias"] not in seen_aliases:
                unique_suggestions.append(suggestion)
                seen_aliases.add(suggestion["alias"])

        unique_suggestions.sort(key=lambda x: (x["available"], x["similarity"]), reverse=True)
        return unique_suggestions[:limit]

    except (ImportError, AttributeError, KeyError, TypeError):
        return _get_fallback_alias_suggestions()


def suggest_provider_alternatives(provider_error: str, failed_model: Optional[str] = None) -> List[Dict[str, str]]:
    """Suggest alternative providers when one is down or unavailable.

    Args:
        provider_error: The error message from the failed provider
        failed_model: The model that failed (optional)

    Returns:
        List of dictionaries with provider alternatives and their descriptions
    """
    suggestions = []

    # Check which providers are available
    api_keys = {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "google": bool(os.getenv("GOOGLE_API_KEY")),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
    }

    # Determine which provider failed
    failed_provider = _detect_failed_provider(provider_error)

    # Suggest OpenRouter as a universal alternative if available
    if failed_provider != "openrouter" and api_keys["openrouter"]:
        suggestions.append(
            {
                "provider": "OpenRouter",
                "description": "Access 100+ models through one API key",
                "example": 'ttt @fast "your question" (uses OpenRouter by default)',
                "setup": "Already configured ✓",
            }
        )

    # Suggest specific alternatives based on the failed provider
    if failed_provider == "openai":
        if api_keys["anthropic"]:
            suggestions.append(
                {
                    "provider": "Anthropic Claude",
                    "description": "Excellent for analysis and reasoning",
                    "example": 'ttt @claude "your question"',
                    "setup": "Already configured ✓",
                }
            )
        if api_keys["google"]:
            suggestions.append(
                {
                    "provider": "Google Gemini",
                    "description": "Good balance of speed and quality",
                    "example": 'ttt @gemini "your question"',
                    "setup": "Already configured ✓",
                }
            )

    elif failed_provider == "anthropic":
        if api_keys["openai"]:
            suggestions.append(
                {
                    "provider": "OpenAI GPT",
                    "description": "Fast and versatile for most tasks",
                    "example": 'ttt @gpt4 "your question"',
                    "setup": "Already configured ✓",
                }
            )
        if api_keys["google"]:
            suggestions.append(
                {
                    "provider": "Google Gemini",
                    "description": "Good alternative for reasoning tasks",
                    "example": 'ttt @gemini "your question"',
                    "setup": "Already configured ✓",
                }
            )

    elif failed_provider == "google":
        if api_keys["openai"]:
            suggestions.append(
                {
                    "provider": "OpenAI GPT",
                    "description": "Reliable alternative with good performance",
                    "example": 'ttt @gpt4 "your question"',
                    "setup": "Already configured ✓",
                }
            )
        if api_keys["anthropic"]:
            suggestions.append(
                {
                    "provider": "Anthropic Claude",
                    "description": "Excellent for complex reasoning",
                    "example": 'ttt @claude "your question"',
                    "setup": "Already configured ✓",
                }
            )

    # Always suggest local as a privacy-focused alternative
    suggestions.append(
        {
            "provider": "Local (Ollama)",
            "description": "Private, runs on your machine (requires Ollama)",
            "example": 'ttt @local "your question"',
            "setup": "Install: curl -fsSL https://ollama.com/install.sh | sh",
        }
    )

    return suggestions


def suggest_troubleshooting_steps(error_type: str, error_message: str = "") -> List[str]:
    """Provide context-specific troubleshooting steps for different error types.

    Args:
        error_type: The type of error (e.g., "connection", "auth", "model_not_found")
        error_message: The full error message for context

    Returns:
        List of troubleshooting steps as strings
    """
    steps = []

    if error_type == "connection" or "connection" in error_message.lower():
        steps = [
            "Check your internet connection",
            "Verify the provider's status page isn't showing outages",
            "Try running 'ttt status' to check backend connectivity",
            "Consider using a different provider with 'ttt @openrouter' if you have an OpenRouter key",
        ]

    elif error_type == "auth" or "api key" in error_message.lower():
        steps = [
            "Check that your API key environment variable is set correctly",
            "Verify your API key hasn't expired or been revoked",
            "Run 'ttt status' to see which API keys are detected",
            "Consider getting an OpenRouter key for access to 100+ models",
        ]

    elif error_type == "model_not_found" or "model" in error_message.lower() and "not found" in error_message.lower():
        steps = [
            "Run 'ttt models' to see all available models",
            "Check if you meant to use a model alias like @gpt4 or @claude",
            "Verify your API keys are configured for the provider",
            "Try a different model: 'ttt @fast \"your question\"'",
        ]

    elif error_type == "rate_limit" or "rate limit" in error_message.lower():
        steps = [
            "Wait a moment before retrying",
            "Consider using a different provider temporarily",
            "Use OpenRouter for higher rate limits across multiple providers",
            "Check your provider's rate limit settings",
        ]

    elif error_type == "timeout" or "timeout" in error_message.lower():
        steps = [
            "Try a simpler question or shorter prompt",
            "Use a faster model like @fast or @gpt3",
            "Check your internet connection stability",
            "Increase timeout with --timeout flag if needed",
        ]

    else:
        # Generic troubleshooting steps
        steps = [
            "Run 'ttt status' to check system health",
            "Try a different model with 'ttt @fast \"your question\"'",
            "Check if your API keys are configured correctly",
            "Visit the TTT documentation for more help",
        ]

    return steps


def _get_provider_from_model(model_name: str) -> str:
    """Extract provider name from model name."""
    if model_name.startswith("openrouter/"):
        return "openrouter"
    elif model_name.startswith("anthropic/") or "claude" in model_name.lower():
        return "anthropic"
    elif model_name.startswith("openai/") or model_name.startswith("gpt-"):
        return "openai"
    elif model_name.startswith("google/") or "gemini" in model_name.lower():
        return "google"
    elif model_name.startswith("cerebras/"):
        return "cerebras"
    else:
        return "local"


def _is_provider_available(provider: str, api_keys: Dict[str, bool]) -> bool:
    """Check if a provider is available based on API keys."""
    if provider == "local":
        return True  # Always suggest local as available
    return api_keys.get(provider, False)


def _get_model_description(alias: str, model_name: str, available: bool, aliases: Optional[List[str]] = None) -> str:
    """Generate a human-readable description for a model."""
    provider = _get_provider_from_model(model_name)

    # Provider-specific descriptions
    provider_descriptions = {
        "openai": "OpenAI GPT",
        "anthropic": "Anthropic Claude",
        "google": "Google Gemini",
        "openrouter": "OpenRouter",
        "cerebras": "Cerebras",
        "local": "Local Ollama",
    }

    # Model-specific descriptions
    if "gpt-4" in model_name or alias == "gpt4" or alias == "best":
        description = f"{provider_descriptions.get(provider, provider)} (high quality, slower)"
    elif "gpt-3.5" in model_name or alias == "gpt3" or alias == "fast":
        description = f"{provider_descriptions.get(provider, provider)} (fast, cheaper)"
    elif "claude" in model_name or alias == "claude":
        description = f"{provider_descriptions.get(provider, provider)} (excellent reasoning)"
    elif "gemini" in model_name or alias == "gemini":
        description = f"{provider_descriptions.get(provider, provider)} (balanced speed/quality)"
    elif alias == "coding":
        description = f"{provider_descriptions.get(provider, provider)} (optimized for code)"
    elif alias == "local":
        description = f"{provider_descriptions.get(provider, provider)} (private, offline)"
    else:
        description = provider_descriptions.get(provider, provider)

    if not available and provider != "local":
        description += " (API key needed)"

    return description


def _detect_failed_provider(error_message: str) -> str:
    """Detect which provider failed based on error message."""
    error_lower = error_message.lower()

    if "openai" in error_lower or "gpt" in error_lower:
        return "openai"
    elif "anthropic" in error_lower or "claude" in error_lower:
        return "anthropic"
    elif "google" in error_lower or "gemini" in error_lower:
        return "google"
    elif "openrouter" in error_lower:
        return "openrouter"
    else:
        return "unknown"


def _get_fallback_suggestions() -> List[Dict[str, Union[str, float, bool]]]:
    """Provide basic suggestions when config loading fails."""
    return [
        {
            "alias": "@fast",
            "model": "openrouter/openai/gpt-3.5-turbo",
            "description": "OpenAI GPT-3.5 (fast, cheap)",
            "similarity": 0.8,
            "available": bool(os.getenv("OPENROUTER_API_KEY")),
        },
        {
            "alias": "@claude",
            "model": "openrouter/anthropic/claude-3-sonnet-20240229",
            "description": "Anthropic Claude (excellent reasoning)",
            "similarity": 0.7,
            "available": bool(os.getenv("OPENROUTER_API_KEY")),
        },
        {
            "alias": "@local",
            "model": "llama2",
            "description": "Local Ollama (private, offline)",
            "similarity": 0.6,
            "available": True,
        },
    ]


def _get_fallback_alias_suggestions() -> List[Dict[str, Union[str, float, bool]]]:
    """Provide basic alias suggestions when config loading fails."""
    return [
        {
            "alias": "@gpt4",
            "model": "gpt-4",
            "description": "OpenAI GPT-4 (high quality)",
            "similarity": 0.9,
            "available": bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")),
        },
        {
            "alias": "@fast",
            "model": "gpt-3.5-turbo",
            "description": "OpenAI GPT-3.5 (fast, cheap)",
            "similarity": 0.8,
            "available": bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")),
        },
        {
            "alias": "@claude",
            "model": "claude-3-sonnet",
            "description": "Anthropic Claude (excellent reasoning)",
            "similarity": 0.7,
            "available": bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY")),
        },
    ]
