"""Tests for multi-modal functionality."""

import base64
from unittest.mock import AsyncMock, Mock, patch

import pytest

from matilda_brain import AIResponse, ImageInput, ask, stream
from matilda_brain.backends import CloudBackend, LocalBackend


class TestImageInput:
    """Test the ImageInput class."""

    def test_image_from_path(self, tmp_path):
        """Test creating ImageInput from file path."""
        # Create a test image file
        image_path = tmp_path / "test.jpg"
        image_data = b"fake image data"
        image_path.write_bytes(image_data)

        img = ImageInput(str(image_path))

        assert img.is_path
        assert not img.is_url
        assert not img.is_bytes
        assert img.get_mime_type() == "image/jpeg"

        # Test base64 conversion
        expected_b64 = base64.b64encode(image_data).decode("utf-8")
        assert img.to_base64() == expected_b64

    def test_image_from_url(self):
        """Test creating ImageInput from URL."""
        url = "https://example.com/image.png"
        img = ImageInput(url)

        assert not img.is_path
        assert img.is_url
        assert not img.is_bytes
        assert img.get_mime_type() == "image/jpeg"  # Default

        # URLs should return as-is for base64
        assert img.to_base64() == url

    def test_image_from_bytes(self):
        """Test creating ImageInput from raw bytes."""
        image_data = b"raw image bytes"
        img = ImageInput(image_data, mime_type="image/png")

        assert not img.is_path
        assert not img.is_url
        assert img.is_bytes
        assert img.get_mime_type() == "image/png"

        expected_b64 = base64.b64encode(image_data).decode("utf-8")
        assert img.to_base64() == expected_b64

    def test_mime_type_inference(self, tmp_path):
        """Test MIME type inference from file extension."""
        test_cases = {
            "test.jpg": "image/jpeg",
            "test.jpeg": "image/jpeg",
            "test.png": "image/png",
            "test.gif": "image/gif",
            "test.webp": "image/webp",
            "test.bmp": "image/bmp",
            "test.unknown": "image/jpeg",  # Default
        }

        for filename, expected_mime in test_cases.items():
            path = tmp_path / filename
            path.write_bytes(b"data")
            img = ImageInput(str(path))
            assert img.get_mime_type() == expected_mime


class TestMultiModalAPI:
    """Test multi-modal API functionality."""

    def test_ask_with_image(self):
        """Test ask() with image input."""
        # Setup mock
        mock_backend = Mock()
        mock_backend.ask = AsyncMock(
            return_value=AIResponse("This is a dog", model="gpt-4-vision-preview", backend="cloud")
        )
        mock_backend.name = "mock"

        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_route.return_value = (mock_backend, "gpt-4-vision-preview")

            # Test with image
            response = ask(["What's in this image?", ImageInput("https://example.com/dog.jpg")])

            assert response == "This is a dog"
            assert response.model == "gpt-4-vision-preview"

            # Verify routing was called correctly
            mock_route.assert_called_once()
            call_args = mock_route.call_args
            assert isinstance(call_args[0][0], list)
            assert len(call_args[0][0]) == 2
            assert call_args[0][0][0] == "What's in this image?"
            assert isinstance(call_args[0][0][1], ImageInput)

    def test_stream_with_image(self):
        """Test stream() with image input."""
        # Setup mock
        mock_backend = Mock()
        mock_backend.name = "mock"

        async def mock_astream(*args, **kwargs):
            for chunk in ["This ", "is ", "a ", "cat"]:
                yield chunk

        mock_backend.astream = mock_astream

        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_route.return_value = (mock_backend, "gpt-4-vision-preview")

            # Test streaming with image
            chunks = list(stream(["Describe this image:", ImageInput(b"fake image data")]))

            assert chunks == ["This ", "is ", "a ", "cat"]


class TestCloudBackendMultiModal:
    """Test CloudBackend multi-modal support."""

    @pytest.mark.asyncio
    async def test_cloud_backend_with_images(self):
        """Test cloud backend handles images correctly."""
        class FakeLiteLLM:
            pass

        with patch.dict("sys.modules", {"litellm": FakeLiteLLM()}):
            backend = CloudBackend()

        # Mock litellm
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="A beautiful sunset", tool_calls=None))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=20)

        with patch.object(backend, "litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)

            # Test with images (using fake image bytes for testing)
            fake_image_bytes = b"fake_image_data_for_testing"
            response = await backend.ask(
                [
                    "What's in this image?",
                    ImageInput(fake_image_bytes),
                    "Is it beautiful?",
                ],
                model="gpt-4-vision-preview",
            )

            assert response == "A beautiful sunset"
            assert response.succeeded

            # Check the call was made correctly
            call_args = mock_litellm.acompletion.call_args
            messages = call_args[1]["messages"]
            assert len(messages) == 1
            assert messages[0]["role"] == "user"

            # Check content array
            content = messages[0]["content"]
            assert isinstance(content, list)
            assert len(content) == 3
            assert content[0]["type"] == "text"
            assert content[0]["text"] == "What's in this image?"
            assert content[1]["type"] == "image_url"
            assert content[2]["type"] == "text"
            assert content[2]["text"] == "Is it beautiful?"

    @pytest.mark.asyncio
    async def test_cloud_backend_image_formats(self, tmp_path):
        """Test different image input formats."""
        class FakeLiteLLM:
            pass

        with patch.dict("sys.modules", {"litellm": FakeLiteLLM()}):
            backend = CloudBackend()

        # Create test image file
        image_path = tmp_path / "test.png"
        image_data = b"test image data"
        image_path.write_bytes(image_data)

        # Mock litellm
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Response", tool_calls=None))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=20)

        with patch.object(backend, "litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)

            # Test 1: File path
            await backend.ask(["Text", ImageInput(str(image_path))])

            content = mock_litellm.acompletion.call_args[1]["messages"][0]["content"]
            assert content[1]["type"] == "image_url"
            assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")

            # Test 2: URL
            await backend.ask(["Text", ImageInput("https://example.com/image.jpg")])

            content = mock_litellm.acompletion.call_args[1]["messages"][0]["content"]
            assert content[1]["image_url"]["url"] == "https://example.com/image.jpg"

            # Test 3: Raw bytes
            await backend.ask(["Text", ImageInput(b"raw bytes", mime_type="image/gif")])

            content = mock_litellm.acompletion.call_args[1]["messages"][0]["content"]
            assert content[1]["image_url"]["url"].startswith("data:image/gif;base64,")


class TestLocalBackendMultiModal:
    """Test LocalBackend multi-modal handling."""

    @pytest.mark.asyncio
    async def test_local_backend_rejects_images(self):
        """Test local backend properly rejects image inputs."""
        from matilda_brain import MultiModalError

        backend = LocalBackend()

        # Try to use images - should raise an exception
        with pytest.raises(MultiModalError) as exc_info:
            await backend.ask(["What's in this image?", ImageInput("image.jpg")])

        assert "does not support image inputs" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_local_backend_extracts_text(self):
        """Test local backend extracts text from mixed input."""
        backend = LocalBackend()

        # Mock httpx client
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Extracted text response"}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Test with text-only items in list
            response = await backend.ask(["First part", "Second part"])

            assert response.succeeded

            # Check that text was joined
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["prompt"] == "First part Second part"


class TestRoutingMultiModal:
    """Test routing with multi-modal inputs."""

    def test_routing_detects_images(self):
        """Test router detects images and switches to cloud."""
        from matilda_brain.core.routing import Router

        router = Router()

        # Mock backends
        with patch.object(router, "get_backend") as mock_get:
            mock_cloud = Mock()
            mock_cloud.name = "cloud"
            mock_get.return_value = mock_cloud

            # Route with images
            backend, model = router.smart_route(["What's this?", ImageInput("image.jpg")])

            assert backend == mock_cloud
            assert model == "gpt-4-vision-preview"
            mock_get.assert_called_with("cloud")

    def test_routing_respects_explicit_vision_model(self):
        """Test routing respects explicit vision model selection."""
        from matilda_brain.core.routing import Router

        router = Router()

        with patch.object(router, "get_backend") as mock_get:
            mock_cloud = Mock()
            mock_cloud.name = "cloud"
            mock_get.return_value = mock_cloud

            # Route with specific vision model
            backend, model = router.smart_route("Describe this", model="gemini-pro-vision")

            assert model == "gemini-pro-vision"
            assert backend.name == "cloud"
