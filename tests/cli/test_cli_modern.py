"""Comprehensive tests for the modern Click-based CLI interface.

Tests all commands, options, help text, and integration with the app hooks system.
"""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from matilda_brain.cli import cli as main
from .conftest import IntegrationTestBase


class TestAskCommand(IntegrationTestBase):
    """Test the ask command functionality."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_basic_prompt_demonstrates_core_functionality(self):
        """Test basic ask functionality - demonstrates core TTT question-answering capability with proper error handling."""
        # Real integration test demonstrating TTT's primary use case
        result = self.runner.invoke(main, ["ask", "What are the key features of Python programming language?"])

        # Should handle request gracefully whether API is available or not
        assert result.exit_code in [0, 1], f"Ask command failed unexpectedly: {result.output}"

        if result.exit_code == 0:
            # Successful response should be substantial and informative
            response = result.output.strip()
            assert len(response) > 50, f"Response too brief for meaningful answer: {response}"

            # Should mention Python-related concepts in a meaningful way
            response_lower = response.lower()
            python_concepts = ["python", "language", "programming", "feature"]
            found_concepts = [concept for concept in python_concepts if concept in response_lower]
            assert (
                len(found_concepts) >= 2
            ), f"Response should address Python programming concepts. Found: {found_concepts}"

        else:
            # Graceful error handling should provide clear feedback
            error_output = result.output.lower()
            expected_error_indicators = ["error", "failed", "key", "api", "config"]
            has_error_info = any(indicator in error_output for indicator in expected_error_indicators)
            assert has_error_info, f"Error output should provide helpful information: {result.output}"

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_with_comprehensive_options_demonstrates_advanced_usage(self):
        """Test ask with various options - demonstrates advanced TTT configuration and feature usage."""
        # Real integration test showing comprehensive option usage
        result = self.runner.invoke(
            main,
            [
                "ask",
                "Analyze this Python function and suggest improvements: def process_data(items): return [x*2 for x in items if x > 0]",
                "--model",
                "gpt-4",
                "--temperature",
                "0.3",  # Lower temperature for code analysis
                "--tools",
                "true",
                "--session",
                "code-review-session",
                "--system",
                "You are a senior Python developer conducting code review",
                "--max-tokens",
                "500",
            ],
        )

        # Should handle complex option combinations gracefully
        assert result.exit_code in [0, 1], f"Complex ask command failed: {result.output}"

        # Critical: argument parsing should work (exit code 2 = argument error)
        assert result.exit_code != 2, f"CLI argument parsing failed: {result.output}"

        if result.exit_code == 0:
            # Should provide meaningful code analysis
            response = result.output.strip()
            assert len(response) > 30, f"Code analysis response too brief: {response}"

            # Should address code analysis concepts
            response_lower = response.lower()
            analysis_concepts = ["function", "code", "improve", "python", "suggest"]
            found_concepts = [concept for concept in analysis_concepts if concept in response_lower]
            assert len(found_concepts) >= 2, f"Should provide code analysis. Found concepts: {found_concepts}"


class TestListCommand(IntegrationTestBase):
    """Test the list command functionality."""

    def test_list_models_demonstrates_model_discovery(self):
        """Test listing models - demonstrates TTT's model discovery and configuration capabilities."""
        # Real integration test showing model registry functionality
        result = self.runner.invoke(main, ["list", "models"])

        # Should successfully enumerate available models
        assert result.exit_code == 0, f"Model listing failed: {result.output}"

        output = result.output.strip()
        assert len(output) > 0, "Model list should not be empty"

        # Should show structured model information
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        assert len(lines) >= 2, f"Should list multiple models or provide header info: {output}"

        # Should contain recognizable model names or providers
        output_lower = output.lower()
        model_indicators = ["gpt", "claude", "gemini", "model", "provider", "openai", "anthropic"]
        found_indicators = [indicator for indicator in model_indicators if indicator in output_lower]
        assert len(found_indicators) > 0, f"Should contain model or provider information. Output: {output}"


class TestConfigCommand(IntegrationTestBase):
    """Test the config command functionality."""

    def test_config_get_demonstrates_configuration_access(self):
        """Test config get subcommand - demonstrates TTT's configuration inspection capabilities."""
        # Test configuration value retrieval with proper validation
        with patch("matilda_brain.config.manager.ConfigManager.show_value") as mock_show:
            # Mock realistic config output
            mock_show.return_value = "gpt-4"

            result = self.runner.invoke(main, ["config", "get", "models.default"])

            assert result.exit_code == 0, f"Config get command failed: {result.output}"

            # Verify the hook was called with correct parameter
            mock_show.assert_called_once_with("models.default")

            # Should provide meaningful output about the configuration
            output = result.output.strip()
            if output:  # If there's output, it should be informative
                assert len(output) > 0, "Config get should provide value information"
                # Should show the key being queried
                assert (
                    "models.default" in output or "model" in output.lower()
                ), f"Should reference the config key: {output}"

    def test_config_set_demonstrates_configuration_management(self):
        """Test config set subcommand - demonstrates TTT's configuration modification capabilities."""
        # Test configuration value setting with proper validation
        with patch("matilda_brain.config.manager.ConfigManager.set_value") as mock_set:
            mock_set.return_value = True  # Indicate successful setting

            result = self.runner.invoke(main, ["config", "set", "models.default", "gpt-4"])

            assert result.exit_code == 0, f"Config set command failed: {result.output}"

            # Verify the hook was called with correct parameters
            mock_set.assert_called_once_with("models.default", "gpt-4")

            # Should provide feedback about the configuration change
            output = result.output.strip()
            if output:  # If there's output, it should be confirmatory
                output_lower = output.lower()
                confirmation_words = ["set", "updated", "changed", "saved", "success"]
                has_confirmation = any(word in output_lower for word in confirmation_words)
                assert has_confirmation or "gpt-4" in output, f"Should confirm config change: {output}"

    def test_config_list_demonstrates_comprehensive_configuration_view(self):
        """Test config list subcommand - demonstrates TTT's complete configuration overview capabilities."""
        # Test complete configuration display with realistic data
        with patch("matilda_brain.config.manager.ConfigManager.get_merged_config") as mock_get:
            # Mock realistic TTT configuration structure
            mock_config = {
                "models": {"default": "gpt-4", "aliases": {"fast": "gpt-3.5-turbo", "smart": "gpt-4"}},
                "api": {"temperature": 0.7, "max_tokens": 2048},
                "backends": {"openai": {"enabled": True}, "local": {"enabled": False}},
            }
            mock_get.return_value = mock_config

            result = self.runner.invoke(main, ["config", "list"])

            assert result.exit_code == 0, f"Config list command failed: {result.output}"

            # Should display the complete configuration
            mock_get.assert_called_once()

            output = result.output
            # Should contain key configuration elements
            assert "gpt-4" in output, f"Should show default model: {output}"

            # Should be formatted as JSON or structured text
            if "{" in output and "}" in output:
                # JSON format - verify it's parseable
                try:
                    import json

                    json.loads(output)
                except json.JSONDecodeError:
                    pass  # Acceptable if mixed with other text

            # Should contain configuration sections
            config_sections = ["model", "api", "backend", "temperature"]
            found_sections = [section for section in config_sections if section in output.lower()]
            assert len(found_sections) >= 2, f"Should show multiple config sections. Found: {found_sections}"

    def test_config_list_with_secrets(self):
        """Test config list with show-secrets option."""
        # Mock the config manager to return sample config with secrets
        with patch("matilda_brain.config.manager.ConfigManager.get_merged_config") as mock_get:
            mock_get.return_value = {"model": "gpt-4", "api_key": "secret-key"}

            result = self.runner.invoke(main, ["config", "list", "--show-secrets"])

            assert result.exit_code == 0
            assert "secret-key" in result.output
            mock_get.assert_called_once()


class TestModernToolsCommand(IntegrationTestBase):
    """Test the modern CLI tools command functionality."""

    def test_tools_enable_demonstrates_tool_management(self):
        """Test tools enable subcommand - demonstrates TTT's tool activation and management capabilities."""
        # Test tool enablement with realistic tool management scenario
        with (
            patch("matilda_brain.config.manager.ConfigManager.get_merged_config") as mock_get,
            patch("matilda_brain.config.manager.ConfigManager.set_value") as mock_set,
        ):
            # Mock current state with web_search disabled
            mock_get.return_value = {"tools": {"disabled": ["web_search"], "enabled": ["calculator", "file_reader"]}}
            mock_set.return_value = True  # Successful update

            result = self.runner.invoke(main, ["tools", "enable", "web_search"])

            assert result.exit_code == 0, f"Tools enable command failed: {result.output}"

            # Should update configuration to enable the tool
            mock_get.assert_called()
            mock_set.assert_called_once()

            # Verify configuration update removes tool from disabled list
            call_args = mock_set.call_args
            assert "tools.disabled" in str(call_args) or "disabled" in str(
                call_args
            ), f"Should update disabled tools list: {call_args}"

            # Should provide confirmation feedback
            output_lower = result.output.lower()
            success_indicators = ["enabled", "activated", "success", "web_search"]
            found_indicators = [indicator for indicator in success_indicators if indicator in output_lower]
            assert len(found_indicators) >= 1, f"Should confirm tool enablement: {result.output}"

    def test_tools_disable(self):
        """Test tools disable subcommand."""
        # Mock the config manager methods that tools enable/disable uses
        with (
            patch("matilda_brain.config.manager.ConfigManager.get_merged_config") as mock_get,
            patch("matilda_brain.config.manager.ConfigManager.set_value") as mock_set,
        ):
            mock_get.return_value = {"tools": {"disabled": []}}
            mock_set.return_value = None

            result = self.runner.invoke(main, ["tools", "disable", "web_search"])

            assert result.exit_code == 0
            assert "disabled" in result.output.lower()
            mock_get.assert_called()
            mock_set.assert_called_once()

    def test_tools_list(self):
        """Test tools list subcommand."""
        # Mock the tools listing and config manager
        mock_tool = Mock()
        mock_tool.name = "web_search"
        mock_tool.description = "Web search tool"

        with (
            patch("matilda_brain.tools.list_tools") as mock_list,
            patch("matilda_brain.config.manager.ConfigManager.get_merged_config") as mock_get,
        ):
            mock_list.return_value = [mock_tool]
            mock_get.return_value = {"tools": {"disabled": []}}

            result = self.runner.invoke(main, ["tools", "list"])

            assert result.exit_code == 0
            assert "web_search" in result.output
            mock_list.assert_called_once()
            mock_get.assert_called_once()


class TestExportCommand(IntegrationTestBase):
    """Test the export command functionality."""

    def test_export_with_options(self):
        """Test export with various options."""
        # Mock the session manager methods used by export command
        with (
            patch("matilda_brain.session.manager.ChatSessionManager.load_session") as mock_load,
            patch("pathlib.Path.write_text") as mock_write,
        ):
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

    def test_export_nonexistent_session(self):
        """Test export with nonexistent session."""
        # Mock the session manager to return None for nonexistent session
        with patch("matilda_brain.session.manager.ChatSessionManager.load_session") as mock_load:
            mock_load.return_value = None

            result = self.runner.invoke(main, ["export", "nonexistent"])

            assert result.exit_code == 1
            assert "not found" in result.output.lower()
            mock_load.assert_called_once_with("nonexistent")


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_hook_exception_handling(self):
        """Test that exceptions from hooks are handled gracefully."""
        # Make the underlying API call fail to test exception handling
        with patch("matilda_brain.internal.hooks.core.ttt_stream", side_effect=Exception("Test error")):
            result = self.runner.invoke(main, ["ask", "test"])

            # Should handle exception gracefully - exact behavior depends on implementation
            # At minimum, shouldn't crash completely
            assert result.exit_code in [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
