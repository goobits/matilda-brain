"""Error display templates for clean, user-friendly error messages.

This module provides templates for converting technical errors into actionable
user messages with emoji indicators and concise suggestions.
"""

from typing import Optional, List


def format_model_overload_error(model: Optional[str] = None) -> str:
    """Format model overload/503 error with suggestions.

    Args:
        model: The model that was overloaded

    Returns:
        Clean error message with suggestions
    """
    model_text = f" ({model})" if model else ""
    return (
        f"⚠️  Model temporarily overloaded{model_text}\n"
        f'Try: ttt "your prompt" -m @fast  # Use a faster model\n'
        f"Or wait a moment and retry your request"
    )


def format_api_key_error(provider: str, env_var: Optional[str] = None) -> str:
    """Format API key missing/invalid error with setup instructions.

    Args:
        provider: The provider name (openai, anthropic, etc.)
        env_var: Environment variable name for the API key

    Returns:
        Clean error message with setup instructions
    """
    env_var = env_var or f"{provider.upper()}_API_KEY"
    setup_cmd = f"export {env_var}=your-key-here"

    provider_urls = {
        "openai": "https://platform.openai.com/account/api-keys",
        "anthropic": "https://console.anthropic.com/",
        "google": "https://makersuite.google.com/app/apikey",
        "openrouter": "https://openrouter.ai/keys",
    }

    url = provider_urls.get(provider.lower(), f"https://{provider}.com")

    return f"❌ Missing {provider} API key\nGet key: {url}\nSet key: {setup_cmd}"


def format_connection_error(backend: Optional[str] = None, details: Optional[str] = None) -> str:
    """Format connection failure error with troubleshooting.

    Args:
        backend: Backend name that failed to connect
        details: Additional error details

    Returns:
        Clean error message with troubleshooting steps
    """
    backend_text = f" to {backend}" if backend else ""

    if backend == "local" or "ollama" in str(details).lower():
        return (
            f"🔌 Connection failed{backend_text}\n"
            f"Check: Is Ollama running? (ollama serve)\n"
            f'Or use: ttt "your prompt" -m @fast  # Use cloud model'
        )

    return (
        f"🔌 Connection failed{backend_text}\n"
        f"Check: Internet connection and service status\n"
        f"Try: ttt status  # Check backend availability"
    )


def format_invalid_model_error(model: str, suggestions: Optional[List[str]] = None) -> str:
    """Format unknown/invalid model error with alternatives.

    Args:
        model: The invalid model name
        suggestions: List of suggested alternative models

    Returns:
        Clean error message with model suggestions
    """
    message = f"❌ Unknown model: {model}\n"

    if suggestions:
        # Show up to 3 suggestions
        suggestion_list = ", ".join(suggestions[:3])
        message += f"Try: {suggestion_list}\n"

    message += "See all: ttt models"
    return message


def format_config_error(issue: str, file_path: Optional[str] = None) -> str:
    """Format configuration error with helpful guidance.

    Args:
        issue: Description of the configuration issue
        file_path: Path to problematic config file

    Returns:
        Clean error message with guidance
    """
    if file_path:
        return f"⚙️  Config error in {file_path}\nIssue: {issue}\nFix: Edit config or run 'ttt config list'"

    return f"⚙️  Configuration error\nIssue: {issue}\nHelp: ttt config list"


def format_rate_limit_error(provider: str, retry_after: Optional[int] = None) -> str:
    """Format rate limit error with timing guidance.

    Args:
        provider: Provider that rate limited the request
        retry_after: Seconds to wait before retrying

    Returns:
        Clean error message with retry guidance
    """
    if retry_after:
        wait_text = f"Wait {retry_after}s then retry"
    else:
        wait_text = "Wait a moment then retry"

    return f'⚠️  Rate limit exceeded ({provider})\n{wait_text}\nOr try: ttt "your prompt" -m @fast  # Different model'


def format_quota_error(provider: str, quota_type: str = "requests") -> str:
    """Format quota exceeded error with account guidance.

    Args:
        provider: Provider with quota issue
        quota_type: Type of quota exceeded

    Returns:
        Clean error message with account guidance
    """
    return (
        f"❌ {quota_type.capitalize()} quota exceeded ({provider})\n"
        f"Check: Account usage and billing status\n"
        f"Or try: Different API key or provider"
    )


def format_timeout_error(backend: Optional[str] = None, timeout: Optional[float] = None) -> str:
    """Format timeout error with retry suggestions.

    Args:
        backend: Backend that timed out
        timeout: Timeout duration in seconds

    Returns:
        Clean error message with retry suggestions
    """
    backend_text = f" ({backend})" if backend else ""
    timeout_text = f" after {timeout}s" if timeout else ""

    return (
        f"⏱️  Request timed out{backend_text}{timeout_text}\n"
        f"Try: Shorter prompt or increase timeout\n"
        f'Or: ttt "prompt" --timeout 120'
    )


def format_generic_error(error: Exception, context: Optional[str] = None) -> str:
    """Format generic error with minimal technical details.

    Args:
        error: The exception that occurred
        context: Optional context about what was being done

    Returns:
        Clean error message
    """
    context_text = f" during {context}" if context else ""
    error_msg = str(error).strip()

    # Keep it simple for unknown errors
    return (
        f"❌ Error{context_text}\n"
        f"Details: {error_msg[:100]}{'...' if len(error_msg) > 100 else ''}\n"
        f"Help: Run with --debug for full details"
    )


def get_model_suggestions(invalid_model: str, available_models: Optional[List[str]] = None) -> List[str]:
    """Get model suggestions based on invalid model name.

    Args:
        invalid_model: The model name that wasn't found
        available_models: List of available models

    Returns:
        List of suggested model names
    """
    if not available_models:
        # Default suggestions based on common patterns
        if "gpt" in invalid_model.lower():
            return ["gpt-4o", "gpt-4o-mini", "@fast"]
        elif "claude" in invalid_model.lower():
            return ["claude-3-5-sonnet-20241022", "@best"]
        elif "gemini" in invalid_model.lower():
            return ["gemini-1.5-pro", "@fast"]
        else:
            return ["@fast", "@best", "@cheap"]

    # Simple similarity matching (could be enhanced with fuzzy matching)
    suggestions = []
    invalid_lower = invalid_model.lower()

    for model in available_models:
        model_lower = model.lower()
        # Check for partial matches
        if (
            invalid_lower in model_lower
            or model_lower in invalid_lower
            or any(word in model_lower for word in invalid_lower.split("-"))
        ):
            suggestions.append(model)
            if len(suggestions) >= 3:
                break

    # Add generic fallbacks if no matches
    if not suggestions:
        suggestions = ["@fast", "@best", "@cheap"]

    return suggestions[:3]


def should_use_error_template(exception: Exception) -> bool:
    """Check if an exception should use error templates vs full traceback.

    Args:
        exception: The exception to check

    Returns:
        True if should use clean template, False for full traceback
    """
    # Import here to avoid circular imports
    from ...core.exceptions import (
        APIKeyError,
        BackendConnectionError,
        BackendTimeoutError,
        ModelNotFoundError,
        RateLimitError,
        QuotaExceededError,
        ConfigurationError,
        ValidationError,
    )

    # Use templates for expected user-facing errors
    template_exceptions = (
        APIKeyError,
        BackendConnectionError,
        BackendTimeoutError,
        ModelNotFoundError,
        RateLimitError,
        QuotaExceededError,
        ConfigurationError,
        ValidationError,
    )

    return isinstance(exception, template_exceptions)
