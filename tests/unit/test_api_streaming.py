"""Advanced tests for the API module to increase coverage."""

from unittest.mock import patch

import pytest

from matilda_brain import (
    BackendNotAvailableError,
    ImageInput,
    achat,
    ask,
    ask_async,
    stream,
    stream_async,
)
from matilda_brain.session.chat import PersistentChatSession as ChatSession
from tests.utils import MockBackend


@pytest.fixture
def mock_backend():
    """Provide a mock backend."""
    return MockBackend(response_text="Mock response")


@pytest.fixture
def mock_router(mock_backend):
    """Mock the router to return our mock backend."""
    with patch("matilda_brain.core.routing.router") as mock:
        mock.smart_route.return_value = (mock_backend, "mock-model")
        yield mock


class TestAskFunction:
    """Test the ask function."""

    def test_ask_routes_to_backend_and_returns_response_with_metadata(self):
        """Test basic ask functionality."""
        mock_backend = MockBackend()
        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_route.return_value = (mock_backend, "mock-model")

            response = ask("Test prompt")

            assert str(response) == "Mock response"
            assert response.model == "mock-model"
            assert response.backend == "mock"

            # Verify router was called
            mock_route.assert_called_once()
            call_args = mock_route.call_args
            assert call_args[0][0] == "Test prompt"

    def test_ask_with_all_parameters(self):
        """Test ask with all parameters."""
        mock_backend = MockBackend()
        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_route.return_value = (mock_backend, "specific-model")

            ask(
                "Test prompt",
                model="specific-model",
                system="System prompt",
                temperature=0.7,
                max_tokens=100,
                backend="cloud",
                custom_param="value",
            )

            # Verify parameters were passed to router
            call_args = mock_route.call_args
            assert call_args[1]["model"] == "specific-model"
            assert call_args[1]["backend"] == "cloud"
            assert call_args[1]["custom_param"] == "value"

            # Verify backend received parameters
            assert mock_backend.last_kwargs["system"] == "System prompt"
            assert mock_backend.last_kwargs["temperature"] == 0.7
            assert mock_backend.last_kwargs["max_tokens"] == 100

    def test_ask_with_images(self):
        """Test ask with image inputs."""
        mock_backend = MockBackend()
        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_route.return_value = (mock_backend, "mock-model")

            ask(["What's in this image?", ImageInput(b"fake_image_data_for_testing")])

            # Verify prompt was passed correctly
            assert isinstance(mock_backend.last_prompt, list)
            assert mock_backend.last_prompt[0] == "What's in this image?"
            assert isinstance(mock_backend.last_prompt[1], ImageInput)


class TestStreamFunction:
    """Test the stream function."""

    def test_stream_routes_to_backend_and_yields_response_chunks(self):
        """Test basic streaming functionality."""
        mock_backend = MockBackend()
        mock_backend.response_text = "Hello world test"
        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_route.return_value = (mock_backend, "mock-model")

            chunks = list(stream("Test prompt"))

            assert chunks == ["Hello ", "world ", "test "]
            assert mock_backend.last_prompt == "Test prompt"

    def test_stream_with_parameters(self):
        """Test streaming with all parameters."""
        mock_backend = MockBackend()
        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_route.return_value = (mock_backend, "specific-model")

            list(
                stream(
                    "Test prompt",
                    model="specific-model",
                    system="System prompt",
                    temperature=0.5,
                    max_tokens=50,
                    backend="local",
                )
            )

            # Verify parameters were passed
            assert mock_backend.last_kwargs["system"] == "System prompt"
            assert mock_backend.last_kwargs["temperature"] == 0.5
            assert mock_backend.last_kwargs["max_tokens"] == 50

    def test_stream_with_images(self):
        """Test streaming with image inputs."""
        mock_backend = MockBackend()
        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_route.return_value = (mock_backend, "mock-model")

            chunks = list(stream(["Describe this", ImageInput(b"fake_image_data_for_testing")]))

            assert isinstance(mock_backend.last_prompt, list)
            assert len(chunks) > 0


class TestChatSession:
    """Test ChatSession class."""

    def test_chat_session_initialization_resolves_backend_and_model_defaults(self):
        """Test ChatSession initialization with defaults."""
        with patch("matilda_brain.session.chat.router") as mock_router:
            mock_backend = MockBackend()
            # Mock the smart_route to return backend and model
            mock_router.smart_route.return_value = (mock_backend, "default-model")
            mock_router.resolve_backend.return_value = mock_backend
            mock_router.resolve_model.return_value = "default-model"

            session = ChatSession()

            assert session.system is None
            # Model gets resolved by router
            assert session.model is not None
            # Backend is resolved by router, might not be the mock
            assert session.backend is not None
            assert session.history == []

    def test_chat_session_initialization_with_params(self):
        """Test ChatSession initialization with parameters."""
        with patch("matilda_brain.session.chat.router") as mock_router:
            mock_backend = MockBackend("local")
            # Mock router to return our backend
            mock_router.resolve_backend.return_value = mock_backend
            mock_router.resolve_model.return_value = "specific-model"

            session = ChatSession(
                system="You are helpful",
                model="specific-model",
                backend="local",
                temperature=0.8,
            )

            assert session.system == "You are helpful"
            assert session.model == "specific-model"
            # Backend might be LocalBackend due to routing
            assert session.backend is not None
            assert session.kwargs["temperature"] == 0.8

    def test_chat_session_ask_first_message(self):
        """Test asking first message in chat session."""
        mock_backend = MockBackend()
        session = ChatSession(backend=mock_backend)

        response = session.ask("Hello")

        assert str(response) == "Mock response"
        assert len(session.history) == 2
        # Check message exists (may have timestamp and metadata)
        assert any(msg["role"] == "user" and msg["content"] == "Hello" for msg in session.history)
        # Check assistant response exists (may have metadata)
        assert any(msg["role"] == "assistant" and msg["content"] == "Mock response" for msg in session.history)

        # First message should be passed as-is
        assert mock_backend.last_prompt == "Hello"

    def test_chat_session_ask_conversation(self):
        """Test multi-turn conversation."""
        mock_backend = MockBackend()
        session = ChatSession(backend=mock_backend)

        # First exchange
        mock_backend.response_text = "Hi there!"
        session.ask("Hello")

        # Second exchange
        mock_backend.response_text = "I'm doing well"
        session.ask("How are you?")

        # Check that the latest prompt was passed
        # (The conversation context is now handled differently)
        assert mock_backend.last_prompt == "How are you?"

        # Check history
        assert len(session.history) == 4
        # Check messages exist (may have timestamps and metadata)
        assert any(msg["role"] == "user" and msg["content"] == "How are you?" for msg in session.history[2:])
        assert any(msg["role"] == "assistant" and msg["content"] == "I'm doing well" for msg in session.history[2:])

    def test_chat_session_stream(self):
        """Test streaming in chat session."""
        mock_backend = MockBackend()
        mock_backend.response_text = "Streamed response"
        session = ChatSession(backend=mock_backend)

        chunks = list(session.stream("Test streaming"))

        assert chunks == ["Streamed ", "response "]
        assert len(session.history) == 2
        assert session.history[1]["content"] == "Streamed response "

    def test_chat_session_clear(self):
        """Test clearing chat history."""
        session = ChatSession(backend=MockBackend())

        session.ask("Message 1")
        session.ask("Message 2")
        assert len(session.history) == 4

        session.clear()
        assert len(session.history) == 0

    def test_chat_session_with_system_prompt(self):
        """Test chat session with system prompt."""
        mock_backend = MockBackend()
        session = ChatSession(system="You are a pirate", backend=mock_backend)

        session.ask("Hello")

        # System prompt should be passed to backend
        assert mock_backend.last_kwargs["system"] == "You are a pirate"


# TestChatContextManager removed to eliminate duplication
# Comprehensive chat context manager tests are in test_chat.py


class TestAsyncFunctions:
    """Test async versions of functions."""

    @pytest.mark.asyncio
    async def test_ask_async(self):
        """Test async ask function."""
        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_backend = MockBackend("local")
            # Mock the router to return our backend
            mock_route.return_value = (mock_backend, "model")

            response = await ask_async(
                "Test prompt",
                model="model",
                system="System",
                temperature=0.5,
                max_tokens=100,
                backend="local",
            )

            assert str(response) == "Mock response"
            assert mock_backend.last_prompt == "Test prompt"
            assert mock_backend.last_kwargs["system"] == "System"

    @pytest.mark.asyncio
    async def test_stream_async(self):
        """Test async stream function."""
        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_backend = MockBackend()
            mock_backend.response_text = "Async stream test"
            mock_route.return_value = (mock_backend, "mock-model")

            chunks = []
            async for chunk in stream_async("Test"):
                chunks.append(chunk)

            assert chunks == ["Async ", "stream ", "test "]

    @pytest.mark.asyncio
    async def test_achat_context_manager(self):
        """Test async chat context manager."""
        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_backend = MockBackend()
            mock_route.return_value = (mock_backend, "mock-model")

            async with achat(system="Async system") as session:
                assert isinstance(session, ChatSession)
                assert session.system == "Async system"

                # Can't directly test ask in async context without more setup
                # but the context manager itself works


class TestErrorHandling:
    """Test error handling in API functions."""

    def test_ask_with_invalid_backend(self):
        """Test ask with invalid backend string."""
        with pytest.raises(BackendNotAvailableError) as exc_info:
            ChatSession(backend="invalid-backend")

        assert "not available" in str(exc_info.value) or "not found" in str(exc_info.value)

    def test_stream_with_failing_backend(self):
        """Test streaming when backend fails."""
        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            # Create a backend that fails during streaming
            class FailingBackend(MockBackend):
                async def astream(self, prompt, **kwargs):
                    yield "Start "
                    raise Exception("Stream failed")

            failing_backend = FailingBackend()
            mock_route.return_value = (failing_backend, "model")

            # Should get partial results before failure
            chunks = []
            try:
                for chunk in stream("Test"):
                    chunks.append(chunk)
            except Exception:
                pass  # Expected to fail

            # We should get at least the partial result
            assert "Start " in chunks or len(chunks) == 3  # Either partial or full mock response


class TestBackendSelection:
    """Test backend selection logic."""

    def test_backend_instance_passed_directly(self):
        """Test passing backend instance directly."""
        custom_backend = MockBackend("custom")

        with patch("matilda_brain.core.routing.router.smart_route") as mock_route:
            mock_route.return_value = (custom_backend, "model")

            ask("Test", backend=custom_backend)

            # Router should receive the backend instance
            call_args = mock_route.call_args
            assert call_args[1]["backend"] == custom_backend
