"""Tests for the tools CLI command functionality."""

from unittest.mock import Mock, patch

from matilda_brain.cli import cli as main
from tests.cli.conftest import IntegrationTestBase


class TestCLIToolsCommand(IntegrationTestBase):
    """Test the core CLI tools command functionality."""

    def test_tools_command_shows_management_and_extensions_help(self):
        """Test tools command help."""
        result = self.runner.invoke(main, ["tools", "--help"])

        assert result.exit_code == 0
        output = result.output
        assert "Manage CLI tools and extensions" in output

    def test_tools_subcommands_exist(self):
        """Test that tools subcommands are available."""
        result = self.runner.invoke(main, ["tools", "--help"])

        assert result.exit_code == 0
        output = result.output

        # Should list subcommands
        assert "enable" in output
        assert "disable" in output
        assert "list" in output

    def test_tools_enable(self):
        """Test tools enable subcommand."""
        # Mock the config manager methods that tools enable/disable uses
        with patch("matilda_brain.config.manager.ConfigManager.get_merged_config") as mock_get, patch(
            "matilda_brain.config.manager.ConfigManager.set_value"
        ) as mock_set:
            mock_get.return_value = {"tools": {"disabled": ["web_search"]}}
            mock_set.return_value = None

            result = self.runner.invoke(main, ["tools", "enable", "web_search"])

            assert result.exit_code == 0
            assert "enabled" in result.output.lower()
            mock_get.assert_called()
            mock_set.assert_called_once()

    def test_tools_disable(self):
        """Test tools disable subcommand."""
        # Mock the config manager methods that tools enable/disable uses
        with patch("matilda_brain.config.manager.ConfigManager.get_merged_config") as mock_get, patch(
            "matilda_brain.config.manager.ConfigManager.set_value"
        ) as mock_set:
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

        with patch("matilda_brain.tools.list_tools") as mock_list, patch(
            "matilda_brain.config.manager.ConfigManager.get_merged_config"
        ) as mock_get:
            mock_list.return_value = [mock_tool]
            mock_get.return_value = {"tools": {"disabled": []}}

            result = self.runner.invoke(main, ["tools", "list"])

            assert result.exit_code == 0
            assert "web_search" in result.output
            mock_list.assert_called_once()
            mock_get.assert_called_once()

    def test_tools_command_parameter_passing(self):
        """Test tools enable/disable/list commands pass parameters correctly."""
        # Test tools list - this should always work
        result = self.runner.invoke(main, ["tools", "list", "--show-disabled"])

        # Tools list should succeed - validates CLI structure and parameter passing
        assert result.exit_code == 0, f"Tools list failed with output: {result.output}"

        # Test tools enable/disable with a hypothetical tool
        # These might fail if tool doesn't exist, but shouldn't have argument parsing errors
        result = self.runner.invoke(main, ["tools", "enable", "web_search"])

        # Should not fail with argument parsing error (exit code 2)
        assert result.exit_code != 2, f"Tools enable had argument parsing error: {result.output}"

        result = self.runner.invoke(main, ["tools", "disable", "calculator"])

        # Should not fail with argument parsing error (exit code 2)
        assert result.exit_code != 2, f"Tools disable had argument parsing error: {result.output}"
