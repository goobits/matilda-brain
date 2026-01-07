"""Unified routing logic for selecting backends and models."""

from typing import Any, Dict, List, Optional, Union, cast

from ..backends import HAS_LOCAL_BACKEND, BaseBackend, CloudBackend
from ..config.schema import get_config
from ..plugins.loader import plugin_registry
from ..internal.utils import get_logger
from .exceptions import BackendNotAvailableError
from .models import AIResponse, ImageInput

if HAS_LOCAL_BACKEND:
    from ..backends import LocalBackend

logger = get_logger(__name__)


class Router:
    """
    Smart router that selects the best backend and model for each request.

    The router handles:
    - Backend selection (local vs cloud vs auto)
    - Model resolution (aliases to actual models)
    - Fallback handling when primary backend fails
    - Smart routing based on query type
    """

    def __init__(self) -> None:
        self.config = get_config()
        self._backends: Dict[str, BaseBackend] = {}
        self._local_models_cache: Optional[List[str]] = None
        self._cache_timestamp: Optional[float] = None
        # Get cache TTL from constants
        from ..config.loader import get_config_value

        self._cache_ttl = get_config_value("constants.timeouts.cache_ttl", 30)  # Cache TTL in seconds

    def get_backend(self, backend_name: str) -> BaseBackend:
        """Get or create a backend instance."""
        if backend_name not in self._backends:
            # Pass the full configuration dict to backends
            config_dict = self.config.model_dump()

            # Try built-in backends first
            if backend_name == "local":
                if not HAS_LOCAL_BACKEND:
                    raise BackendNotAvailableError(
                        "local",
                        "Local backend not available. Install with: pip install ai[local]",
                    )
                self._backends[backend_name] = LocalBackend(config_dict)
            elif backend_name == "cloud":
                self._backends[backend_name] = CloudBackend(config_dict)
            else:
                # Try plugin registry
                backend = plugin_registry.create_backend(backend_name, config_dict)
                if backend:
                    self._backends[backend_name] = backend
                else:
                    raise BackendNotAvailableError(backend_name, "Backend not found in registry")

        return self._backends[backend_name]

    def resolve_backend(self, backend: Optional[Union[str, BaseBackend]] = None) -> BaseBackend:
        """
        Resolve backend specification to actual backend instance.

        Args:
            backend: Backend specification (str, BaseBackend, or None for auto)

        Returns:
            BaseBackend instance
        """
        if isinstance(backend, BaseBackend):
            return backend

        # Handle mock objects (for testing)
        if hasattr(backend, "_mock_name") or str(type(backend)).startswith("<class 'unittest.mock"):
            return cast(BaseBackend, backend)

        if isinstance(backend, str):
            return self.get_backend(backend)

        # Auto-select backend
        if backend is None:
            return self._auto_select_backend()

        raise ValueError(f"Invalid backend specification: {backend}")

    def _try_backend_safely(self, backend_name: str, success_message: str) -> Optional[BaseBackend]:
        """
        Safely try to get and validate a backend.

        Args:
            backend_name: Name of the backend to try
            success_message: Message to log on success

        Returns:
            Backend instance if available, None otherwise
        """
        try:
            backend = self.get_backend(backend_name)
            if backend.is_available:
                logger.debug(success_message)
                return backend
        except (BackendNotAvailableError, ImportError, ConnectionError) as e:
            # Use warning for local backend failures, debug for others
            log_level = logger.warning if backend_name == "local" else logger.debug
            log_level(f"{backend_name.title()} backend not available: {e}")
        return None

    def _auto_select_backend(self) -> BaseBackend:
        """
        Automatically select the best available backend.

        Returns:
            BaseBackend instance
        """
        # Check default backend preference
        if self.config.default_backend and self.config.default_backend != "auto":
            backend = self._try_backend_safely(
                self.config.default_backend, f"Using configured default backend: {self.config.default_backend}"
            )
            if backend:
                return backend

            # If default backend was explicitly configured but unavailable, raise a clear error
            if self.config.default_backend == "local":
                error_msg = (
                    "Local backend is configured as default but Ollama is not running. "
                    "Please start Ollama with 'ollama serve' or change default_backend in your config."
                )
                raise BackendNotAvailableError("local", error_msg)
            else:
                # For other backends, show a generic error
                error_msg = f"Configured default backend '{self.config.default_backend}' is not available."
                raise BackendNotAvailableError(self.config.default_backend, error_msg)

        # Try cloud first (always available)
        backend = self._try_backend_safely("cloud", "Using cloud backend")
        if backend:
            return backend

        # Fallback to local if available
        if HAS_LOCAL_BACKEND:
            backend = self._try_backend_safely("local", "Using local backend")
            if backend:
                return backend

        # Try other backends in fallback order
        for backend_name in self.config.fallback_order:
            if backend_name in ["cloud", "local"]:
                continue  # Already tried above
            backend = self._try_backend_safely(backend_name, f"Auto-selected backend: {backend_name}")
            if backend:
                return backend

        # No backends available
        error_msg = "No backends available."
        if not HAS_LOCAL_BACKEND:
            error_msg += " For local models: pip install ai[local]"
        raise BackendNotAvailableError("auto", error_msg)

    def _is_local_model(self, model: str, local_backend: Optional[Any]) -> bool:
        """
        Check if a model is available locally with caching.

        Args:
            model: Model name to check
            local_backend: Local backend instance

        Returns:
            True if model is available locally
        """
        import time

        current_time = time.time()

        # Check if cache is still valid
        if (
            self._local_models_cache is not None
            and self._cache_timestamp is not None
            and current_time - self._cache_timestamp < self._cache_ttl
        ):
            return model in self._local_models_cache

        # Cache is stale or missing, refresh it
        try:
            import httpx

            from ..internal.utils import run_async

            async def fetch_local_models() -> List[str]:
                """Fetch available local models using proper resource management."""
                if local_backend is None:
                    return []

                try:
                    # Use backend health check timeout from constants
                    from ..config.loader import get_config_value

                    health_check_timeout = get_config_value("constants.timeouts.backend_health_check", 3)

                    # Use async context manager to ensure proper HTTP client cleanup
                    async with httpx.AsyncClient(timeout=health_check_timeout) as client:
                        response = await client.get(f"{local_backend.base_url}/api/tags")
                        try:
                            if response.status_code == 200:
                                data = response.json()
                                return [m["name"] for m in data.get("models", [])]
                            return []
                        finally:
                            # Ensure response is properly closed
                            await response.aclose()

                except (ConnectionError, TimeoutError, ValueError, httpx.RequestError, httpx.HTTPStatusError):
                    return []

            available_models = run_async(fetch_local_models())
            self._local_models_cache = available_models
            self._cache_timestamp = current_time

            return model in available_models

        except (ImportError, ConnectionError, TimeoutError) as e:
            logger.debug(f"Failed to fetch local models: {e}")
            return False

    def resolve_model(self, model: Optional[str] = None, backend: Optional[BaseBackend] = None) -> str:
        """
        Resolve model specification to actual model name.

        Args:
            model: Model name or alias
            backend: Target backend for context

        Returns:
            Resolved model name
        """
        if model is None:
            # Use default model from config
            if self.config.default_model:
                model = self.config.default_model
            else:
                # Use backend-specific default
                if backend and hasattr(backend, "default_model"):
                    return str(backend.default_model)

                # Get fallback from config
                from ..config.loader import get_config_value

                return str(get_config_value("models.default", "gpt-3.5-turbo"))

        # Try to resolve alias
        from ..config.schema import model_registry

        # At this point model should not be None, but add safety check
        if model is None:
            raise ValueError("Model cannot be None at this point")

        resolved = model_registry.resolve_model_name(model)
        logger.debug(f"Resolved model '{model}' to '{resolved}'")
        return str(resolved)

    def smart_route(
        self,
        prompt: Union[str, List[Union[str, ImageInput]]],
        *,
        model: Optional[str] = None,
        backend: Optional[Union[str, BaseBackend]] = None,
        **kwargs: Any,
    ) -> tuple[BaseBackend, str]:
        """
        Smart routing that selects backend and model based on preferences and prompt.

        Args:
            prompt: The user prompt - can be a string or list of content (text/images)
            model: Specific model requested
            backend: Specific backend requested
            **kwargs: Additional parameters

        Returns:
            Tuple of (backend, model_name)
        """
        # Check if prompt contains images (multi-modal)
        has_images = False
        if not isinstance(prompt, str):
            has_images = any(isinstance(item, ImageInput) for item in prompt)
            # If images present, must use cloud backend with vision model
            if has_images:
                if backend is None or backend == "local":
                    logger.info("Images detected, switching to cloud backend with vision model")
                    backend = "cloud"
                    if model is None:
                        # Default to a vision-capable model
                        model = "gpt-4-vision-preview"

        # If specific backend requested, use it
        if backend is not None:
            selected_backend = self.resolve_backend(backend)
            selected_model = self.resolve_model(model, selected_backend)
            return selected_backend, selected_model

        # If specific model requested, determine backend from model
        if model is not None:
            # First check if it's in the registry
            from ..config.schema import model_registry

            model_info = model_registry.get_model(model)
            if model_info:
                if model_info.provider == "local":
                    selected_backend = self.get_backend("local")
                else:
                    selected_backend = self.get_backend("cloud")
                selected_model = self.resolve_model(model, selected_backend)
                return selected_backend, selected_model

            # If not in registry, detect cloud models by naming patterns
            # Get patterns from config
            from ..config.loader import get_project_config

            project_defaults = get_project_config()
            cloud_model_patterns = project_defaults.get("routing", {}).get(
                "cloud_model_patterns",
                [
                    "openrouter/",
                    "anthropic/",
                    "openai/",
                    "google/",
                    "gpt-",
                    "claude-",
                    "gemini-",
                    "mistral/",
                    "meta/",
                    "cohere/",
                    "replicate/",
                    "huggingface/",
                ],
            )

            is_cloud_model = any(model.startswith(pattern) for pattern in cloud_model_patterns)

            if is_cloud_model:
                logger.debug(f"Detected cloud model pattern: {model}")
                selected_backend = self.get_backend("cloud")
                selected_model = self.resolve_model(model, selected_backend)
                return selected_backend, selected_model

            # If not a cloud model and local backend is available, check if it's a local model
            if HAS_LOCAL_BACKEND:
                try:
                    local_backend = self.get_backend("local")
                    if local_backend.is_available and self._is_local_model(model, local_backend):
                        logger.debug(f"Detected local model: {model}")
                        selected_model = self.resolve_model(model, local_backend)
                        return local_backend, selected_model
                except (BackendNotAvailableError, ConnectionError, ValueError) as e:
                    logger.debug(f"Failed to check local backend for model {model}: {e}")

        # Use auto-selection to respect configured default_backend
        selected_backend = self._auto_select_backend()

        # Use configured default model
        selected_model = self.resolve_model(model, selected_backend)

        return selected_backend, selected_model

    async def route_with_fallback(
        self,
        prompt: str,
        method: str = "ask",
        *,
        max_retries: Optional[int] = None,
        **kwargs: Any,
    ) -> AIResponse:
        """
        Route request with automatic fallback on failure.

        Args:
            prompt: The user prompt
            method: Method to call ('ask' or 'astream')
            max_retries: Maximum retries (uses config default if None)
            **kwargs: Parameters for the request

        Returns:
            AIResponse from successful backend
        """
        max_retries = max_retries or self.config.max_retries

        # Get primary backend and model
        backend, model = self.smart_route(prompt, **kwargs)

        # Try primary backend
        try:
            if method == "ask":
                response = await backend.ask(prompt, model=model, **kwargs)
                if not response.failed:
                    return response
        except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
            logger.warning(f"Primary backend {backend.name} failed: {e}")

        # Try fallback backends if enabled
        if not self.config.enable_fallbacks:
            logger.debug("Fallbacks disabled, returning failed response")
            return AIResponse("", error="Primary backend failed and fallbacks disabled")

        # Try other backends
        for backend_name in self.config.fallback_order:
            if backend_name == backend.name:
                continue  # Skip the one we already tried

            try:
                fallback_backend = self.get_backend(backend_name)
                if not fallback_backend.is_available:
                    continue

                logger.info(f"Trying fallback backend: {backend_name}")

                # Resolve model for this backend
                fallback_model = self.resolve_model(model, fallback_backend)

                if method == "ask":
                    response = await fallback_backend.ask(prompt, model=fallback_model, **kwargs)
                    if not response.failed:
                        return response

            except (
                BackendNotAvailableError,
                ConnectionError,
                TimeoutError,
                ValueError,
            ) as e:
                logger.warning(f"Fallback backend {backend_name} failed: {e}")

        # All backends failed
        return AIResponse("", error="All backends failed")


# Global router instance
router = Router()
