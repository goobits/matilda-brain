"""Tests for the ask CLI command functionality."""

import pytest

from matilda_brain.cli import main
from tests.cli.conftest import IntegrationTestBase


class TestAskCommand(IntegrationTestBase):
    """Test the ask command functionality."""

    def test_ask_command_exists(self):
        """Test that ask command is available and accepts --help."""
        result = self.runner.invoke(main, ["ask", "--help"])
        assert result.exit_code == 0

    @pytest.mark.integration
    def test_ask_basic_prompt(self):
        """Test basic ask functionality with real hooks."""
        # This is a real integration test - it will make actual API calls
        # if you have API keys configured, otherwise it will fail gracefully
        result = self.runner.invoke(main, ["ask", "What is Python?"])

        # Integration test - verify CLI works (may fail with API errors in CI)
        # Exit code 0 = success, 1 = expected error (like missing API key)
        assert result.exit_code in [0, 1]

        # If successful, should have some output
        if result.exit_code == 0:
            assert len(result.output.strip()) > 0
        else:
            # If failed due to API issues, that's expected in test environment
            assert "error" in result.output.lower() or "Error" in result.output

    @pytest.mark.integration
    def test_ask_with_options(self):
        """Test ask with various options."""
        # Real integration test with options
        result = self.runner.invoke(
            main,
            [
                "ask",
                "Debug this code",
                "--model",
                "gpt-4",
                "--temperature",
                "0.7",
                "--tools",
                "true",
                "--session",
                "test-session",
            ],
        )

        # Integration test - verify CLI handles options correctly
        # Exit code 0 = success, 1 = expected error (like missing API key/model)
        assert result.exit_code in [0, 1]

        # The important thing is that it doesn't crash with exit code 2 (argument error)
        # which would indicate the CLI argument parsing failed
        assert result.exit_code != 2

    # Parameter-specific tests have been consolidated into TestCLIParameterValidation
    # in test_cli_modern.py to eliminate redundancy and improve test organization.
    # Basic ask command functionality tests remain here for command-specific validation.
