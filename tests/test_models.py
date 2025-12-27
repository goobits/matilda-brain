"""Tests for the data models."""

from datetime import datetime

import pytest

from matilda_brain import AIResponse, ConfigModel, ModelInfo


class TestAIResponse:
    """Test AIResponse class."""

    @pytest.mark.unit
    def test_metadata_storage(self):
        """Test metadata is stored correctly."""
        response = AIResponse(
            "Test response",
            model="gpt-3.5-turbo",
            backend="cloud",
            tokens_in=10,
            tokens_out=20,
            time_taken=1.5,
            cost=0.01,
        )

        assert response.model == "gpt-3.5-turbo"
        assert response.backend == "cloud"
        assert response.tokens_in == 10
        assert response.tokens_out == 20
        assert response.time_taken == 1.5
        assert response.time == 1.5  # Alias
        assert response.cost == 0.01
        assert response.succeeded
        assert not response.failed

    @pytest.mark.unit
    def test_error_handling(self):
        """Test error state handling."""
        response = AIResponse("", model="test-model", error="Test error")

        assert response.error == "Test error"
        assert response.failed
        assert not response.succeeded

    @pytest.mark.unit
    def test_timestamp_automatically_set_on_response_creation(self):
        """Test that timestamp is set by default."""
        response = AIResponse("test")
        assert isinstance(response.timestamp, datetime)

    @pytest.mark.unit
    def test_repr(self):
        """Test string representation."""
        response = AIResponse(
            "A long response that should be truncated for display",
            model="test-model",
            backend="test",
            time_taken=0.5,
        )

        repr_str = repr(response)
        assert "AIResponse" in repr_str
        assert "test-model" in repr_str
        assert "test" in repr_str
        assert "0.50s" in repr_str


class TestModelInfo:
    """Test ModelInfo dataclass."""

    @pytest.mark.unit
    def test_basic_creation(self):
        """Test basic model creation."""
        model = ModelInfo(name="test-model", provider="test", provider_name="test-provider-model")

        assert model.name == "test-model"
        assert model.provider == "test"
        assert model.provider_name == "test-provider-model"
        assert model.aliases == []
        assert model.capabilities == []

    @pytest.mark.unit
    def test_with_optional_fields(self):
        """Test model with all fields."""
        model = ModelInfo(
            name="gpt-4",
            provider="openai",
            provider_name="gpt-4",
            aliases=["best", "quality"],
            speed="slow",
            quality="high",
            capabilities=["text", "reasoning"],
            context_length=8192,
            cost_per_token=0.00003,
        )

        assert model.aliases == ["best", "quality"]
        assert model.speed == "slow"
        assert model.quality == "high"
        assert model.capabilities == ["text", "reasoning"]
        assert model.context_length == 8192
        assert model.cost_per_token == 0.00003


class TestConfigModel:
    """Test ConfigModel configuration."""

    @pytest.mark.unit
    def test_default_values(self):
        """Test default configuration values."""
        config = ConfigModel()

        # All optional fields should be None by default
        assert config.ollama_base_url is None
        assert config.default_backend is None
        assert config.timeout is None
        assert config.max_retries is None
        assert config.enable_fallbacks is True
        assert config.fallback_order == ["cloud", "local"]

    @pytest.mark.unit
    def test_model_aliases(self):
        """Test model aliases configuration."""
        # ConfigModel starts with empty aliases
        config = ConfigModel()
        assert config.model_aliases == {}

        # Test setting model aliases (without hardcoding specific model names)
        test_aliases = {
            "fast": "test-fast-model",
            "best": "test-best-model",
            "cheap": "test-cheap-model",
            "coding": "test-coding-model",
            "local": "test-local-model",
        }
        config.model_aliases = test_aliases

        # Verify all aliases were set correctly
        assert config.model_aliases == test_aliases

    @pytest.mark.unit
    def test_custom_values(self):
        """Test setting custom values."""
        config = ConfigModel(ollama_base_url="http://custom:8080", default_backend="local", timeout=60)

        assert config.ollama_base_url == "http://custom:8080"
        assert config.default_backend == "local"
        assert config.timeout == 60
