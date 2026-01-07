"""Tests for the cloud backend with mocked LiteLLM."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

import matilda_brain as ttt

from matilda_brain import (
    APIKeyError,
    BackendNotAvailableError,
    EmptyResponseError,
    ImageInput,
    ModelNotFoundError,
    QuotaExceededError,
    RateLimitError,
)


class MockLiteLLM:
    """Mock LiteLLM module for testing."""

    def __init__(self):
        self.acompletion = AsyncMock()
        self.ModelResponse = Mock
        self.AuthenticationError = type("AuthenticationError", (Exception,), {})
        self.RateLimitError = type("RateLimitError", (Exception,), {})
        self.NotFoundError = type("NotFoundError", (Exception,), {})
        self.APIError = type("APIError", (Exception,), {})

    class MockChoice:
        def __init__(self, message, finish_reason="stop"):
            self.message = message
            self.finish_reason = finish_reason

    class MockMessage:
        def __init__(self, content):
            self.content = content
            self.tool_calls = None

    class MockUsage:
        def __init__(self, prompt_tokens=10, completion_tokens=20, total_tokens=30):
            self.prompt_tokens = prompt_tokens
            self.completion_tokens = completion_tokens
            self.total_tokens = total_tokens

    class MockResponse:
        def __init__(self, content, model="gpt-3.5-turbo", usage=None):
            self.choices = [MockLiteLLM.MockChoice(MockLiteLLM.MockMessage(content))]
            self.model = model
            self.usage = usage or MockLiteLLM.MockUsage()


@pytest.fixture
def mock_litellm():
    """Fixture that provides a mocked litellm module."""
    mock = MockLiteLLM()
    with patch.dict("sys.modules", {"litellm": mock}):
        yield mock


@pytest.fixture
def cloud_backend(mock_litellm):
    """Fixture that provides a CloudBackend with mocked litellm."""
    # Need to reload the module to pick up the mocked litellm
    import importlib


    importlib.reload(ttt.backends.cloud)

    backend = ttt.backends.cloud.CloudBackend()
    backend.litellm = mock_litellm
    return backend


class TestCloudBackendInitialization:
    """Test CloudBackend initialization."""

    def test_init_creates_backend_with_litellm_dependency_available(self, mock_litellm):
        """Test successful initialization with litellm available."""
        import importlib


        importlib.reload(ttt.backends.cloud)

        backend = ttt.backends.cloud.CloudBackend()
        assert backend.name == "cloud"
        assert backend.litellm is not None

    def test_init_without_litellm(self):
        """Test initialization fails without litellm."""
        with patch.dict("sys.modules", {"litellm": None}):
            import importlib


            importlib.reload(ttt.backends.cloud)

            with pytest.raises(BackendNotAvailableError) as exc_info:
                ttt.backends.cloud.CloudBackend()

            assert "LiteLLM is required" in str(exc_info.value)


# Removed TestCloudBackendProperties - tests for trivial getters add no value


class TestCloudBackendAsk:
    """Test CloudBackend ask method."""

    @pytest.mark.asyncio
    async def test_ask_returns_response_with_model_and_token_metadata(self, cloud_backend, mock_litellm):
        """Test successful ask request."""
        mock_response = MockLiteLLM.MockResponse("This is a test response", model="gpt-3.5-turbo")
        mock_litellm.acompletion.return_value = mock_response

        response = await cloud_backend.ask("Test prompt", model="gpt-3.5-turbo")

        assert str(response) == "This is a test response"
        assert response.model == "gpt-3.5-turbo"
        assert response.backend == "cloud"
        assert response.tokens_in == 10
        assert response.tokens_out == 20

        # Verify litellm was called correctly
        mock_litellm.acompletion.assert_called_once()
        call_args = mock_litellm.acompletion.call_args
        assert call_args[1]["model"] == "gpt-3.5-turbo"
        assert call_args[1]["messages"][0]["content"] == "Test prompt"

    @pytest.mark.asyncio
    async def test_ask_with_system_prompt(self, cloud_backend, mock_litellm):
        """Test ask with system prompt."""
        mock_response = MockLiteLLM.MockResponse("Response")
        mock_litellm.acompletion.return_value = mock_response

        await cloud_backend.ask("User prompt", system="You are a helpful assistant")

        # Check that system message was added
        call_args = mock_litellm.acompletion.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "User prompt"

    @pytest.mark.asyncio
    async def test_ask_with_images(self, cloud_backend, mock_litellm):
        """Test ask with image inputs."""
        mock_response = MockLiteLLM.MockResponse("I see an image")
        mock_litellm.acompletion.return_value = mock_response

        await cloud_backend.ask(["What's in this image?", ImageInput(b"fake_image_data_for_testing")])

        # Check that message was formatted correctly for vision
        call_args = mock_litellm.acompletion.call_args
        messages = call_args[1]["messages"]
        assert messages[0]["role"] == "user"
        assert isinstance(messages[0]["content"], list)
        assert messages[0]["content"][0]["type"] == "text"
        assert messages[0]["content"][0]["text"] == "What's in this image?"
        assert messages[0]["content"][1]["type"] == "image_url"

    @pytest.mark.asyncio
    async def test_ask_authentication_error(self, cloud_backend, mock_litellm):
        """Test ask with authentication error."""
        mock_litellm.acompletion.side_effect = Exception("Invalid API key")

        with pytest.raises(APIKeyError) as exc_info:
            await cloud_backend.ask("Test", model="gpt-3.5-turbo")

        assert exc_info.value.details["provider"] == "openai"
        assert exc_info.value.details["env_var"] == "OPENAI_API_KEY"

    @pytest.mark.asyncio
    async def test_ask_rate_limit_error(self, cloud_backend, mock_litellm):
        """Test ask with rate limit error."""
        mock_litellm.acompletion.side_effect = Exception("Rate limit exceeded")

        with pytest.raises(RateLimitError) as exc_info:
            await cloud_backend.ask("Test", model="claude-3-sonnet-20240229")

        assert exc_info.value.details["provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_ask_model_not_found(self, cloud_backend, mock_litellm):
        """Test ask with model not found error."""
        mock_litellm.acompletion.side_effect = Exception("Model 'gpt-5' not found")

        with pytest.raises(ModelNotFoundError) as exc_info:
            await cloud_backend.ask("Test", model="gpt-5")

        assert exc_info.value.details["model"] == "gpt-5"


class TestCloudBackendStream:
    """Test CloudBackend streaming."""

    @pytest.mark.asyncio
    async def test_stream_yields_incremental_content_chunks(self, cloud_backend, mock_litellm):
        """Test successful streaming."""

        # Create async generator for streaming
        async def mock_stream(*args, **kwargs):
            chunks = ["Hello", " ", "world", "!"]
            for chunk in chunks:
                mock_chunk = Mock()
                mock_chunk.choices = [Mock()]
                mock_chunk.choices[0].delta = Mock()
                mock_chunk.choices[0].delta.content = chunk
                yield mock_chunk

        mock_litellm.acompletion.return_value = mock_stream()

        chunks = []
        async for chunk in cloud_backend.astream("Test prompt"):
            chunks.append(chunk)

        assert chunks == ["Hello", " ", "world", "!"]

        # Verify streaming was requested
        call_args = mock_litellm.acompletion.call_args
        assert call_args[1]["stream"] is True

    @pytest.mark.asyncio
    async def test_stream_with_images(self, cloud_backend, mock_litellm):
        """Test streaming with image inputs."""

        async def mock_stream(*args, **kwargs):
            yield Mock(choices=[Mock(delta=Mock(content="Image "))])
            yield Mock(choices=[Mock(delta=Mock(content="description"))])

        mock_litellm.acompletion.return_value = mock_stream()

        chunks = []
        async for chunk in cloud_backend.astream(["Describe this", ImageInput(b"fake_image_data_for_testing")]):
            chunks.append(chunk)

        assert "".join(chunks) == "Image description"


class TestCloudBackendModels:
    """Test CloudBackend model listing."""

    @pytest.mark.asyncio
    async def test_list_models(self, cloud_backend):
        """Test listing available models."""
        models = await cloud_backend.list_models()

        assert isinstance(models, list)
        assert len(models) > 0
        assert "gpt-4" in models
        assert "gpt-3.5-turbo" in models
        assert "claude-3-opus" in models  # Use model name, not provider name
        assert "gemini-pro" in models

    @pytest.mark.asyncio
    async def test_list_models_with_capabilities(self, cloud_backend):
        """Test listing models returns detailed info."""
        models = await cloud_backend.list_models(detailed=True)

        assert isinstance(models, list)
        assert all(isinstance(m, dict) for m in models)

        # Check that models have expected structure (without hardcoding specific model names)
        if models:  # Only check if we have models
            first_model = models[0]
            assert "name" in first_model
            assert "provider" in first_model
            assert "capabilities" in first_model


class TestCloudBackendStatus:
    """Test CloudBackend status checks."""

    @pytest.mark.asyncio
    async def test_status_all_providers_ok(self, cloud_backend, monkeypatch):
        """Test status when all providers have API keys."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        status = await cloud_backend.status()

        assert status["available"] is True
        assert status["providers"]["openai"]["available"] is True
        assert status["providers"]["anthropic"]["available"] is True
        assert status["providers"]["google"]["available"] is True

    @pytest.mark.asyncio
    async def test_status_missing_api_keys(self, cloud_backend, monkeypatch):
        """Test status with missing API keys."""
        # Clear all API keys
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        status = await cloud_backend.status()

        assert status["available"] is True  # At least one provider might work
        assert status["providers"]["openai"]["available"] is False
        assert "OPENAI_API_KEY" in status["providers"]["openai"]["error"]

    @pytest.mark.asyncio
    async def test_status_with_test_mode(self, cloud_backend, mock_litellm, monkeypatch):
        """Test status with connection testing."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Mock successful test
        mock_response = MockLiteLLM.MockResponse("Test response")
        mock_litellm.acompletion.return_value = mock_response

        status = await cloud_backend.status(test_connection=True)

        assert status["providers"]["openai"]["test_result"] == "success"

        # Verify test was performed
        mock_litellm.acompletion.assert_called()


class TestCloudBackendErrorHandling:
    """Test comprehensive error handling."""

    @pytest.mark.asyncio
    async def test_provider_specific_errors(self, cloud_backend, mock_litellm):
        """Test provider-specific error detection."""
        # Test OpenAI quota error
        mock_litellm.acompletion.side_effect = Exception("You exceeded your current quota")

        with pytest.raises(QuotaExceededError) as exc_info:
            await cloud_backend.ask("Test", model="gpt-4")

        assert exc_info.value.details["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_empty_response_handling(self, cloud_backend, mock_litellm):
        """Test handling of empty responses."""
        # Mock empty response
        mock_response = Mock()
        mock_response.choices = []
        mock_litellm.acompletion.return_value = mock_response

        with pytest.raises(EmptyResponseError) as exc_info:
            await cloud_backend.ask("Test")

        assert "empty response" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_timeout_handling(self, cloud_backend, mock_litellm):
        """Test timeout handling."""

        # Mock timeout by raising TimeoutError directly
        mock_litellm.acompletion.side_effect = asyncio.TimeoutError("Mocked timeout")

        with pytest.raises(Exception):  # noqa: B017  # Should timeout
            await cloud_backend.ask("Test", timeout=0.1)


class TestProviderDetection:
    """Test provider detection from model names."""

    def test_get_provider_from_model(self, cloud_backend):
        """Test provider detection for various models."""
        assert cloud_backend._get_provider_from_model("gpt-4") == "openai"
        assert cloud_backend._get_provider_from_model("gpt-3.5-turbo") == "openai"
        assert cloud_backend._get_provider_from_model("claude-3-opus-20240229") == "anthropic"
        assert cloud_backend._get_provider_from_model("claude-3-sonnet-20240229") == "anthropic"
        assert cloud_backend._get_provider_from_model("gemini-pro") == "google"
        assert cloud_backend._get_provider_from_model("gemini-1.5-pro") == "google"
        assert cloud_backend._get_provider_from_model("unknown-model") == "unknown"
