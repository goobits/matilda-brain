"""Tests for the local backend."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from matilda_brain.backends.local import LocalBackend


@pytest.fixture
def local_backend():
    """Create a LocalBackend instance for testing."""
    return LocalBackend(
        {
            "timeout": 30,
            "local": {
                "base_url": "http://localhost:11434",
                "default_model": "test-model",
            },
        }
    )


class TestLocalBackend:
    """Test LocalBackend class."""

    def test_initialization(self, local_backend):
        """Test backend initialization."""
        assert local_backend.name == "local"
        assert local_backend.base_url == "http://localhost:11434"
        assert local_backend.default_model == "test-model"
        assert local_backend.timeout == 30

    @pytest.mark.asyncio
    async def test_ask_returns_response_from_ollama_api(self, local_backend):
        """Test successful ask request."""
        mock_response_data = {
            "response": "Test response",
            "eval_count": 50,
            "prompt_eval_count": 20,
            "eval_duration": 1000000000,
            "load_duration": 500000000,
            "total_duration": 2000000000,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await local_backend.ask("Test prompt")

            assert str(result) == "Test response"
            assert result.model == "test-model"
            assert result.backend == "local"
            assert result.tokens_in == 20
            assert result.tokens_out == 50
            assert result.time_taken > 0
            assert not result.failed

    @pytest.mark.asyncio
    async def test_ask_with_options(self, local_backend):
        """Test ask with optional parameters."""
        mock_response_data = {"response": "Test response"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            await local_backend.ask(
                "Test prompt",
                model="custom-model",
                system="Test system",
                temperature=0.7,
                max_tokens=100,
            )

            # Check that the request was made with correct parameters
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            request_data = call_args[1]["json"]

            assert request_data["model"] == "custom-model"
            assert request_data["prompt"] == "Test prompt"
            assert request_data["system"] == "Test system"
            assert request_data["options"]["temperature"] == 0.7
            assert request_data["options"]["num_predict"] == 100

    @pytest.mark.asyncio
    async def test_ask_http_error(self, local_backend):
        """Test ask with HTTP error."""
        from matilda_brain import ModelNotFoundError

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.text = "Model not found"

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=mock_response)
            )

            with pytest.raises(ModelNotFoundError) as exc_info:
                await local_backend.ask("Test prompt")

            assert exc_info.value.details["model"] == "test-model"
            assert exc_info.value.details["backend"] == "local"

    @pytest.mark.asyncio
    async def test_astream_yields_chunks_from_ollama_streaming(self, local_backend):
        """Test successful streaming request."""
        mock_lines = [
            '{"response": "Hello", "done": false}',
            '{"response": " world", "done": false}',
            '{"response": "!", "done": true}',
        ]

        async def mock_aiter_lines():
            for line in mock_lines:
                yield line

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.aiter_lines = mock_aiter_lines
            mock_response.raise_for_status = MagicMock()

            mock_stream = MagicMock()
            mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream.__aexit__ = AsyncMock(return_value=None)

            mock_client.return_value.__aenter__.return_value.stream = MagicMock(return_value=mock_stream)

            chunks = []
            async for chunk in local_backend.astream("Test prompt"):
                chunks.append(chunk)

            assert chunks == ["Hello", " world", "!"]

    @pytest.mark.asyncio
    async def test_models_lists_available_ollama_models(self, local_backend):
        """Test successful models listing."""
        mock_response_data = {"models": [{"name": "llama2"}, {"name": "codellama"}, {"name": "mistral"}]}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            models = await local_backend.models()

            assert models == ["llama2", "codellama", "mistral"]

    @pytest.mark.asyncio
    async def test_models_error(self, local_backend):
        """Test models listing with error."""
        from matilda_brain import BackendConnectionError

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("Connection failed"))

            with pytest.raises(BackendConnectionError) as exc_info:
                await local_backend.models()

            assert exc_info.value.details["backend"] == "local"
            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_status(self, local_backend):
        """Test status method."""
        with patch.object(local_backend, "models", return_value=["model1", "model2"]):
            with patch.object(local_backend, "ais_available", new=AsyncMock(return_value=True)):
                status = await local_backend.status()

                assert status["backend"] == "local"
                assert status["base_url"] == "http://localhost:11434"
                assert status["available"] is True
                assert status["models_count"] == 2
                assert status["default_model"] == "test-model"
