"""Base backend abstract class defining the common interface."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from ..core.models import AIResponse, ImageInput


class BaseBackend(ABC):
    """
    Abstract base class for all AI backends.

    This defines the common interface that all backends must implement,
    whether they're local (Ollama) or cloud-based (OpenAI, Anthropic, etc.).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the backend.

        Args:
            config: Backend-specific configuration
        """
        self.config = config or {}

        # Extract backend-specific config if available
        backends_config = self.config.get("backends", {})
        backend_specific = backends_config.get(self.name, {}) if hasattr(self, "name") else {}

        # Merge configurations with backend-specific taking precedence
        self.backend_config = {**self.config, **backend_specific}

        # Common configuration attributes
        from ..config.loader import get_config_value

        self.timeout = self.backend_config.get("timeout") or get_config_value("timeout", 30)
        self.max_retries = self.backend_config.get("max_retries") or get_config_value("max_retries", 3)
        self.default_model = self.backend_config.get("default_model") or get_config_value("models.default")

    @abstractmethod
    async def ask(
        self,
        prompt: Union[str, List[Union[str, ImageInput]]],
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> AIResponse:
        """
        Send a single prompt and get a response.

        Args:
            prompt: The user prompt - can be a string or list of content (text/images)
            model: Specific model to use (optional)
            system: System prompt (optional)
            temperature: Sampling temperature (optional)
            max_tokens: Maximum tokens to generate (optional)
            tools: List of functions/tools the AI can call (optional)
            **kwargs: Additional backend-specific parameters

        Returns:
            AIResponse containing the response and metadata
        """
        pass

    @abstractmethod
    def astream(
        self,
        prompt: Union[str, List[Union[str, ImageInput]]],
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream a response token by token.

        Args:
            prompt: The user prompt - can be a string or list of content (text/images)
            model: Specific model to use (optional)
            system: System prompt (optional)
            temperature: Sampling temperature (optional)
            max_tokens: Maximum tokens to generate (optional)
            tools: List of functions/tools the AI can call (optional)
            **kwargs: Additional backend-specific parameters

        Yields:
            Response chunks as they arrive
        """
        pass

    @abstractmethod
    async def models(self) -> List[str]:
        """
        Get list of available models.

        Returns:
            List of model names available on this backend
        """
        pass

    @abstractmethod
    async def status(self) -> Dict[str, Any]:
        """
        Get backend status information.

        Returns:
            Dictionary containing status information
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name for identification."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is currently available."""
        pass
