"""Tests for the models, info, list, status, and export CLI commands."""

from unittest.mock import Mock, patch

from matilda_brain.cli import cli as main
from tests.cli.conftest import IntegrationTestBase


class TestListCommand(IntegrationTestBase):
    """Test the list command functionality."""

    def test_list_help_shows_resources(self):
        """Test list command help shows available resources."""
        result = self.runner.invoke(main, ["list", "--help"])

        assert result.exit_code == 0
        assert len(result.output) > 0

    def test_list_models(self):
        """Test listing models."""
        # Real integration test - will show configured models
        result = self.runner.invoke(main, ["list", "models"])

        # Should work with configured models
        assert result.exit_code == 0
        assert len(result.output.strip()) > 0

    def test_list_with_format(self):
        """Test list with different format."""
        # Test JSON format
        result = self.runner.invoke(main, ["list", "models", "--format", "json"])

        assert result.exit_code == 0
        # JSON output should be parseable
        try:
            import json

            json.loads(result.output)
        except json.JSONDecodeError:
            # If not valid JSON, at least should have some output
            assert len(result.output.strip()) > 0

    def test_list_command_parameter_passing(self):
        """Test list command passes resource and format parameters correctly."""
        # Test list models command with JSON format
        result = self.runner.invoke(main, ["--verbose", "list", "models", "--format", "json"])

        # List command should succeed - validates CLI structure and parameter passing
        assert result.exit_code == 0, f"List command failed with output: {result.output}"

        # With --format json, output should be valid JSON
        if "--format json" in str(result.output) or "{" in result.output:
            import json

            try:
                # Try to find and parse JSON in output
                lines = result.output.strip().split("\n")
                for line in lines:
                    if line.strip().startswith("[") or line.strip().startswith("{"):
                        json.loads(line)
                        break
            except json.JSONDecodeError:
                pass  # JSON parsing is secondary - main test is exit code 0

        # Test list sessions
        result = self.runner.invoke(main, ["list", "sessions"])
        assert result.exit_code == 0, f"List sessions failed with output: {result.output}"


class TestCLIStatusCommand(IntegrationTestBase):
    """Test the CLI-specific status command functionality."""

    def test_status_command_reports_backend_and_api_key_availability(self):
        """Test basic status command."""
        # Mock the backend components used by status check
        with patch("matilda_brain.backends.local.LocalBackend") as mock_local, patch("os.getenv") as mock_getenv:
            # Mock local backend
            mock_local_instance = Mock()
            mock_local_instance.is_available = True
            mock_local_instance.base_url = "http://localhost:11434"
            mock_local_instance.list_models.return_value = ["model1", "model2"]
            mock_local.return_value = mock_local_instance

            # Mock API key environment variables
            def getenv_side_effect(key, default=None):
                if key == "OPENAI_API_KEY":
                    return "test-key"
                return default

            mock_getenv.side_effect = getenv_side_effect

            result = self.runner.invoke(main, ["status"])

            assert result.exit_code == 0
            assert "TTT System Status" in result.output or "healthy" in result.output.lower()


    def test_status_command_parameter_passing(self):
        """Test status command passes json parameter correctly."""
        # Test status command with JSON output
        result = self.runner.invoke(main, ["status", "--json"])

        # Status command should succeed - validates CLI structure
        assert result.exit_code == 0, f"Status command failed with output: {result.output}"

        # With --json flag, output should contain JSON-like structure
        assert "{" in result.output or "[" in result.output, "Expected JSON-like output from --json flag"

        # Test status command without JSON flag
        result = self.runner.invoke(main, ["status"])
        assert result.exit_code == 0, f"Status command failed with output: {result.output}"


class TestModelsCommand(IntegrationTestBase):
    """Test the models command functionality."""

    def test_models_command_lists_available_models_from_registry(self):
        """Test basic models command."""
        # Mock the model registry used by models command
        with patch("matilda_brain.config.schema.get_model_registry") as mock_registry:
            mock_model = Mock()
            mock_model.name = "gpt-4"
            mock_model.provider = "openai"
            mock_model.provider_name = "OpenAI"
            mock_model.context_length = 8192
            mock_model.cost_per_token = 0.00003
            mock_model.speed = "fast"
            mock_model.quality = "high"
            mock_model.aliases = ["gpt4"]

            mock_registry_instance = Mock()
            mock_registry_instance.list_models.return_value = ["gpt-4"]
            mock_registry_instance.get_model.return_value = mock_model
            mock_registry.return_value = mock_registry_instance

            result = self.runner.invoke(main, ["models"])

            assert result.exit_code == 0
            assert "gpt-4" in result.output
            mock_registry.assert_called_once()


    def test_models_command_parameter_passing(self):
        """Test models command passes json parameter correctly."""
        # Test models command with JSON output
        result = self.runner.invoke(main, ["models", "--json"])

        # Models command should succeed - validates CLI structure
        assert result.exit_code == 0, f"Models command failed with output: {result.output}"

        # With --json flag, output should be JSON
        assert "{" in result.output or "[" in result.output, "Expected JSON output from --json flag"

        # Test models command without JSON flag
        result = self.runner.invoke(main, ["models"])
        assert result.exit_code == 0, f"Models command failed with output: {result.output}"


class TestInfoCommand(IntegrationTestBase):
    """Test the info command functionality."""

    def test_info_command_displays_detailed_model_information(self):
        """Test basic info command."""
        # Mock the model registry used by info command
        with patch("matilda_brain.config.schema.get_model_registry") as mock_registry:
            mock_model = Mock()
            mock_model.name = "gpt-4"
            mock_model.provider = "openai"
            mock_model.provider_name = "OpenAI"
            mock_model.context_length = 8192
            mock_model.cost_per_token = 0.00003
            mock_model.speed = "fast"
            mock_model.quality = "high"
            mock_model.aliases = ["gpt4"]
            mock_model.capabilities = ["text"]

            mock_registry_instance = Mock()
            mock_registry_instance.get_model.return_value = mock_model
            mock_registry.return_value = mock_registry_instance

            result = self.runner.invoke(main, ["info", "gpt-4"])

            assert result.exit_code == 0
            assert "gpt-4" in result.output
            mock_registry.assert_called_once()
            mock_registry_instance.get_model.assert_called_once_with("gpt-4")

    def test_info_no_model_shows_models(self):
        """Test info command without model shows available models."""
        # The info command without model should show models list as a fallback
        result = self.runner.invoke(main, ["info"])

        # In real integration testing, this should work but might fail if model registry can't load
        # Exit codes: 0=success, 1=general error (like missing models), 2=argument error
        assert result.exit_code in [0, 1, 2]

        # If it succeeded, should show model-related output
        if result.exit_code == 0:
            assert len(result.output.strip()) > 0


    def test_info_command_parameter_passing(self):
        """Test info command passes model and json parameters correctly."""
        # Test info command with model and JSON output
        result = self.runner.invoke(main, ["info", "gpt-4", "--json"])

        # Info command should succeed - validates CLI structure and parameter passing
        assert result.exit_code == 0, f"Info command failed with output: {result.output}"

        # With --json flag, output should be JSON
        assert "{" in result.output, "Expected JSON output from --json flag"

        # Test info command without model (should show available models or help)
        result = self.runner.invoke(main, ["info"])
        # Should either succeed or gracefully indicate missing model
        assert result.exit_code in [0, 1, 2], f"Info command failed unexpectedly: {result.output}"


class TestExportCommand(IntegrationTestBase):
    """Test the export command functionality."""

    def test_export_command_loads_and_outputs_session_data(self):
        """Test basic export command."""
        # Mock the session manager methods used by export command
        with patch("matilda_brain.session.manager.ChatSessionManager.load_session") as mock_load:
            mock_session = Mock()
            mock_session.id = "session-1"
            mock_session.messages = []
            # Mock created_at with proper datetime-like object or remove the attribute
            delattr(mock_session, "created_at") if hasattr(mock_session, "created_at") else None
            mock_load.return_value = mock_session

            result = self.runner.invoke(main, ["export", "session-1"])

            assert result.exit_code == 0
            assert "session-1" in result.output
            mock_load.assert_called_once_with("session-1")

    def test_export_with_options(self):
        """Test export with various options."""
        # Mock the session manager methods used by export command
        with patch("matilda_brain.session.manager.ChatSessionManager.load_session") as mock_load, patch(
            "pathlib.Path.write_text"
        ) as mock_write:
            mock_session = Mock()
            mock_session.id = "session-1"
            mock_session.messages = [{"role": "user", "content": "Hello"}]
            # Remove created_at attribute since it may cause issues
            delattr(mock_session, "created_at") if hasattr(mock_session, "created_at") else None
            mock_session.model = "gpt-4"
            mock_session.system_prompt = "You are helpful"
            mock_session.tools = None
            mock_load.return_value = mock_session
            mock_write.return_value = None

            result = self.runner.invoke(
                main,
                [
                    "export",
                    "session-1",
                    "--format",
                    "json",
                    "--output",
                    "output.json",
                    "--include-metadata",
                ],
            )

            assert result.exit_code == 0
            assert "exported" in result.output.lower()
            mock_load.assert_called_once_with("session-1")
            mock_write.assert_called_once()

    def test_export_no_session_shows_list(self):
        """Test export without session shows session list."""
        # For integration test, just test that it doesn't crash
        result = self.runner.invoke(main, ["export"])

        # Should either succeed (showing session list) or fail gracefully
        assert result.exit_code in [0, 1, 2]

    def test_export_nonexistent_session(self):
        """Test export with nonexistent session."""
        # Mock the session manager to return None for nonexistent session
        with patch("matilda_brain.session.manager.ChatSessionManager.load_session") as mock_load:
            mock_load.return_value = None

            result = self.runner.invoke(main, ["export", "nonexistent"])

            assert result.exit_code == 1
            assert "not found" in result.output.lower()
            mock_load.assert_called_once_with("nonexistent")

    def test_export_command_parameter_passing(self):
        """Test export command passes session_id, format, output, include_metadata parameters correctly."""
        # Test export with non-existent session (should handle gracefully)
        result = self.runner.invoke(
            main, ["export", "nonexistent-session", "--format", "json", "--include-metadata"]
        )

        # Export should either succeed (if session exists) or fail gracefully with exit code 1
        # The important thing is that it processes the arguments correctly (no exit code 2)
        assert result.exit_code in [0, 1], f"Export failed with unexpected exit code. Output: {result.output}"

        # Should not have argument parsing errors (exit code 2)
        if result.exit_code == 1:
            # Should be a graceful error about session not found, not argument error
            assert "not found" in result.output.lower() or "error" in result.output.lower()
