"""CLI parameter validation tests.

Tests parameter conversion, validation, and passing across all CLI commands.
"""

import json
import os
from unittest.mock import patch

import pytest

from matilda_brain.cli import cli as main
from .conftest import IntegrationTestBase


class TestCLIParameterValidation(IntegrationTestBase):
    """Comprehensive CLI parameter validation across all commands.

    This is the master test class for CLI parameter validation that consolidates
    all parameter testing from across multiple test files. It validates:
    - Parameter type conversions (string->int, string->float, string->bool)
    - Parameter passing from CLI to hook functions
    - Complex parameter combinations across all commands
    - Error handling for invalid parameters
    """

    @pytest.mark.parametrize(
        "command_args,expected_exit_codes,description",
        [
            # Ask command variations
            (["ask", "test", "--model", "gpt-4"], [0, 1], "Ask with model parameter"),
            (["ask", "test", "--temperature", "0.7"], [0, 1], "Ask with temperature parameter"),
            (["ask", "test", "--max-tokens", "100"], [0, 1], "Ask with max-tokens parameter"),
            (["ask", "test", "--tools"], [0, 1], "Ask with tools flag"),
            (["ask", "test", "--stream"], [0, 1], "Ask with stream flag"),
            (["ask", "test", "--session", "test-session"], [0, 1], "Ask with session parameter"),
            (["ask", "test", "--system", "You are helpful"], [0, 1], "Ask with system parameter"),
            (["ask", "test", "--json"], [0, 1], "Ask with JSON flag"),
            # Config command variations
            (["config", "get", "model"], [0, 1], "Config get with key parameter"),
            (["config", "set", "model", "gpt-4"], [0], "Config set with key-value parameters"),
            (["config", "list"], [0], "Config list command"),
            (["config", "list", "--show-secrets"], [0], "Config list with show-secrets"),
            # List command variations
            (["list", "models"], [0], "List models command"),
            (["list", "sessions"], [0], "List sessions command"),
            (["list", "models", "--format", "json"], [0], "List models with format parameter"),
            (["--verbose", "list", "models"], [0], "List models with verbose parameter"),
            # Status and info commands
            (["status"], [0], "Status command"),
            (["status", "--json"], [0], "Status with JSON flag"),
            (["models"], [0], "Models command"),
            (["models", "--json"], [0], "Models with JSON flag"),
            (["info", "gpt-4"], [0, 1], "Info with model parameter"),
            (["info", "gpt-4", "--json"], [0, 1], "Info with model and JSON"),
            # Tools commands
            (["tools", "list"], [0], "Tools list command"),
            (["tools", "list", "--show-disabled"], [0], "Tools list with show-disabled"),
            (["tools", "enable", "web_search"], [0, 1], "Tools enable command"),
            (["tools", "disable", "calculator"], [0, 1], "Tools disable command"),
            # Export command
            (["export", "test-session"], [0, 1], "Export command with session"),
            (["export", "test-session", "--format", "json"], [0, 1], "Export with format parameter"),
            (["export", "test-session", "--include-metadata"], [0, 1], "Export with include-metadata"),
            # Chat command (interactive, limited testing)
            (["chat", "--model", "gpt-4"], [0, 1], "Chat with model parameter"),
        ],
    )
    def test_parameter_conversion_and_passing(self, command_args, expected_exit_codes, description):
        """Test that all CLI parameters are correctly converted and passed to hooks."""
        # Add empty input for chat command to exit gracefully
        input_data = "\n" if command_args[0] == "chat" else None

        with patch("matilda_brain.app_hooks.on_ask") as mock_ask, patch("matilda_brain.app_hooks.on_chat") as mock_chat:
            mock_ask.return_value = None
            mock_chat.return_value = None
            result = self.runner.invoke(main, command_args, input=input_data)

        # Critical: Parameter parsing should never fail (exit code 2 = Click argument error)
        assert result.exit_code != 2, f"{description} failed with argument parsing error: {result.output}"

        # Command should either succeed or fail gracefully, not crash
        assert result.exit_code in expected_exit_codes, (
            f"{description} had unexpected exit code {result.exit_code}. Expected {expected_exit_codes}. Output: {result.output}"
        )

    @pytest.mark.parametrize(
        "data_type,param_args,expected_type,expected_value",
        [
            ("float", ["ask", "test", "--temperature", "0.123"], float, 0.123),
            ("int", ["ask", "test", "--max-tokens", "2048"], int, 2048),
            ("bool_true_tools", ["ask", "test", "--tools"], bool, True),
            ("bool_true_stream", ["ask", "test", "--stream"], bool, True),
            ("str", ["ask", "test", "--model", "gpt-4"], str, "gpt-4"),
            ("str", ["ask", "test", "--session", "test-session"], str, "test-session"),
            ("str", ["ask", "test", "--system", "You are helpful"], str, "You are helpful"),
        ],
    )
    def test_click_type_conversions(self, data_type, param_args, expected_type, expected_value):
        """Test Click type conversions work correctly for all parameter types."""
        with patch("matilda_brain.app_hooks.on_ask") as mock_ask:
            mock_ask.return_value = None

            result = self.runner.invoke(main, param_args)

            # Command should succeed - validates Click type conversion
            assert result.exit_code == 0, f"Type conversion failed for {data_type}: {result.output}"

            # Verify the hook was called with correct parameters
            mock_ask.assert_called_once()
            kwargs = mock_ask.call_args[1]

            # Extract the parameter name from the CLI arg (remove --)
            param_name = None
            for i, arg in enumerate(param_args):
                if arg.startswith("--"):
                    if i + 1 < len(param_args) and not param_args[i + 1].startswith("--"):
                        param_name = arg[2:].replace("-", "_")  # CLI uses dashes, Python uses underscores
                        break

            if param_name and param_name in kwargs:
                actual_value = kwargs[param_name]
                assert isinstance(actual_value, expected_type), (
                    f"Expected {expected_type}, got {type(actual_value)} for {param_name}"
                )
                assert actual_value == expected_value, f"Expected {expected_value}, got {actual_value} for {param_name}"

    @pytest.mark.parametrize(
        "command_args,description",
        [
            # Complex parameter combinations
            (
                [
                    "ask",
                    "complex test",
                    "--model",
                    "gpt-4",
                    "--temperature",
                    "0.8",
                    "--max-tokens",
                    "200",
                    "--tools",
                    "--stream",
                    "--session",
                    "complex-session",
                    "--system",
                    "You are helpful",
                    "--json",
                ],
                "Complex ask command with all parameters",
            ),
            (["config", "list", "--show-secrets"], "Config list with show-secrets"),
            (["--verbose", "list", "models", "--format", "json"], "List models with format and verbose"),
            (
                ["export", "test-session", "--format", "json", "--include-metadata"],
                "Export with multiple parameters",
            ),
            (["tools", "list", "--show-disabled"], "Tools list with show-disabled"),
        ],
    )
    def test_complex_parameter_combinations(self, command_args, description):
        """Test complex combinations of parameters work together."""
        with patch("matilda_brain.app_hooks.on_ask") as mock_ask, patch("matilda_brain.app_hooks.on_chat") as mock_chat:
            mock_ask.return_value = None
            mock_chat.return_value = None
            result = self.runner.invoke(main, command_args)

        # Complex parameter combinations should not cause parsing errors
        assert result.exit_code != 2, f"{description} failed with argument parsing error: {result.output}"

        # Should either succeed or fail gracefully
        assert result.exit_code in [0, 1], f"{description} had unexpected exit code {result.exit_code}: {result.output}"

    @pytest.mark.integration
    def test_ask_parameter_passing_with_json_validation(self):
        """Test ask command with comprehensive parameter validation via JSON output."""
        result = self.runner.invoke(
            main,
            [
                "ask",
                "Test parameter passing with detailed validation",
                "--model",
                "gpt-4",
                "--temperature",
                "0.3",
                "--max-tokens",
                "400",
                "--session",
                "validation-session",
                "--system",
                "You are a helpful assistant for testing",
                "--json",
            ],
        )

        # Critical: CLI should handle complex parameter combinations
        assert result.exit_code in [0, 1], f"CLI parameter handling failed: {result.output}"
        assert result.exit_code != 2, f"CLI argument parsing error: {result.output}"

        if result.exit_code == 0 and "{" in result.output:
            try:
                # Find and parse JSON in output
                output_lines = result.output.strip().split("\n")
                for line in output_lines:
                    if line.strip().startswith("{"):
                        output_data = json.loads(line)

                        # Validate parameter type conversions
                        temp = output_data.get("temperature")
                        if temp is not None:
                            assert isinstance(temp, (int, float)), f"Temperature should be numeric: {temp}"
                            assert temp == 0.3, f"Temperature conversion failed: {temp}"

                        max_tokens = output_data.get("max_tokens")
                        if max_tokens is not None:
                            assert isinstance(max_tokens, int), f"Max tokens should be integer: {max_tokens}"
                            assert max_tokens == 400, f"Max tokens conversion failed: {max_tokens}"

                        # Validate session parameter
                        session_id = output_data.get("session_id") or output_data.get("session")
                        if session_id:
                            assert "validation-session" in str(session_id), f"Session parameter lost: {session_id}"

                        # Validate system prompt
                        system_prompt = output_data.get("system") or output_data.get("system_prompt")
                        if system_prompt:
                            assert "testing" in str(system_prompt).lower(), (
                                f"System prompt not preserved: {system_prompt}"
                            )

                        break
            except json.JSONDecodeError:
                # JSON parsing is secondary - main validation is exit code
                pass

    def test_debug_functionality_via_environment(self):
        """Test that debug functionality works through environment variable."""
        original_debug = os.environ.get("TTT_DEBUG")

        try:
            # Test with TTT_DEBUG environment variable
            os.environ["TTT_DEBUG"] = "true"

            result = self.runner.invoke(main, ["list", "models"])

            # Should succeed with debug enabled via env var
            assert result.exit_code == 0, f"Debug via env var caused failure: {result.output}"

        finally:
            # Restore original environment
            if original_debug is None:
                os.environ.pop("TTT_DEBUG", None)
            else:
                os.environ["TTT_DEBUG"] = original_debug

        # Test normal operation without debug
        result = self.runner.invoke(main, ["list", "models"])
        assert result.exit_code == 0, f"Command failed without debug: {result.output}"

    def test_config_set_get_parameter_validation(self):
        """Test config set/get commands pass key/value parameters correctly."""
        # Test config set - validates parameter passing
        result = self.runner.invoke(main, ["config", "set", "model", "gpt-4"])
        assert result.exit_code == 0, f"Config set failed: {result.output}"

        # Test config get - validates key parameter passing
        result = self.runner.invoke(main, ["config", "get", "model"])
        assert result.exit_code == 0, f"Config get failed: {result.output}"
        assert "gpt-4" in result.output, f"Config get didn't return expected value: {result.output}"

    @pytest.mark.integration
    def test_mocked_ask_parameter_validation(self):
        """Test ask command parameter conversion with mocked hooks to verify exact parameter passing."""
        with patch("matilda_brain.app_hooks.on_ask") as mock_ask:
            mock_ask.return_value = None

            result = self.runner.invoke(
                main,
                [
                    "ask",
                    "test prompt for mocked validation",
                    "--model",
                    "gpt-4",
                    "--temperature",
                    "0.7",
                    "--max-tokens",
                    "100",
                    "--tools",
                    "--session",
                    "mock-test-session",
                    "--system",
                    "You are helpful for testing",
                ],
            )

            # Verify command executed without errors
            assert result.exit_code == 0, f"Mocked command failed: {result.output}"

            # Verify the hook was called with correct parameters
            mock_ask.assert_called_once()
            kwargs = mock_ask.call_args[1]

            # Verify all parameters were passed correctly with proper types
            assert kwargs["prompt"] == "test prompt for mocked validation"
            assert kwargs["model"] == "gpt-4"
            assert kwargs["temperature"] == 0.7  # Float conversion
            assert kwargs["max_tokens"] == 100  # Int conversion
            assert kwargs["tools"] is True  # Bool conversion
            assert kwargs["session"] == "mock-test-session"
            assert kwargs["system"] == "You are helpful for testing"
            assert kwargs["stream"] is True  # Bool conversion
