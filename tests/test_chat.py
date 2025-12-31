"""Tests for chat functionality including persistent sessions and streaming."""

import json
import pickle
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from matilda_brain import (
    AIResponse,
    ImageInput,
    InvalidParameterError,
    SessionLoadError,
    SessionSaveError,
    chat,
)
from matilda_brain.session.chat import PersistentChatSession, _estimate_tokens
from tests.utils import MockBackend


@pytest.fixture
def mock_backend():
    """Provide a mock backend."""
    return MockBackend(responses=["Response 1", "Response 2", "Response 3"])


@pytest.fixture
def mock_router(mock_backend):
    """Mock router to return our backend."""
    with patch("matilda_brain.core.routing.router") as mock:
        mock.smart_route.return_value = (mock_backend, "mock-model")
        mock.resolve_backend.return_value = mock_backend
        mock.resolve_model.return_value = "mock-model"
        yield mock


class TestPersistentChatSession:
    """Test the PersistentChatSession class - basic functionality."""

    def test_session_initialization(self):
        """Test creating a new persistent session."""
        session = PersistentChatSession(system="Test system prompt", model="gpt-3.5-turbo", session_id="test_123")

        assert session.system == "Test system prompt"
        assert session.model == "gpt-3.5-turbo"
        assert session.metadata["session_id"] == "test_123"
        assert len(session.history) == 0
        assert "created_at" in session.metadata

    def test_auto_session_id(self):
        """Test automatic session ID generation."""
        session = PersistentChatSession()

        assert session.metadata["session_id"] is not None
        assert session.metadata["session_id"].startswith("chat_")
        assert len(session.metadata["session_id"]) > 10

    @patch("matilda_brain.core.routing.router")
    def test_ask_updates_history(self, mock_router):
        """Test that ask() updates conversation history."""
        # Setup mock backend
        mock_backend = Mock()
        mock_backend.ask = AsyncMock(
            return_value=AIResponse(
                "Hello! Nice to meet you.",
                model="gpt-3.5-turbo",
                backend="cloud",
                tokens_in=10,
                tokens_out=20,
                cost=0.001,
            )
        )

        # Mock router to return our backend
        mock_router.resolve_backend.return_value = mock_backend

        # Create session with the mock backend directly
        session = PersistentChatSession(backend=mock_backend, model="gpt-3.5-turbo")
        session.ask("Hello, my name is Bob")

        # Check history
        assert len(session.history) == 2
        assert session.history[0]["role"] == "user"
        assert session.history[0]["content"] == "Hello, my name is Bob"
        assert "timestamp" in session.history[0]

        assert session.history[1]["role"] == "assistant"
        assert session.history[1]["content"] == "Hello! Nice to meet you."
        assert session.history[1]["model"] == "gpt-3.5-turbo"
        assert session.history[1]["tokens_in"] == 10
        assert session.history[1]["tokens_out"] == 20
        assert session.history[1]["cost"] == 0.001

    @patch("matilda_brain.core.routing.router")
    def test_metadata_tracking(self, mock_router):
        """Test that metadata is properly tracked."""
        # Setup mock backend
        mock_backend = Mock()
        mock_backend.ask = AsyncMock(
            return_value=AIResponse("Response", model="gpt-4", tokens_in=50, tokens_out=100, cost=0.01)
        )

        # Mock router to return our backend
        mock_router.resolve_backend.return_value = mock_backend

        # Create session with the mock backend directly
        session = PersistentChatSession(backend=mock_backend, model="gpt-4")

        # Make multiple requests
        session.ask("First question")
        session.ask("Second question")

        # Check metadata
        assert session.metadata["total_tokens_in"] == 100  # 50 * 2
        assert session.metadata["total_tokens_out"] == 200  # 100 * 2
        assert session.metadata["total_cost"] == 0.02  # 0.01 * 2

        # Check model usage
        assert "gpt-4" in session.metadata["model_usage"]
        assert session.metadata["model_usage"]["gpt-4"]["count"] == 2
        assert session.metadata["model_usage"]["gpt-4"]["tokens_in"] == 100
        assert session.metadata["model_usage"]["gpt-4"]["tokens_out"] == 200
        assert session.metadata["model_usage"]["gpt-4"]["cost"] == 0.02

    def test_save_json(self, tmp_path):
        """Test saving session as JSON."""
        session = PersistentChatSession(system="Test system", model="test-model", session_id="save_test")

        # Add some history
        session.history.append(
            {
                "role": "user",
                "content": "Test message",
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Save as JSON
        save_path = tmp_path / "test_session.json"
        result_path = session.save(save_path, format="json")

        assert result_path == save_path
        assert save_path.exists()

        # Verify contents
        with open(save_path) as f:
            data = json.load(f)

        assert data["version"] == "1.0"
        assert data["system"] == "Test system"
        assert data["model"] == "test-model"
        assert len(data["history"]) == 1
        assert data["metadata"]["session_id"] == "save_test"

    def test_save_pickle(self, tmp_path):
        """Test that pickle format is deprecated and saves as JSON instead."""
        import warnings

        session = PersistentChatSession(system="Test system", session_id="pickle_test")

        # Save with pickle format (should trigger deprecation warning and save as JSON)
        save_path = tmp_path / "test_session.pkl"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result_path = session.save(save_path, format="pickle")
            # Verify deprecation warning was issued
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "pickle" in str(w[0].message).lower()

        # Result path should be changed to .json
        expected_path = tmp_path / "test_session.json"
        assert result_path == expected_path
        assert expected_path.exists()
        assert not save_path.exists()  # Original .pkl path should not exist

        # Verify it's a valid JSON file
        with open(expected_path, "r") as f:
            data = json.load(f)

        assert data["version"] == "1.0"
        assert data["metadata"]["session_id"] == "pickle_test"

    def test_load_json(self, tmp_path):
        """Test loading session from JSON."""
        # Create a session file
        session_data = {
            "version": "1.0",
            "system": "Loaded system",
            "model": "loaded-model",
            "backend": "cloud",
            "history": [
                {"role": "user", "content": "Previous message"},
                {"role": "assistant", "content": "Previous response"},
            ],
            "metadata": {
                "session_id": "loaded_session",
                "created_at": datetime.now().isoformat(),
                "total_tokens_in": 100,
                "total_tokens_out": 200,
                "total_cost": 0.05,
            },
            "kwargs": {"temperature": 0.7},
        }

        save_path = tmp_path / "load_test.json"
        with open(save_path, "w") as f:
            json.dump(session_data, f)

        # Load the session
        loaded = PersistentChatSession.load(save_path)

        assert loaded.system == "Loaded system"
        assert loaded.model == "loaded-model"
        assert len(loaded.history) == 2
        assert loaded.metadata["session_id"] == "loaded_session"
        assert loaded.metadata["total_tokens_in"] == 100
        assert loaded.kwargs["temperature"] == 0.7

    def test_load_auto_format(self, tmp_path):
        """Test auto-detecting file format on load."""
        session = PersistentChatSession(session_id="auto_test")

        import warnings

        # Save as JSON with .json extension
        json_path = tmp_path / "session.json"
        session.save(json_path)

        # Load without specifying format
        loaded = PersistentChatSession.load(json_path)
        assert loaded.metadata["session_id"] == "auto_test"

        # Save with pickle format (deprecated - converts to JSON)
        pkl_path = tmp_path / "session.pkl"
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result_path = session.save(pkl_path, format="pickle")

        # The result should be a .json file (extension is changed)
        assert result_path.suffix == ".json"

        # Load the resulting JSON file
        loaded = PersistentChatSession.load(result_path)
        assert loaded.metadata["session_id"] == "auto_test"

    def test_get_summary(self):
        """Test getting session summary."""
        session = PersistentChatSession(session_id="summary_test")

        # Add some history
        session.history.extend(
            [
                {"role": "user", "content": "Question 1"},
                {"role": "assistant", "content": "Answer 1"},
                {"role": "user", "content": "Question 2"},
                {"role": "assistant", "content": "Answer 2"},
            ]
        )

        session.metadata["total_tokens_in"] = 150
        session.metadata["total_tokens_out"] = 300
        session.metadata["total_cost"] = 0.075

        summary = session.get_summary()

        assert summary["session_id"] == "summary_test"
        assert summary["message_count"] == 4
        assert summary["user_messages"] == 2
        assert summary["assistant_messages"] == 2
        assert summary["total_tokens_in"] == 150
        assert summary["total_tokens_out"] == 300
        assert summary["total_cost"] == 0.075

    def test_export_messages_text(self):
        """Test exporting messages as text."""
        session = PersistentChatSession()
        session.history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm doing well, thanks!"},
        ]

        text = session.export_messages(format="text")
        expected = "User: Hello\n\nAssistant: Hi there!\n\nUser: How are you?\n\nAssistant: I'm doing well, thanks!"
        assert text == expected

    def test_export_messages_markdown(self):
        """Test exporting messages as markdown."""
        session = PersistentChatSession()
        session.history = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
        ]

        markdown = session.export_messages(format="markdown")
        # The markdown format includes a session header and uses ### for roles
        assert markdown.startswith("# Chat Session:")
        assert "### User" in markdown
        assert "What is Python?" in markdown
        assert "### Assistant" in markdown
        assert "Python is a programming language." in markdown

    def test_export_messages_json(self):
        """Test exporting messages as JSON."""
        session = PersistentChatSession()
        session.history = [{"role": "user", "content": "Test"}]

        json_str = session.export_messages(format="json")
        data = json.loads(json_str)
        assert isinstance(data, dict)
        assert "session_id" in data
        assert "messages" in data
        assert isinstance(data["messages"], list)
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "Test"

    def test_clear_history(self):
        """Test clearing conversation history."""
        session = PersistentChatSession()
        session.history = [
            {"role": "user", "content": "Message"},
            {"role": "assistant", "content": "Response"},
        ]

        session.clear()

        assert len(session.history) == 0
        # Metadata should be preserved
        assert session.metadata["session_id"] is not None

    @patch("matilda_brain.core.routing.router")
    def test_multimodal_in_persistent_session(self, mock_router):
        """Test multi-modal content in persistent sessions."""
        from matilda_brain import ImageInput

        # Setup mock
        mock_backend = Mock()
        mock_backend.ask = AsyncMock(return_value=AIResponse("I see an image", model="gpt-4-vision-preview"))
        mock_router.smart_route.return_value = (mock_backend, "gpt-4-vision-preview")
        mock_router.resolve_backend.return_value = mock_backend

        # Create session with the mocked backend
        session = PersistentChatSession(backend=mock_backend)

        # Ask with image
        session.ask(["What's in this image?", ImageInput("test.jpg")])

        # Check history stores the multi-modal content
        assert len(session.history) == 2
        assert isinstance(session.history[0]["content"], list)
        assert len(session.history[0]["content"]) == 2
        assert session.history[0]["content"][0] == "What's in this image?"


class TestPersistentChatSessionAdvanced:
    """Advanced tests for PersistentChatSession - comprehensive functionality."""

    def test_init_with_all_parameters(self, mock_router, mock_backend):
        """Test initialization with all parameters."""
        session = PersistentChatSession(
            system="Custom system prompt",
            model="specific-model",
            backend=mock_backend,
            session_id="custom-id",
            temperature=0.7,
        )

        assert session.system == "Custom system prompt"
        assert session.model == "specific-model"
        assert session.metadata["session_id"] == "custom-id"
        assert session.kwargs["temperature"] == 0.7
        assert session.history == []
        assert "created_at" in session.metadata

    def test_auto_generate_session_id(self, mock_router):
        """Test automatic session ID generation."""
        # Need to patch the _generate_session_id method directly
        with patch.object(PersistentChatSession, "_generate_session_id") as mock_generate:
            mock_generate.return_value = "chat_20240101_120000_abcd1234"

            session = PersistentChatSession()

            assert session.metadata["session_id"] == "chat_20240101_120000_abcd1234"

    def test_ask_with_multimodal_content(self, mock_router, mock_backend):
        """Test asking with multimodal content."""
        session = PersistentChatSession(backend=mock_backend)

        response = session.ask(["What's in this image?", ImageInput("test.jpg")])

        assert str(response) == "Response 1"
        assert len(session.history) == 2

        # Check message storage
        user_msg = session.history[0]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert user_msg["content"][0] == "What's in this image?"

    def test_metadata_tracking_comprehensive(self, mock_router, mock_backend):
        """Test comprehensive metadata tracking."""
        session = PersistentChatSession(model="test-model", backend=mock_backend)

        # Make several asks to accumulate metadata
        session.ask("First question")
        session.ask("Second question", model="different-model")
        session.ask("Third question")

        metadata = session.metadata

        # Check token counts
        assert metadata["total_tokens_in"] > 0
        assert metadata["total_tokens_out"] > 0
        assert metadata["total_cost"] > 0

        # Check model usage
        assert "test-model" in metadata["model_usage"]
        assert "different-model" in metadata["model_usage"]
        assert metadata["model_usage"]["test-model"]["count"] == 2
        assert metadata["model_usage"]["different-model"]["count"] == 1

        # Check backend usage
        assert "mock" in metadata["backend_usage"]
        assert metadata["backend_usage"]["mock"]["count"] == 3

    def test_save_invalid_format(self, mock_router, mock_backend):
        """Test saving with invalid format."""
        session = PersistentChatSession(backend=mock_backend)

        with pytest.raises(InvalidParameterError) as exc_info:
            session.save("test.xml", format="xml")

        assert exc_info.value.details["parameter"] == "format"
        assert exc_info.value.details["value"] == "xml"

    def test_save_permission_error(self, mock_router, mock_backend):
        """Test handling permission errors during save."""
        session = PersistentChatSession(backend=mock_backend)

        # Try to save to a path that will fail
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with pytest.raises(SessionSaveError) as exc_info:
                session.save("/root/test.json")

        assert "Access denied" in str(exc_info.value)

    def test_load_corrupted_json(self, mock_router):
        """Test loading corrupted JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json}")
            temp_path = Path(f.name)

        try:
            with pytest.raises(SessionLoadError) as exc_info:
                PersistentChatSession.load(temp_path)

            assert "Invalid JSON" in str(exc_info.value)

        finally:
            temp_path.unlink()

    def test_export_messages_invalid_format(self, mock_router, mock_backend):
        """Test exporting with invalid format."""
        session = PersistentChatSession(backend=mock_backend)

        with pytest.raises(ValueError) as exc_info:
            session.export_messages(format="pdf")

        assert "Unknown format" in str(exc_info.value)

    def test_multimodal_metadata(self, mock_router, mock_backend):
        """Test metadata tracking with multimodal inputs."""
        session = PersistentChatSession(backend=mock_backend)

        # Ask with images
        session.ask(["First image", ImageInput("img1.jpg"), ImageInput("img2.jpg")])

        # Check metadata
        assert session.metadata["multimodal_messages"] == 1
        assert session.metadata["total_images"] == 2


class TestChatContextManager:
    """Test the chat() context manager with persistence."""

    def test_chat_always_persistent(self):
        """Test that chat() always returns PersistentChatSession."""
        with chat() as session:
            assert isinstance(session, PersistentChatSession)
            assert hasattr(session, "ask")
            assert hasattr(session, "stream")
            assert hasattr(session, "save")
            assert hasattr(session, "load")

    def test_chat_with_custom_session_id(self):
        """Test chat with custom session ID."""
        with chat(session_id="custom_123") as session:
            assert session.metadata["session_id"] == "custom_123"

    def test_save_and_resume_workflow(self, tmp_path):
        """Test the save and resume workflow."""
        save_path = tmp_path / "workflow_test.json"

        # Create and save a session
        with chat(system="Test assistant") as session:
            # Mock the backend
            with patch.object(session, "backend") as mock_backend:
                mock_backend.ask = AsyncMock(return_value=AIResponse("I'll remember that", model="test-model"))

                session.ask("Remember: The secret code is 42")
                session.save(save_path)

        # Load and continue the session
        loaded = PersistentChatSession.load(save_path)
        assert loaded.system == "Test assistant"
        assert len(loaded.history) == 2
        assert "secret code is 42" in loaded.history[0]["content"]


class TestDurationCalculation:
    """Test session duration calculation."""

    def test_duration_empty_session(self):
        """Test duration for empty session."""
        session = PersistentChatSession()
        assert session._calculate_duration() == "0m"

    def test_duration_with_timestamps(self):
        """Test duration calculation with timestamps."""
        session = PersistentChatSession()

        # Set creation time
        session.metadata["created_at"] = "2024-01-01T10:00:00"

        # Add messages with timestamps
        session.history = [
            {"role": "user", "content": "Hi", "timestamp": "2024-01-01T10:00:00"},
            {
                "role": "assistant",
                "content": "Hello",
                "timestamp": "2024-01-01T10:05:00",
            },
            {"role": "user", "content": "Bye", "timestamp": "2024-01-01T10:30:00"},
            {
                "role": "assistant",
                "content": "Goodbye",
                "timestamp": "2024-01-01T11:15:00",
            },
        ]

        duration = session._calculate_duration()
        assert duration == "1h 15m"

    def test_duration_multi_day(self):
        """Test duration calculation across days."""
        session = PersistentChatSession()

        session.metadata["created_at"] = "2024-01-01T10:00:00"
        session.history = [
            {"role": "user", "content": "Start", "timestamp": "2024-01-01T10:00:00"},
            {"role": "assistant", "content": "End", "timestamp": "2024-01-03T14:30:00"},
        ]

        duration = session._calculate_duration()
        assert duration == "2d 4h 30m"

    def test_duration_with_iso_timestamps(self, mock_router, mock_backend):
        """Test duration calculation with ISO timestamps."""
        session = PersistentChatSession(backend=mock_backend)

        # Set specific timestamps for created_at and add message with specific timestamp
        start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 10, 30, 45, tzinfo=timezone.utc)

        session.metadata["created_at"] = start.isoformat()
        # Add a message with specific timestamp
        session.history.append({"role": "user", "content": "test message", "timestamp": end.isoformat()})

        summary = session.get_summary()

        # Should be 30.75 minutes (30 minutes and 45 seconds)
        assert abs(summary["duration_minutes"] - 30.75) < 0.01

    def test_duration_with_datetime_objects(self, mock_router, mock_backend):
        """Test duration calculation with one hour duration."""
        session = PersistentChatSession(backend=mock_backend)

        # Set created_at and add message with 1 hour difference
        start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)

        session.metadata["created_at"] = start.isoformat()
        # Add a message with specific timestamp
        session.history.append({"role": "user", "content": "test message", "timestamp": end.isoformat()})

        summary = session.get_summary()

        assert summary["duration_minutes"] == 60.0


class TestTokenEstimation:
    """Test token estimation functionality."""

    def test_estimate_tokens_text(self):
        """Test token estimation for text."""
        # Estimate is len(text) // 4
        assert _estimate_tokens("Hello world") == len("Hello world") // 4  # 11 // 4 = 2
        assert (
            _estimate_tokens("This is a longer sentence with more words")
            == len("This is a longer sentence with more words") // 4
        )

    def test_estimate_tokens_multimodal(self):
        """Test token estimation for multimodal content."""
        content = ["What's in this image?", ImageInput("test.jpg")]

        # Should estimate text tokens + fixed amount for image
        tokens = _estimate_tokens(content)
        assert tokens > 50  # Images add significant tokens

    def test_estimate_tokens_empty(self):
        """Test token estimation for empty input."""
        assert _estimate_tokens("") == 0
        assert _estimate_tokens([]) == 0
