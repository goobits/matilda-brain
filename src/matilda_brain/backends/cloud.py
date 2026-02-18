"""Cloud backend implementation using LiteLLM for multiple providers."""

import json
import os
import time
from typing import Any, AsyncIterator, Dict, List, NoReturn, Optional, Union, cast

# Import model_registry lazily to avoid import-time config loading
from ..core.exceptions import (
    APIKeyError,
    BackendConnectionError,
    BackendNotAvailableError,
    BackendTimeoutError,
    EmptyResponseError,
    ModelNotFoundError,
    QuotaExceededError,
    RateLimitError,
)
from ..core.models import AIResponse, ImageInput
from ..internal.utils import get_logger
from ..internal.utils.messages import build_message_list, extract_messages_from_kwargs
from ..internal.utils.providers import PROVIDER_ENV_VARS
from .base import BaseBackend

logger = get_logger(__name__)


class CloudBackend(BaseBackend):
    """
    Cloud backend that uses LiteLLM to access multiple AI providers.

    Supports OpenAI, Anthropic, Google, and many other providers through
    a unified interface.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the cloud backend.

        Args:
            config: Configuration dictionary containing API keys and settings
        """
        super().__init__(config)

        # Import LiteLLM here to avoid import errors if not installed
        try:
            import litellm

            self.litellm = litellm
        except ImportError as e:
            raise BackendNotAvailableError(
                "cloud",
                "LiteLLM is required for cloud backend. Install with: pip install litellm",
            ) from e

        # Get cloud-specific config
        cloud_config = self.backend_config.get("cloud", {})

        # Default models for different providers
        from ..config.loader import get_config_value

        self.default_models = cloud_config.get("default_models") or get_config_value(
            "backends.cloud.default_models",
            {
                "openai": "gpt-3.5-turbo",
                "anthropic": "claude-3-sonnet-20240229",
                "google": "gemini-pro",
                "openrouter": "openrouter/google/gemini-flash-1.5",
            },
        )

        # Get default model from backend_config (handles merging)
        self.default_model = self.backend_config.get("default_model") or get_config_value(
            "models.default", "gpt-3.5-turbo"
        )

        # Get provider order preference
        self.provider_order = cloud_config.get("provider_order") or get_config_value(
            "backends.cloud.provider_order", ["openai", "anthropic", "google"]
        )

        # Configure API keys from environment
        self._configure_api_keys()

    def _build_messages(
        self,
        prompt: Union[str, List[Union[str, ImageInput]]],
        system: Optional[str] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build messages array for the API request.

        Args:
            prompt: The user prompt - can be a string or list of content (text/images)
            system: System prompt (optional)
            kwargs: Additional parameters that may contain pre-built messages

        Returns:
            List of message dictionaries formatted for the API
        """
        # Check if we received pre-built messages from chat session
        pre_built = extract_messages_from_kwargs(kwargs)
        if pre_built:
            return pre_built

        # Use the shared message building utility
        return build_message_list(prompt, system)

    def _prepare_params(
        self,
        prompt: Union[str, List[Union[str, ImageInput]]],
        model: Optional[str],
        system: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        tools: Optional[List[Any]],
        stream: bool,
        kwargs: Dict[str, Any],
    ) -> tuple[str, Dict[str, Any]]:
        """
        Prepare parameters for LiteLLM API request.

        Handles message building, tool resolution, and parameter assembly for
        both ask() and astream() methods, ensuring consistent behavior.

        Args:
            prompt: The user prompt - can be a string or list of content (text/images)
            model: Specific model to use (optional)
            system: System prompt (optional)
            temperature: Sampling temperature (optional)
            max_tokens: Maximum tokens to generate (optional)
            tools: List of tool definitions (optional)
            stream: Whether to stream the response
            kwargs: Additional parameters

        Returns:
            Tuple of (used_model, params_dict)
        """
        used_model = model or self.default_model

        # Build messages
        messages = self._build_messages(prompt, system, kwargs)

        # Build base parameters
        params: Dict[str, Any] = {
            "model": used_model,
            "messages": messages,
        }

        if stream:
            params["stream"] = True

        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        # Add tools if provided
        if tools:
            from ..tools import resolve_tools

            resolved_tools = resolve_tools(tools)
            tool_definitions = [tool_def.to_openai_schema() for tool_def in resolved_tools]

            if tool_definitions:
                params["tools"] = tool_definitions
                params["tool_choice"] = "auto"

        # Add any additional parameters, filtering out None values and 'messages'
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None and k != "messages"}
        params.update(filtered_kwargs)

        # Add API key explicitly for OpenRouter models
        if used_model.startswith("openrouter/") and os.getenv("OPENROUTER_API_KEY"):
            params["api_key"] = os.getenv("OPENROUTER_API_KEY")

        return used_model, params

    def _handle_request_error(self, e: Exception, used_model: str, request_type: str = "request") -> NoReturn:
        """
        Handle errors from API requests by converting them to appropriate exceptions.

        Args:
            e: The original exception
            used_model: The model that was being used
            request_type: Type of request for logging ("request" or "streaming request")

        Raises:
            Appropriate exception based on error type
        """
        from ..internal.utils.error_display import format_model_overload_error, get_model_suggestions

        error_msg = str(e)
        logger.error(f"Cloud {request_type} failed: {error_msg}")

        # Check for specific error types
        # ServiceUnavailableError (503) - model overloaded or service down
        if hasattr(e, "__class__") and e.__class__.__name__ == "ServiceUnavailableError":
            # Extract key information from the error message
            if "overloaded" in error_msg.lower():
                # Model is temporarily overloaded - provide clean formatted message
                formatted_msg = format_model_overload_error(used_model)
                raise BackendConnectionError(self.name, Exception(formatted_msg)) from e
            else:
                # General service unavailable
                raise BackendConnectionError(
                    self.name, Exception("⚠️  Service temporarily unavailable (503). Please try again")
                ) from e
        elif "api_key" in error_msg.lower() or "api key" in error_msg.lower() or "authentication" in error_msg.lower():
            provider = self._get_provider_from_model(used_model)
            raise APIKeyError(provider, PROVIDER_ENV_VARS.get(provider)) from e
        elif "rate limit" in error_msg.lower():
            provider = self._get_provider_from_model(used_model)
            # Extract retry_after if available
            retry_after = None
            if hasattr(e, "response") and hasattr(e.response, "headers"):
                retry_after = e.response.headers.get("retry-after")
                if retry_after:
                    try:
                        retry_after = int(retry_after)
                    except (ValueError, TypeError):
                        retry_after = None
            raise RateLimitError(provider, retry_after) from e
        elif "quota" in error_msg.lower():
            provider = self._get_provider_from_model(used_model)
            quota_type = "requests"
            if "token" in error_msg.lower():
                quota_type = "tokens"
            raise QuotaExceededError(provider, quota_type) from e
        elif (
            "model_not_found" in error_msg.lower()
            or "does not exist" in error_msg.lower()
            or "not found" in error_msg.lower()
        ):
            # Try to get model suggestions
            try:
                from ..config.schema import get_model_registry

                registry = get_model_registry()
                available_models = list(registry.models.keys())
                get_model_suggestions(used_model, available_models)
            except (ImportError, AttributeError, KeyError) as exc:
                logger.warning(f"Could not load model suggestions: {exc}")
            except Exception:
                logger.exception("Unexpected error loading model suggestions")

            # Create enhanced ModelNotFoundError with suggestions
            raise ModelNotFoundError(used_model, self.name) from e
        elif "timeout" in error_msg.lower():
            raise BackendTimeoutError(self.name, self.timeout) from e
        else:
            raise BackendConnectionError(self.name, e) from e

    def _configure_api_keys(self) -> None:
        """Configure API keys from environment variables."""
        # OpenAI
        if openai_key := (self.backend_config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")):
            os.environ["OPENAI_API_KEY"] = openai_key

        # Anthropic
        if anthropic_key := (self.backend_config.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")):
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key

        # Google
        if google_key := (self.backend_config.get("google_api_key") or os.getenv("GOOGLE_API_KEY")):
            os.environ["GOOGLE_API_KEY"] = google_key

        # OpenRouter
        if openrouter_key := (self.backend_config.get("openrouter_api_key") or os.getenv("OPENROUTER_API_KEY")):
            os.environ["OPENROUTER_API_KEY"] = openrouter_key

        # Cerebras
        if cerebras_key := (self.backend_config.get("cerebras_api_key") or os.getenv("CEREBRAS_API_KEY")):
            os.environ["CEREBRAS_API_KEY"] = cerebras_key

    @property
    def name(self) -> str:
        """Backend name for identification."""
        return "cloud"

    @property
    def is_available(self) -> bool:
        """Check if the cloud backend is available (always True since installed)."""
        # The cloud backend is always "available" as a backend option
        # Individual providers may or may not be configured
        return True

    @property
    def supports_streaming(self) -> bool:
        """Check if backend supports streaming."""
        return True

    @property
    def supports_messages(self) -> bool:
        """Check if backend supports message history format."""
        return True

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
        Send a single prompt to a cloud provider and get a complete response.

        Args:
            prompt: The user prompt - can be a string or list of content (text/images)
            model: Specific model to use (optional)
            system: System prompt (optional)
            temperature: Sampling temperature (optional)
            max_tokens: Maximum tokens to generate (optional)
            **kwargs: Additional parameters

        Returns:
            AIResponse containing the response and metadata
        """
        start_time = time.time()

        # Use unified parameter preparation
        used_model, params = self._prepare_params(
            prompt=prompt,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            stream=False,
            kwargs=kwargs,
        )

        tool_result = None

        try:
            logger.debug(f"Sending request to {used_model}")
            logger.debug(f"Parameters: max_tokens={params.get('max_tokens')}, temperature={params.get('temperature')}")

            response = await self.litellm.acompletion(**params)

            # Handle streaming response if stream=True
            if kwargs.get("stream", False):
                # Collect all chunks from the stream
                response_content = ""
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta:
                        content = chunk.choices[0].delta.content
                        if content:
                            response_content += str(content)

                # For streaming, we don't have tool calls or other metadata
                # Just return the content
                return AIResponse(
                    content=response_content,
                    model=used_model,
                    backend=self.name,
                    metadata={
                        "finish_reason": "stop",
                        "elapsed_time": time.time() - start_time,
                    },
                )

            # Extract response content for non-streaming
            if not response.choices:
                raise EmptyResponseError(used_model, self.name)

            response_content = response.choices[0].message.content or ""

            # Handle tool calls if present
            message = response.choices[0].message
            if hasattr(message, "tool_calls") and message.tool_calls:
                # Import tool execution here to avoid circular imports
                from ..tools import execute_tools

                # Build tool calls data
                tool_calls_data = []

                for tool_call in message.tool_calls:
                    if tool_call.type == "function":
                        func_call = tool_call.function
                        try:
                            arguments = json.loads(func_call.arguments) if func_call.arguments else {}
                        except json.JSONDecodeError:
                            arguments = {}

                        tool_calls_data.append(
                            {
                                "id": tool_call.id,
                                "name": func_call.name,
                                "arguments": arguments,
                            }
                        )

                # Execute tool calls
                if tool_calls_data and tools:
                    # The new executor doesn't need tool definitions map
                    tool_result = await execute_tools(tool_calls_data, parallel=True)

                    # Update content with tool results if content is empty
                    if not response_content:
                        # Generate a response based on tool results
                        results_summary = []
                        for call in tool_result.calls:
                            if call.succeeded:
                                results_summary.append(f"{call.name}: {call.result}")
                            else:
                                results_summary.append(f"{call.name}: Error - {call.error}")
                        response_content = "Tool execution completed:\n" + "\n".join(results_summary)

            if not response_content:
                raise EmptyResponseError(used_model, self.name)

            time_taken = time.time() - start_time

            # Extract usage information
            usage = response.usage
            tokens_in = usage.prompt_tokens if usage else None
            tokens_out = usage.completion_tokens if usage else None

            # Calculate cost if available
            cost = None
            if hasattr(response, "_hidden_params"):
                try:
                    if isinstance(response._hidden_params, dict) and "response_cost" in response._hidden_params:
                        cost = response._hidden_params["response_cost"]
                except (TypeError, AttributeError):
                    # Handle mocks or other non-dict types
                    pass

            return AIResponse(
                response_content,
                model=used_model,
                backend=self.name,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                time_taken=time_taken,
                tool_result=tool_result,
                cost=cost,
                metadata={
                    "provider": self._get_provider_from_model(used_model),
                    "finish_reason": response.choices[0].finish_reason,
                },
            )

        except EmptyResponseError:
            # Re-raise EmptyResponseError as-is
            raise
        except Exception as e:
            self._handle_request_error(e, used_model)

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
        Stream a response from a cloud provider token by token.

        Args:
            prompt: The user prompt - can be a string or list of content (text/images)
            model: Specific model to use (optional)
            system: System prompt (optional)
            temperature: Sampling temperature (optional)
            max_tokens: Maximum tokens to generate (optional)
            **kwargs: Additional parameters

        Yields:
            Response chunks as they arrive
        """

        async def _gen() -> AsyncIterator[str]:
            # Use unified parameter preparation
            used_model, params = self._prepare_params(
                prompt=prompt,
                model=model,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                stream=True,
                kwargs=kwargs,
            )

            try:
                logger.debug(f"Starting stream request to {used_model}")
                logger.debug(
                    f"Stream parameters: max_tokens={params.get('max_tokens')}, temperature={params.get('temperature')}"
                )

                response = await self.litellm.acompletion(**params)

                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta:
                        content = chunk.choices[0].delta.content
                        if content:
                            # Content should be a string in streaming responses
                            yield str(content)

            except Exception as e:
                self._handle_request_error(e, used_model, "streaming request")

        return _gen()

    async def models(self) -> List[str]:
        """
        Get list of available models from the central model registry.
        This backend supports all non-local models.

        Returns:
            List of model names available on cloud providers
        """
        # Get all model definitions from the registry
        from ..config.schema import model_registry

        all_model_info = model_registry.models.values()

        # Filter for models that are NOT from the 'local' provider
        cloud_models = [model.name for model in all_model_info if model.provider != "local"]
        logger.debug(f"Found {len(cloud_models)} cloud models in registry")
        return sorted(cloud_models)

    async def list_models(self, detailed: bool = False) -> List[Union[str, Dict[str, Any]]]:
        """
        List available models from the registry, optionally with details.

        Args:
            detailed: Whether to return detailed model information

        Returns:
            List of model names or detailed model information
        """
        # Get all non-local models from the registry
        from ..config.schema import model_registry

        all_model_info = [model for model in model_registry.models.values() if model.provider != "local"]

        if not detailed:
            result: List[str] = sorted([model.name for model in all_model_info])
            return cast(List[Union[str, Dict[str, Any]]], result)

        # Return detailed information directly from the model info objects
        detailed_models: List[Union[str, Dict[str, Any]]] = []
        for model in sorted(all_model_info, key=lambda m: m.name):
            detailed_models.append(
                {
                    "name": model.name,
                    "provider": model.provider,
                    "capabilities": model.capabilities,
                    "speed": model.speed,
                    "quality": model.quality,
                    "context_length": model.context_length,
                }
            )
        return detailed_models

    # Removed _get_provider_for_model and _get_capabilities_for_model
    # This logic is now handled by the ModelInfo dataclass in the registry

    async def status(self, test_connection: bool = False) -> Dict[str, Any]:
        """
        Get status information for cloud providers.

        Args:
            test_connection: Whether to test actual connectivity (optional)

        Returns:
            Dictionary containing status information
        """
        providers: Dict[str, Dict[str, Any]] = {}

        # Check OpenAI
        if os.getenv("OPENAI_API_KEY"):
            providers["openai"] = {"available": True, "configured": True, "models": 4}
        else:
            providers["openai"] = {
                "available": False,
                "configured": False,
                "error": "OPENAI_API_KEY not configured",
            }

        # Check Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            providers["anthropic"] = {
                "available": True,
                "configured": True,
                "models": 3,
            }
        else:
            providers["anthropic"] = {
                "available": False,
                "configured": False,
                "error": "ANTHROPIC_API_KEY not configured",
            }

        # Check Google
        if os.getenv("GOOGLE_API_KEY"):
            providers["google"] = {"available": True, "configured": True, "models": 2}
        else:
            providers["google"] = {
                "available": False,
                "configured": False,
                "error": "GOOGLE_API_KEY not configured",
            }

        # If test_connection is True, perform actual connection tests
        if test_connection:
            for provider, info in providers.items():
                if info.get("configured", False):
                    # Test the connection by making a small API call
                    try:
                        test_model = self.default_models.get(provider)
                        if test_model:
                            # Make a minimal test request
                            test_response = await self.ask("Hello", model=test_model, max_tokens=5)
                            if test_response and not test_response.failed:
                                info["test_result"] = "success"
                            else:
                                info["test_result"] = "failed"
                                info["test_error"] = str(test_response.error) if test_response else "No response"
                    except Exception as e:
                        logger.exception(f"Connection test failed for provider {provider}")
                        info["test_result"] = "failed"
                        info["test_error"] = str(e)

        total_models = sum(p.get("models", 0) for p in providers.values() if p.get("available", False))

        return {
            "backend": self.name,
            "available": self.is_available,
            "providers": providers,
            "total_models": total_models,
            "default_model": self.default_model,
        }

    def _get_provider_from_model(self, model: str) -> str:
        """Determine the provider from the model name."""
        # Handle OpenRouter model format
        if model.startswith("openrouter/"):
            # For OpenRouter, we use OPENROUTER_API_KEY
            return "openrouter"
        elif model.startswith("cerebras/"):
            return "cerebras"
        # Handle direct provider models
        elif model.startswith("gpt-") or "gpt-" in model:
            return "openai"
        elif model.startswith("claude-") or "claude-" in model:
            return "anthropic"
        elif model.startswith("gemini-") or "gemini-" in model:
            return "google"
        else:
            return "unknown"
