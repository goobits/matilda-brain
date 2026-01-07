"""Tests for stateless TTT functionality."""

import json
import pytest
from unittest.mock import Mock, patch

from matilda_brain.internal.stateless import StatelessRequest, StatelessResponse, execute_stateless
from matilda_brain.core.api import stateless
from matilda_brain.core.models import AIResponse


class TestStatelessRequest:
    """Test StatelessRequest dataclass."""

    def test_minimal_request(self):
        """Test creating request with only required fields."""
        req = StatelessRequest(message="Hello")
        assert req.message == "Hello"
        assert req.system is None
        assert req.history == []
        assert req.tools is None
        assert req.model is None
        assert req.temperature == 0.7
        assert req.max_tokens == 2048
        assert req.timeout == 30

    def test_full_request(self):
        """Test creating request with all fields."""
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        req = StatelessRequest(
            message="What's the weather?",
            system="You are a helpful assistant",
            history=history,
            tools=["web_search"],
            model="gpt-4",
            temperature=0.5,
            max_tokens=1000,
            timeout=60,
        )
        assert req.message == "What's the weather?"
        assert req.system == "You are a helpful assistant"
        assert req.history == history
        assert req.tools == ["web_search"]
        assert req.model == "gpt-4"
        assert req.temperature == 0.5
        assert req.max_tokens == 1000
        assert req.timeout == 60


class TestStatelessResponse:
    """Test StatelessResponse dataclass."""

    def test_minimal_response(self):
        """Test creating response with only required fields."""
        resp = StatelessResponse(content="Hello!")
        assert resp.content == "Hello!"
        assert resp.tool_calls is None
        assert resp.finish_reason == "stop"
        assert resp.usage is None
        assert resp.model is None

    def test_full_response(self):
        """Test creating response with all fields."""
        resp = StatelessResponse(
            content="The weather is sunny",
            tool_calls=[{"name": "web_search", "args": {"query": "weather"}}],
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            model="gpt-4",
        )
        assert resp.content == "The weather is sunny"
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0]["name"] == "web_search"
        assert resp.finish_reason == "stop"
        assert resp.usage["prompt_tokens"] == 10
        assert resp.model == "gpt-4"


class TestExecuteStateless:
    """Test execute_stateless function."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock backend."""
        backend = Mock()

        # Create a mock AIResponse with all needed attributes
        ai_response = Mock(spec=AIResponse)
        ai_response.content = "Test response"
        ai_response.model = "test-model"
        ai_response.finish_reason = "stop"
        ai_response.usage = {"prompt_tokens": 5, "completion_tokens": 10}
        ai_response.tool_calls = None

        # Make str() work
        ai_response.__str__ = Mock(return_value="Test response")

        async def mock_ask(*args, **kwargs):
            return ai_response

        backend.ask = mock_ask
        return backend, ai_response

    @pytest.mark.unit
    def test_basic_request(self, mock_backend):
        """Test basic stateless request."""
        backend, ai_response = mock_backend

        with patch("matilda_brain.internal.stateless.router") as mock_router:
            mock_router.smart_route.return_value = (backend, "test-model")

            req = StatelessRequest(message="Hello")
            response = execute_stateless(req)

            assert response.content == "Test response"
            assert response.finish_reason == "stop"
            assert response.model == "test-model"
            assert response.usage["prompt_tokens"] == 5

    @pytest.mark.unit
    def test_request_with_system_prompt(self, mock_backend):
        """Test request with system prompt."""
        backend, ai_response = mock_backend

        with patch("matilda_brain.internal.stateless.router") as mock_router:
            mock_router.smart_route.return_value = (backend, "test-model")

            req = StatelessRequest(
                message="What is Python?", system="You are a programming expert"
            )
            response = execute_stateless(req)

            assert response.content == "Test response"

    @pytest.mark.unit
    def test_request_with_history(self, mock_backend):
        """Test request with conversation history."""
        backend, ai_response = mock_backend

        with patch("matilda_brain.internal.stateless.router") as mock_router:
            mock_router.smart_route.return_value = (backend, "test-model")

            history = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ]
            req = StatelessRequest(
                message="What was my first message?", history=history
            )
            response = execute_stateless(req)

            assert response.content == "Test response"

    @pytest.mark.unit
    def test_request_with_tools(self, mock_backend):
        """Test request with tools enabled."""
        backend, ai_response = mock_backend

        with patch("matilda_brain.internal.stateless.router") as mock_router:
            mock_router.smart_route.return_value = (backend, "test-model")

            req = StatelessRequest(
                message="Search for Python tutorials", tools=["web_search"]
            )
            response = execute_stateless(req)

            assert response.content == "Test response"

    @pytest.mark.unit
    def test_request_with_custom_params(self, mock_backend):
        """Test request with custom temperature and max_tokens."""
        backend, ai_response = mock_backend

        with patch("matilda_brain.internal.stateless.router") as mock_router:
            mock_router.smart_route.return_value = (backend, "test-model")

            req = StatelessRequest(
                message="Test", temperature=0.9, max_tokens=500, model="gpt-4"
            )
            response = execute_stateless(req)

            assert response.content == "Test response"


class TestStatelessAPI:
    """Test the stateless() API function."""

    @pytest.fixture
    def mock_execute(self):
        """Mock execute_stateless."""
        # Patch the import in the stateless module where it's actually used
        with patch("matilda_brain.internal.stateless.execute_stateless") as mock:
            mock.return_value = StatelessResponse(
                content="API test response",
                finish_reason="stop",
                model="test-model",
            )
            yield mock

    @pytest.mark.unit
    def test_api_basic_call(self, mock_execute):
        """Test basic API call."""
        response = stateless("Hello")

        assert response.content == "API test response"
        assert response.finish_reason == "stop"
        assert response.model == "test-model"

        # Verify execute_stateless was called
        assert mock_execute.called
        call_args = mock_execute.call_args[0][0]
        assert call_args.message == "Hello"
        assert call_args.system is None
        assert call_args.history == []

    @pytest.mark.unit
    def test_api_with_system(self, mock_execute):
        """Test API call with system prompt."""
        response = stateless("What is AI?", system="You are an expert")

        assert response.content == "API test response"

        call_args = mock_execute.call_args[0][0]
        assert call_args.message == "What is AI?"
        assert call_args.system == "You are an expert"

    @pytest.mark.unit
    def test_api_with_history(self, mock_execute):
        """Test API call with history."""
        history = [{"role": "user", "content": "Hi"}]
        response = stateless("Continue", history=history)

        assert response.content == "API test response"

        call_args = mock_execute.call_args[0][0]
        assert call_args.history == history

    @pytest.mark.unit
    def test_api_with_tools(self, mock_execute):
        """Test API call with tools."""
        response = stateless("Search", tools=["web_search"])

        assert response.content == "API test response"

        call_args = mock_execute.call_args[0][0]
        assert call_args.tools == ["web_search"]

    @pytest.mark.unit
    def test_api_with_all_params(self, mock_execute):
        """Test API call with all parameters."""
        response = stateless(
            "Complex query",
            system="Expert",
            history=[{"role": "user", "content": "Hi"}],
            tools=["web_search"],
            model="gpt-4",
            temperature=0.8,
            max_tokens=1000,
        )

        assert response.content == "API test response"

        call_args = mock_execute.call_args[0][0]
        assert call_args.message == "Complex query"
        assert call_args.system == "Expert"
        assert call_args.model == "gpt-4"
        assert call_args.temperature == 0.8
        assert call_args.max_tokens == 1000


class TestStatelessCLI:
    """Test CLI integration (requires app_hooks)."""

    @pytest.mark.unit
    def test_cli_hook_exists(self):
        """Test that on_stateless hook exists."""
        from matilda_brain.app_hooks import on_stateless

        assert callable(on_stateless)

    @pytest.mark.unit
    def test_history_file_format(self, tmp_path):
        """Test history file loading."""
        # Create a test history file
        history_file = tmp_path / "history.json"
        history_data = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        history_file.write_text(json.dumps(history_data))

        # Verify file is readable
        with open(history_file) as f:
            loaded = json.load(f)
        assert len(loaded) == 2
        assert loaded[0]["role"] == "user"

    @pytest.mark.unit
    def test_history_file_with_wrapper(self, tmp_path):
        """Test history file with messages wrapper."""
        history_file = tmp_path / "history_wrapped.json"
        history_data = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ]
        }
        history_file.write_text(json.dumps(history_data))

        # Verify file is readable
        with open(history_file) as f:
            loaded = json.load(f)
        assert "messages" in loaded
        assert len(loaded["messages"]) == 2


class TestNoSessionFiles:
    """Test that stateless execution creates NO session files."""

    @pytest.mark.unit
    def test_no_session_files_created(self, tmp_path, monkeypatch):
        """Verify that stateless execution doesn't create session files."""
        # Set session directory to temp path
        monkeypatch.setenv("TTT_SESSION_DIR", str(tmp_path))

        # Mock backend
        backend = Mock()

        # Create a proper mock AIResponse
        ai_response = Mock(spec=AIResponse)
        ai_response.content = "Test"
        ai_response.finish_reason = "stop"
        ai_response.usage = None
        ai_response.tool_calls = None
        ai_response.model = "test-model"
        ai_response.__str__ = Mock(return_value="Test")

        async def mock_ask(*args, **kwargs):
            return ai_response

        backend.ask = mock_ask

        with patch("matilda_brain.internal.stateless.router") as mock_router:
            mock_router.smart_route.return_value = (backend, "test-model")

            # Execute stateless request
            req = StatelessRequest(message="Test message")
            response = execute_stateless(req)

            # Verify response
            assert response.content == "Test"

            # Verify no files were created in session directory
            session_files = list(tmp_path.glob("*.json"))
            assert len(session_files) == 0, f"Session files created: {session_files}"
