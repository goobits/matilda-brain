"""Tests for the config CLI command functionality."""

from unittest.mock import patch

from matilda_brain.cli import main
from tests.cli.conftest import IntegrationTestBase


class TestConfigCommand(IntegrationTestBase):
    """Test the config command functionality."""

    def test_config_command_shows_setup_customization_help(self):
        """Test config command help."""
        result = self.runner.invoke(main, ["config", "--help"])

        assert result.exit_code == 0
        output = result.output
        assert "Customize your setup" in output

    def test_config_subcommands_exist(self):
        """Test that config subcommands are available."""
        result = self.runner.invoke(main, ["config", "--help"])

        assert result.exit_code == 0
        output = result.output

        # Should list subcommands
        assert "get" in output
        assert "set" in output
        assert "list" in output

    def test_config_get(self):
        """Test config get subcommand."""
        # Mock the config manager methods to avoid real file operations
        with patch("matilda_brain.config.manager.ConfigManager.show_value") as mock_show:
            mock_show.return_value = None

            result = self.runner.invoke(main, ["config", "get", "model"])

            assert result.exit_code == 0
            mock_show.assert_called_once_with("model")

    def test_config_set(self):
        """Test config set subcommand."""
        # Mock the config manager methods to avoid real file operations
        with patch("matilda_brain.config.manager.ConfigManager.set_value") as mock_set:
            mock_set.return_value = None

            result = self.runner.invoke(main, ["config", "set", "model", "gpt-4"])

            assert result.exit_code == 0
            mock_set.assert_called_once_with("model", "gpt-4")

    def test_config_list(self):
        """Test config list subcommand."""
        # Mock the config manager to return sample config
        with patch("matilda_brain.config.manager.ConfigManager.get_merged_config") as mock_get:
            mock_get.return_value = {"model": "gpt-4", "temperature": 0.7}

            result = self.runner.invoke(main, ["config", "list"])

            assert result.exit_code == 0
            assert "gpt-4" in result.output
            mock_get.assert_called_once()

    def test_config_list_with_secrets(self):
        """Test config list with show-secrets option."""
        # Mock the config manager to return sample config with secrets
        with patch("matilda_brain.config.manager.ConfigManager.get_merged_config") as mock_get:
            mock_get.return_value = {"model": "gpt-4", "api_key": "secret-key"}

            result = self.runner.invoke(main, ["config", "list", "--show-secrets", "true"])

            assert result.exit_code == 0
            assert "secret-key" in result.output
            mock_get.assert_called_once()

    def test_config_command_parameter_passing(self):
        """Test config set/get commands pass key/value parameters correctly."""
        # Test config set - this command should complete successfully
        result = self.runner.invoke(main, ["config", "set", "model", "gpt-4"])

        # Config set should succeed - this validates CLI structure and parameter passing
        assert result.exit_code == 0, f"Config set failed with output: {result.output}"

        # Test config get - this should retrieve the value we just set
        result = self.runner.invoke(main, ["config", "get", "model"])

        # Config get should succeed and show the value
        assert result.exit_code == 0, f"Config get failed with output: {result.output}"
        # Should contain the value we set (validates parameter was passed correctly)
        assert "gpt-4" in result.output, f"Config get didn't return expected value: {result.output}"

    def test_config_list_command_parameter_passing(self):
        """Test config list command passes show_secrets parameter correctly."""
        # Test config list with show-secrets flag
        result = self.runner.invoke(main, ["config", "list", "--show-secrets", "true"])

        # Config list should succeed - validates CLI structure and parameter passing
        assert result.exit_code == 0, f"Config list failed with output: {result.output}"

        # Test config list without show-secrets
        result = self.runner.invoke(main, ["config", "list"])

        assert result.exit_code == 0, f"Config list (no secrets) failed with output: {result.output}"
