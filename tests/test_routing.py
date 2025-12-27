"""Tests for the routing system."""

from unittest.mock import patch

import pytest

from matilda_brain import AIResponse, BackendNotAvailableError, ModelInfo
from matilda_brain.config import model_registry
from matilda_brain.core.routing import Router
from matilda_brain.plugins import plugin_registry
from tests.utils import MockBackend


class TestRouter:
    """Test the Router class."""

    def test_router_initialization(self):
        """Test router initialization."""
        router = Router()
        assert router.config is not None
        assert router._backends == {}

    def test_get_backend_local(self):
        """Test getting local backend."""
        router = Router()
        backend = router.get_backend("local")

        assert backend is not None
        assert backend.name == "local"
        assert backend in router._backends.values()

    def test_get_backend_cloud(self):
        """Test getting cloud backend."""
        router = Router()
        backend = router.get_backend("cloud")

        assert backend is not None
        assert backend.name == "cloud"
        assert backend in router._backends.values()

    def test_get_backend_from_plugin(self):
        """Test getting backend from plugin registry."""
        # Register a test backend
        plugin_registry.register_backend("plugin-test", MockBackend)

        router = Router()
        backend = router.get_backend("plugin-test")

        assert backend is not None
        assert backend.name == "mock"  # MockBackend returns "mock" as name

    def test_get_backend_invalid(self):
        """Test getting invalid backend raises error."""
        router = Router()

        with pytest.raises(BackendNotAvailableError, match="Backend not found in registry"):
            router.get_backend("non-existent")

    def test_resolve_backend_instance(self):
        """Test resolving a backend instance."""
        router = Router()
        mock_backend = MockBackend()

        resolved = router.resolve_backend(mock_backend)
        assert resolved is mock_backend

    def test_resolve_backend_string(self):
        """Test resolving a backend by name."""
        router = Router()
        resolved = router.resolve_backend("local")

        assert resolved is not None
        assert resolved.name == "local"

    def test_resolve_backend_auto(self):
        """Test auto backend selection."""
        router = Router()

        with patch.object(router, "_auto_select_backend") as mock_auto:
            mock_auto.return_value = MockBackend()

            router.resolve_backend(None)
            mock_auto.assert_called_once()

    def test_resolve_model_with_alias(self):
        """Test model resolution with aliases."""
        router = Router()

        # The default registry should have "fast" alias
        resolved = router.resolve_model("fast")
        assert resolved == "gpt-3.5-turbo"  # Default fast alias

    def test_resolve_model_without_alias(self):
        """Test model resolution without alias."""
        router = Router()

        resolved = router.resolve_model("some-model")
        assert resolved == "some-model"  # Returns as-is

    def test_resolve_model_none(self):
        """Test model resolution with None."""
        router = Router()

        # If config has default_model, that takes precedence
        if router.config.default_model:
            resolved = router.resolve_model(None)
            assert resolved == router.config.default_model
        else:
            # Only if no config default, check backend default
            mock_backend = MockBackend()
            mock_backend.default_model = "backend-default"
            resolved = router.resolve_model(None, backend=mock_backend)
            assert resolved == "backend-default"


class TestSmartRouting:
    """Test smart routing functionality."""

    def test_smart_route_explicit_backend(self):
        """Test routing with explicit backend."""
        router = Router()

        backend, model = router.smart_route("Test prompt", backend="local", model="llama2")

        assert backend.name == "local"
        assert model == "llama2"

    def test_smart_route_explicit_model(self):
        """Test routing with explicit model determines backend."""
        router = Router()

        # Add a local model to registry
        model_registry.add_model(ModelInfo(name="test-local-model", provider="local", provider_name="test"))

        backend, model = router.smart_route("Test prompt", model="test-local-model")

        assert backend.name == "local"
        assert model == "test-local-model"

    # Note: Tests for prefer_local, code_detection, speed_preference,
    # quality_preference, and custom_keywords have been removed as these
    # features were removed from the codebase per user request.
    # The routing now simply uses configured defaults.


class TestRouterFallback:
    """Test router fallback functionality."""

    @pytest.mark.asyncio
    async def test_route_with_fallback_uses_primary_backend_when_available(self):
        """Test successful routing without fallback."""
        router = Router()

        # Mock successful response
        mock_backend = MockBackend()

        with patch.object(router, "smart_route") as mock_route:
            mock_route.return_value = (mock_backend, "mock-model")

            response = await router.route_with_fallback("Test prompt")

            assert response.backend == "mock"
            assert not response.failed

    @pytest.mark.asyncio
    async def test_route_with_fallback_retry(self):
        """Test routing with fallback on failure."""
        router = Router()

        # Create failing and successful backends
        failing_backend = MockBackend({"name": "cloud"})
        failing_backend._available = True  # Make it available so it gets tried

        success_backend = MockBackend({"name": "local"})
        success_backend._available = True

        # Mock the get_backend method
        def mock_get_backend(name):
            if name == "cloud":
                return failing_backend
            elif name == "local":
                return success_backend
            raise ValueError(f"Unknown backend: {name}")

        with patch.object(router, "get_backend", side_effect=mock_get_backend):
            with patch.object(router, "smart_route") as mock_route:
                mock_route.return_value = (failing_backend, "model")

                # Mock ask to fail on cloud backend, succeed on local
                async def mock_ask_failing(prompt, **kwargs):
                    return AIResponse("", error="Failed", backend="cloud")

                async def mock_ask_success(prompt, **kwargs):
                    return AIResponse("Success", backend="local")

                failing_backend.ask = mock_ask_failing
                success_backend.ask = mock_ask_success

                # Enable fallbacks in config
                router.config.enable_fallbacks = True
                router.config.fallback_order = ["local", "cloud"]

                response = await router.route_with_fallback("Test prompt")

                # Should have tried fallback
                assert response.backend == "local"
                assert response.error is None
                assert str(response) == "Success"
