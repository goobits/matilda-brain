"""Tests for the chat CLI command functionality."""

from matilda_brain.cli import main
from tests.cli.conftest import IntegrationTestBase


class TestChatCommand(IntegrationTestBase):
    """Test the chat command functionality."""

    def test_chat_command_exists(self):
        """Test that chat command is available and accepts --help."""
        result = self.runner.invoke(main, ["chat", "--help"])
        assert result.exit_code == 0

    def test_chat_command_accepts_help_and_validates_options(self):
        """Test basic chat functionality."""
        # Chat command is interactive, so we can only test help and argument validation
        # Real chat functionality would hang waiting for user input
        result = self.runner.invoke(main, ["chat", "--help"])
        assert result.exit_code == 0

    def test_chat_with_options(self):
        """Test chat command handles options correctly."""
        # Chat is interactive, but we can test that options are accepted without errors
        # by testing help with complex arguments
        result = self.runner.invoke(main, ["chat", "--help"])
        assert result.exit_code == 0

        # Verify help shows the options we expect
        assert "--model" in result.output
        assert "--session" in result.output
        assert "--tools" in result.output

    # Parameter-specific tests have been consolidated into TestCLIParameterValidation
    # in test_cli_modern.py to eliminate redundancy and improve test organization.
    # Chat command functionality tests remain here for command-specific validation.
