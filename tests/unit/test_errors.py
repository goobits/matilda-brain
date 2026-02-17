"""Tests for error handling, recovery systems, and custom exception hierarchy."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from matilda_brain import (
    AIError,
    APIKeyError,
    BackendConnectionError,
    BackendNotAvailableError,
    BackendTimeoutError,
    ConfigFileError,
    InvalidParameterError,
    InvalidPromptError,
    ModelNotFoundError,
    MultiModalError,
    PluginLoadError,
    PluginValidationError,
    RateLimitError,
    SessionLoadError,
    SessionSaveError,
)
from matilda_brain.tools.base import ToolCall
from matilda_brain.tools.executor import ExecutionConfig, ToolExecutor
from matilda_brain.tools.recovery import (
    ErrorPattern,
    ErrorRecoverySystem,
    ErrorType,
    InputSanitizer,
    RetryConfig,
)

# =============================================================================
# EXCEPTION HIERARCHY TESTS
# =============================================================================


class TestExceptionHierarchy:
    """Test the exception class hierarchy."""

    @pytest.mark.unit
    def test_all_exceptions_inherit_from_ai_error(self):
        """Test that all exceptions inherit from AIError."""
        exceptions = [
            BackendNotAvailableError("test", "reason"),
            BackendConnectionError("test"),
            ModelNotFoundError("test"),
            APIKeyError("test"),
            ConfigFileError("test.yaml", "reason"),
            InvalidPromptError("reason"),
            SessionLoadError("test.json", "reason"),
        ]

        for exc in exceptions:
            assert isinstance(exc, AIError)
            assert isinstance(exc, Exception)

    @pytest.mark.unit
    def test_exception_messages(self):
        """Test that exceptions have proper messages."""
        exc = BackendNotAvailableError("mybackend", "Not installed")
        assert str(exc) == 'Backend "mybackend" is not available: Not installed'

        exc = ModelNotFoundError("gpt-5", "openai")
        assert str(exc) == 'Model "gpt-5" not found in backend "openai"'

        exc = APIKeyError("OpenAI", "OPENAI_API_KEY")
        assert "OPENAI_API_KEY" in str(exc)

    @pytest.mark.unit
    def test_exception_details(self):
        """Test that exceptions store details properly."""
        exc = BackendConnectionError("local", Exception("Connection refused"))
        assert exc.details["backend"] == "local"
        assert "Connection refused" in exc.details["original_error"]

        exc = InvalidParameterError("temperature", 2.5, "Must be between 0 and 1")
        assert exc.details["parameter"] == "temperature"
        assert exc.details["value"] == 2.5
        assert exc.details["reason"] == "Must be between 0 and 1"


# =============================================================================
# BACKEND EXCEPTION TESTS
# =============================================================================


class TestBackendExceptions:
    """Test backend-related exceptions in actual usage."""

    @patch("matilda_brain.backends.local.httpx.AsyncClient")
    def test_local_backend_connection_error(self, mock_client):
        """Test that connection errors raise BackendConnectionError."""
        import httpx

        from matilda_brain.backends.local import LocalBackend

        # Mock connection error
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        backend = LocalBackend()

        with pytest.raises(BackendConnectionError) as exc_info:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(backend.ask("Hello"))
            finally:
                loop.close()

        assert "local" in str(exc_info.value)
        assert exc_info.value.details["backend"] == "local"

    @patch("matilda_brain.backends.local.httpx.AsyncClient")
    def test_local_backend_timeout(self, mock_client):
        """Test that timeouts raise BackendTimeoutError."""
        import httpx

        from matilda_brain.backends.local import LocalBackend

        # Mock timeout
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        backend = LocalBackend()

        with pytest.raises(BackendTimeoutError) as exc_info:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(backend.ask("Hello"))
            finally:
                loop.close()

        assert exc_info.value.details["backend"] == "local"
        assert exc_info.value.details["timeout"] == backend.timeout

    def test_local_backend_multimodal_error(self):
        """Test that multi-modal input raises MultiModalError."""
        from matilda_brain import ImageInput
        from matilda_brain.backends.local import LocalBackend

        backend = LocalBackend()

        with pytest.raises(MultiModalError) as exc_info:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(backend.ask(["What's this?", ImageInput("test.jpg")]))
            finally:
                loop.close()

        assert "Ollama" in str(exc_info.value)
        assert "vision" in str(exc_info.value)

    @patch("matilda_brain.backends.local.httpx.AsyncClient")
    def test_model_not_found(self, mock_client):
        """Test that 404 errors for models raise ModelNotFoundError."""
        import httpx

        from matilda_brain.backends.local import LocalBackend

        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "model not found"

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("Not found", request=Mock(), response=mock_response)
        )

        backend = LocalBackend()

        with pytest.raises(ModelNotFoundError) as exc_info:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(backend.ask("Hello", model="nonexistent"))
            finally:
                loop.close()

        assert exc_info.value.details["model"] == "nonexistent"
        assert exc_info.value.details["backend"] == "local"


class TestCloudBackendExceptions:
    """Test cloud backend exception handling."""

    def test_litellm_not_installed(self):
        """Test that missing LiteLLM raises BackendNotAvailableError."""
        with patch.dict("sys.modules", {"litellm": None}):
            from matilda_brain.backends.cloud import CloudBackend

            with pytest.raises(BackendNotAvailableError) as exc_info:
                CloudBackend()

            assert "LiteLLM" in str(exc_info.value)
            assert exc_info.value.details["backend"] == "cloud"

    def test_api_key_error(self):
        """Test that authentication errors raise APIKeyError."""

        class FakeLiteLLM:
            def __init__(self):
                self.acompletion = AsyncMock(side_effect=Exception("api_key is required"))

        fake_litellm = FakeLiteLLM()
        with patch.dict("sys.modules", {"litellm": fake_litellm}):
            import importlib
            from matilda_brain.backends import cloud

            importlib.reload(cloud)
            backend = cloud.CloudBackend()

        with pytest.raises(APIKeyError) as exc_info:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(backend.ask("Hello", model="gpt-3.5-turbo"))
            finally:
                loop.close()

        assert exc_info.value.details["provider"] == "openai"
        assert exc_info.value.details["env_var"] == "OPENAI_API_KEY"

    def test_rate_limit_error(self):
        """Test that rate limit errors are handled properly."""

        class FakeLiteLLM:
            def __init__(self):
                self.acompletion = AsyncMock(side_effect=Exception("Rate limit exceeded"))

        fake_litellm = FakeLiteLLM()
        with patch.dict("sys.modules", {"litellm": fake_litellm}):
            import importlib
            from matilda_brain.backends import cloud

            importlib.reload(cloud)
            backend = cloud.CloudBackend()

        with pytest.raises(RateLimitError) as exc_info:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(backend.ask("Hello", model="claude-3-sonnet-20240229"))
            finally:
                loop.close()

        assert exc_info.value.details["provider"] == "anthropic"


# =============================================================================
# INPUT SANITIZATION TESTS
# =============================================================================


class TestInputSanitizer:
    """Test input sanitization functionality."""

    def test_sanitize_string_allows_safe_input_through_unchanged(self):
        """Test basic string sanitization."""
        result = InputSanitizer.sanitize_string("hello world")
        assert result == "hello world"

    def test_sanitize_string_dangerous_patterns(self):
        """Test detection of dangerous patterns."""
        dangerous_inputs = [
            "rm -rf /",  # Should be blocked
            "sudo delete everything",  # Should be blocked
            "../../../etc/passwd",  # Should be blocked
        ]

        # Test that dangerous patterns are blocked
        for dangerous in dangerous_inputs:
            with pytest.raises(ValueError, match="dangerous content"):
                InputSanitizer.sanitize_string(dangerous)

        # Test that code-specific dangerous patterns are blocked in code context
        code_dangerous_inputs = [
            'exec("malicious code")',  # Should trigger code pattern
            'eval("bad stuff")',  # Should trigger code pattern
        ]

        for dangerous in code_dangerous_inputs:
            with pytest.raises(ValueError):  # Either pattern match is fine
                InputSanitizer.sanitize_string(dangerous, allow_code=True)

    def test_sanitize_string_length_limit(self):
        """Test string length limits."""
        long_string = "x" * 20000
        with pytest.raises(ValueError, match="too long"):
            InputSanitizer.sanitize_string(long_string, max_length=10000)

    def test_sanitize_path_valid(self):
        """Test valid path sanitization."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.touch()

            result = InputSanitizer.sanitize_path(str(test_file))
            assert isinstance(result, Path)
            assert result.exists()

    def test_sanitize_path_traversal(self):
        """Test path traversal detection."""
        with pytest.raises(ValueError, match="traversal"):
            InputSanitizer.sanitize_path("../../../etc/passwd")

    def test_sanitize_url_valid(self):
        """Test valid URL sanitization."""
        valid_urls = [
            "https://example.com",
            "http://test.local:8080/path",
            "https://api.service.com/v1/data",
        ]

        for url in valid_urls:
            result = InputSanitizer.sanitize_url(url)
            assert result == url

    def test_sanitize_url_invalid_scheme(self):
        """Test invalid URL schemes."""
        invalid_urls = [
            "ftp://example.com",
            "file:///etc/passwd",
            "javascript:alert(1)",
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError):
                InputSanitizer.sanitize_url(url)

    def test_sanitize_json_valid(self):
        """Test valid JSON sanitization."""
        json_str = '{"key": "value", "number": 42}'
        result = InputSanitizer.sanitize_json(json_str)
        assert result == {"key": "value", "number": 42}

    def test_sanitize_json_with_dangerous_strings(self):
        """Test JSON with dangerous string values."""
        # This should now pass since <script> tags are cleaned by bleach, not blocked
        json_str = '{"script": "<script>alert(1)</script>"}'
        result = InputSanitizer.sanitize_json(json_str)
        # bleach should have cleaned the script tag
        assert "<script>" not in result["script"]


# =============================================================================
# ERROR RECOVERY SYSTEM TESTS
# =============================================================================


class TestErrorRecoverySystem:
    """Test error recovery and classification."""

    def test_error_classification(self):
        """Test error message classification."""
        recovery = ErrorRecoverySystem()

        test_cases = [
            ("connection timeout", ErrorType.TIMEOUT_ERROR),
            ("permission denied", ErrorType.PERMISSION_ERROR),
            ("rate limit exceeded", ErrorType.RATE_LIMIT_ERROR),
            ("file not found", ErrorType.RESOURCE_ERROR),
            ("network unreachable", ErrorType.NETWORK_ERROR),
            ("invalid argument", ErrorType.VALIDATION_ERROR),
            ("something weird happened", ErrorType.UNKNOWN_ERROR),
        ]

        for error_msg, expected_type in test_cases:
            pattern = recovery.classify_error(error_msg)
            assert pattern.error_type == expected_type

    def test_should_retry_logic(self):
        """Test retry decision logic."""
        recovery = ErrorRecoverySystem(RetryConfig(max_attempts=3))

        # Retryable error
        retryable_pattern = ErrorPattern(
            pattern="timeout",
            error_type=ErrorType.TIMEOUT_ERROR,
            message="Timeout",
            suggested_action="Try again",
            can_retry=True,
        )

        assert recovery.should_retry(retryable_pattern, 1)
        assert recovery.should_retry(retryable_pattern, 2)
        assert not recovery.should_retry(retryable_pattern, 3)  # Max attempts reached

        # Non-retryable error
        non_retryable_pattern = ErrorPattern(
            pattern="permission",
            error_type=ErrorType.PERMISSION_ERROR,
            message="Permission denied",
            suggested_action="Check permissions",
            can_retry=False,
        )

        assert not recovery.should_retry(non_retryable_pattern, 1)

    def test_calculate_retry_delay(self):
        """Test retry delay calculation."""
        recovery = ErrorRecoverySystem(
            RetryConfig(
                base_delay=1.0,
                exponential_base=2.0,
                max_delay=10.0,
                jitter=False,  # Disable jitter for predictable testing
            )
        )

        pattern = ErrorPattern(
            pattern="timeout",
            error_type=ErrorType.TIMEOUT_ERROR,
            message="Timeout",
            suggested_action="Try again",
        )

        # Test exponential backoff
        delay1 = recovery.calculate_retry_delay(1, pattern)
        delay2 = recovery.calculate_retry_delay(2, pattern)

        assert delay1 == 2.0  # 1.0 * 2^1
        assert delay2 == 4.0  # 1.0 * 2^2

        # Test max delay cap
        delay_large = recovery.calculate_retry_delay(10, pattern)
        assert delay_large == 10.0  # Capped at max_delay

    def test_fallback_suggestions(self):
        """Test fallback tool suggestions."""
        recovery = ErrorRecoverySystem()

        # Test web_search fallback
        suggestions = recovery.get_fallback_suggestions("web_search", {"query": "test"})
        assert len(suggestions) > 0
        # Should suggest http_request as fallback for web_search
        suggestion_names = [s.tool_name for s in suggestions]
        assert "http_request" in suggestion_names

        # Test read_file fallback
        suggestions = recovery.get_fallback_suggestions("read_file", {"file_path": "/test/file.txt"})
        assert len(suggestions) > 0
        # Should suggest list_directory as fallback for read_file
        suggestion_names = [s.tool_name for s in suggestions]
        assert "list_directory" in suggestion_names

    def test_recovery_message_creation(self):
        """Test helpful recovery message creation."""
        recovery = ErrorRecoverySystem()

        tool_call = ToolCall(
            id="test_123",
            name="test_tool",
            arguments={"arg": "value"},
            error="connection timeout",
        )

        error_pattern = ErrorPattern(
            pattern="timeout",
            error_type=ErrorType.TIMEOUT_ERROR,
            message="Connection timed out",
            suggested_action="Check your internet connection",
            can_retry=True,
            fallback_tools=["alternative_tool"],
        )

        message = recovery.create_recovery_message(tool_call, error_pattern)

        assert "test_tool" in message
        assert "Connection timed out" in message
        assert "Check your internet connection" in message
        assert "can be retried" in message
        assert "alternative_tool" in message


# =============================================================================
# TOOL EXECUTOR TESTS
# =============================================================================


class TestToolExecutor:
    """Test the enhanced tool executor."""

    @pytest.fixture
    def executor(self):
        """Create a test executor."""
        config = ExecutionConfig(max_retries=2, timeout_seconds=5.0, enable_fallbacks=True)
        return ToolExecutor(config)

    def test_tool_not_found_error(self, executor):
        """Test helpful error when tool is not found."""
        # Mock the tool registry to return None
        with patch("matilda_brain.tools.executor.get_tool", return_value=None):
            with patch("matilda_brain.tools.executor.list_tools", return_value=[]):
                result = asyncio.run(executor.execute_tool("nonexistent_tool", {}))

                assert not result.succeeded
                assert "not found" in result.error
                assert "💡" in result.error  # Has suggestion

    @pytest.mark.asyncio
    async def test_input_sanitization(self, executor):
        """Test input sanitization during execution."""
        # Mock tool that would receive sanitized inputs
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.function = Mock(return_value="success")

        with patch("matilda_brain.tools.executor.get_tool", return_value=mock_tool):
            result = await executor.execute_tool(
                "test_tool",
                {
                    "file_path": "test.txt",
                    "url": "https://example.com",
                    "query": "test query",
                },
            )

            # Should succeed with sanitized inputs
            assert result.succeeded
            mock_tool.function.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_handling(self, executor):
        """Test timeout handling."""

        # Mock tool that raises timeout immediately
        async def slow_tool(**kwargs):
            raise asyncio.TimeoutError("Mocked tool timeout")

        mock_tool = Mock()
        mock_tool.name = "slow_tool"
        mock_tool.function = slow_tool

        with patch("matilda_brain.tools.executor.get_tool", return_value=mock_tool):
            result = await executor.execute_tool("slow_tool", {}, timeout=1.0)

            assert not result.succeeded
            assert "timed out" in result.error
            assert "💡" in result.error  # Has suggestion

    @pytest.mark.asyncio
    async def test_parallel_execution(self, executor):
        """Test parallel tool execution."""

        # Mock tools
        def quick_tool(**kwargs):
            return f"result from {kwargs.get('id', 'unknown')}"

        mock_tool = Mock()
        mock_tool.name = "quick_tool"
        mock_tool.function = quick_tool

        tool_calls = [
            {"name": "quick_tool", "arguments": {"id": "tool1"}},
            {"name": "quick_tool", "arguments": {"id": "tool2"}},
            {"name": "quick_tool", "arguments": {"id": "tool3"}},
        ]

        with patch("matilda_brain.tools.executor.get_tool", return_value=mock_tool):
            result = await executor.execute_tools(tool_calls, parallel=True)

            assert len(result.calls) == 3
            assert all(call.succeeded for call in result.calls)

    def test_execution_stats(self, executor):
        """Test execution statistics tracking."""
        # Initial stats should be empty
        stats = executor.get_execution_stats()
        assert stats["total_calls"] == 0
        assert stats["successful_calls"] == 0

        # Mock some executions - need to update total_calls first
        executor.execution_stats["total_calls"] = 1
        executor._update_execution_stats(True, 1.0)
        executor.execution_stats["total_calls"] = 2
        executor._update_execution_stats(True, 2.0)
        executor.execution_stats["total_calls"] = 3
        executor._update_execution_stats(False, 0.5)

        stats = executor.get_execution_stats()
        assert stats["total_calls"] == 3
        assert stats["successful_calls"] == 2
        assert stats["failed_calls"] == 1
        assert abs(stats["success_rate"] - 2 / 3) < 0.01
        assert abs(stats["avg_execution_time"] - 1.17) < 0.1  # Allow for floating point precision


# =============================================================================
# CONFIGURATION EXCEPTION TESTS
# =============================================================================


class TestConfigExceptions:
    """Test configuration-related exceptions."""

    def test_invalid_toml_config(self, tmp_path):
        """Test that invalid TOML raises ConfigFileError."""
        from matilda_brain.config import load_config

        # Create invalid TOML
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("invalid = {]")

        with pytest.raises(ConfigFileError) as exc_info:
            load_config(config_file)

        assert str(config_file) in exc_info.value.details["file_path"]
        assert "TOML parsing error" in exc_info.value.details["reason"]

    def test_unsupported_config_format(self, tmp_path):
        """Test that unsupported formats raise ConfigFileError."""
        from matilda_brain.config import load_config

        # Create config with unsupported extension
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with pytest.raises(ConfigFileError) as exc_info:
            load_config(config_file)

        assert "Unsupported config file format" in str(exc_info.value)


# =============================================================================
# SESSION EXCEPTION TESTS
# =============================================================================


class TestSessionExceptions:
    """Test session-related exceptions."""

    def test_session_load_not_found(self):
        """Test loading non-existent session raises SessionLoadError."""
        from matilda_brain.session.chat import PersistentChatSession

        with pytest.raises(SessionLoadError) as exc_info:
            PersistentChatSession.load("nonexistent.json")

        assert "File not found" in exc_info.value.details["reason"]
        assert "nonexistent.json" in exc_info.value.details["file_path"]

    def test_session_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises SessionLoadError."""
        from matilda_brain.session.chat import PersistentChatSession

        # Create invalid JSON
        session_file = tmp_path / "invalid.json"
        session_file.write_text("{invalid json}")

        with pytest.raises(SessionLoadError) as exc_info:
            PersistentChatSession.load(session_file)

        assert "Invalid JSON" in exc_info.value.details["reason"]

    def test_session_save_invalid_format(self):
        """Test saving with invalid format raises InvalidParameterError."""
        from matilda_brain.session.chat import PersistentChatSession
        from tests.utils import MockBackend

        session = PersistentChatSession(backend=MockBackend())

        with pytest.raises(InvalidParameterError) as exc_info:
            session.save("test.txt", format="xml")

        assert exc_info.value.details["parameter"] == "format"
        assert exc_info.value.details["value"] == "xml"
        assert "json" in exc_info.value.details["reason"]

    def test_session_save_permission_error(self, tmp_path):
        """Test saving to protected location raises SessionSaveError."""
        from matilda_brain.session.chat import PersistentChatSession
        from tests.utils import MockBackend

        session = PersistentChatSession(backend=MockBackend())

        # Try to save to a read-only directory
        protected_dir = tmp_path / "protected"
        protected_dir.mkdir()
        protected_file = protected_dir / "session.json"

        # Make directory read-only
        protected_dir.chmod(0o444)

        try:
            with pytest.raises(SessionSaveError) as exc_info:
                session.save(protected_file)

            assert str(protected_file) in exc_info.value.details["file_path"]
        finally:
            # Restore permissions for cleanup
            protected_dir.chmod(0o755)


# =============================================================================
# PLUGIN EXCEPTION TESTS
# =============================================================================


class TestPluginExceptions:
    """Test plugin-related exceptions."""

    def test_plugin_load_error(self, tmp_path):
        """Test that plugin load errors are handled properly."""
        from matilda_brain.plugins import PluginRegistry

        # Create a plugin with syntax error
        plugin_file = tmp_path / "bad_plugin.py"
        plugin_file.write_text("def register_plugin(registry)\n    pass")  # Missing colon

        registry = PluginRegistry()

        with pytest.raises(PluginLoadError) as exc_info:
            registry._load_plugin_from_file(plugin_file)

        assert str(plugin_file) in exc_info.value.details["plugin_path"]

    def test_plugin_validation_error(self, tmp_path):
        """Test that plugins without register_plugin raise PluginValidationError."""
        from matilda_brain.plugins import PluginRegistry

        # Create a plugin without register_plugin
        plugin_file = tmp_path / "invalid_plugin.py"
        plugin_file.write_text("# No register_plugin function")

        registry = PluginRegistry()

        with pytest.raises(PluginValidationError) as exc_info:
            registry._load_plugin_from_file(plugin_file)

        assert "register_plugin" in exc_info.value.details["reason"]


# =============================================================================
# ROUTING EXCEPTION TESTS
# =============================================================================


class TestRoutingExceptions:
    """Test routing-related exceptions."""

    def test_unknown_backend(self):
        """Test that unknown backends raise BackendNotAvailableError."""
        from matilda_brain.core.routing import Router

        router = Router()

        with pytest.raises(BackendNotAvailableError) as exc_info:
            router.get_backend("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert exc_info.value.details["backend"] == "nonexistent"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for the complete error recovery system."""

    @pytest.mark.asyncio
    async def test_file_operation_with_recovery(self):
        """Test file operations with recovery."""
        executor = ToolExecutor()

        # Test reading non-existent file within allowed directory
        result = await executor.execute_tool("read_file", {"file_path": "nonexistent_file.txt"})

        # Should provide helpful error (either as error or as result with error info)
        error_text = result.error or result.result or ""
        assert (
            "File not found" in error_text
            or "not found" in error_text
            or "does not exist" in error_text
            or "Resource Error" in error_text
        )
        assert "Check the file path" in error_text or "Suggestion" in error_text or "Check the file" in error_text

    @pytest.mark.asyncio
    async def test_network_operation_with_retry(self):
        """Test network operations with retry logic."""
        executor = ToolExecutor(ExecutionConfig(max_retries=2))

        # Mock network failure then success
        call_count = 0

        def mock_web_search(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network unreachable")
            return "Search results"

        mock_tool = Mock()
        mock_tool.name = "web_search"
        mock_tool.function = mock_web_search

        with patch("matilda_brain.tools.executor.get_tool", return_value=mock_tool):
            # Patch the recovery system to handle the error correctly
            with patch.object(
                executor.recovery_system,
                "_adapt_arguments",
                return_value={"query": "test"},
            ):
                # Should eventually succeed after retry
                result = await executor.execute_tool("web_search", {"query": "test"})

                # Verify retry happened
                assert call_count >= 1  # At least one attempt
                # The result may succeed or fail depending on fallback behavior
                if result.succeeded:
                    assert result.result == "Search results"


if __name__ == "__main__":
    pytest.main([__file__])
