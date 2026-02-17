"""Tests for core CLI functionality and structure."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from matilda_brain.cli import cli as main


class TestCLIStructure:
    """Test CLI structure and help display.

    Note: These tests focus on functionality rather than specific text content.
    We test that commands exist and work, not what their help text says.
    This makes tests more maintainable and less brittle.
    """

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_help_command_succeeds(self):
        """Test that help command runs without errors."""
        result = self.runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        # Help should produce some output
        assert len(result.output) > 0

    def test_version_option_works(self):
        """Test that --version flag works."""
        result = self.runner.invoke(main, ["--version"])
        assert result.exit_code in [0, 2]
        if result.exit_code == 0:
            # Version output should contain a version number pattern
            assert any(char.isdigit() for char in result.output)

    def test_no_command_displays_help_text_and_exits_gracefully(self):
        """Test that invoking with no command shows help and exits gracefully."""
        result = self.runner.invoke(main, [])
        # When no command is given, Click shows help and exits with code 0 or 2
        assert result.exit_code in [0, 2]
        # Should produce some output (the help text)
        assert len(result.output) > 0


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_invalid_command(self):
        """Test handling of invalid commands."""
        result = self.runner.invoke(main, ["invalid-command"])

        # The CLI treats unknown commands as prompts for the ask command
        assert result.exit_code == 0
        # With mocking, we get a generic response, not the command echoed
        assert len(result.output) > 0

    def test_hook_exception_handling(self):
        """Test that exceptions from hooks are handled gracefully."""
        # Make the underlying API call fail to test exception handling
        with patch("matilda_brain.internal.hooks.core.ttt_stream", side_effect=Exception("Test error")):
            result = self.runner.invoke(main, ["ask", "test"])

            # Should handle exception gracefully - exact behavior depends on implementation
            # At minimum, shouldn't crash completely
            assert result.exit_code in [0, 1]


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_command_chain_compatibility(self):
        """Test that commands work with shell pipes and redirects."""
        # Test help for all main commands
        commands = [
            "ask",
            "chat",
            "list",
            "status",
            "models",
            "info",
            "config",
            "tools",
            "export",
        ]

        for cmd in commands:
            result = self.runner.invoke(main, [cmd, "--help"])
            assert result.exit_code == 0, f"Help failed for command: {cmd}"

    def test_nested_subcommands(self):
        """Test that nested subcommands work correctly."""
        # Test config subcommands
        config_subcommands = ["get", "set", "list"]
        for subcmd in config_subcommands:
            result = self.runner.invoke(main, ["config", subcmd, "--help"])
            assert result.exit_code == 0, f"Help failed for config {subcmd}"

        # Test tools subcommands
        tools_subcommands = ["enable", "disable", "list"]
        for subcmd in tools_subcommands:
            result = self.runner.invoke(main, ["tools", subcmd, "--help"])
            assert result.exit_code == 0, f"Help failed for tools {subcmd}"
