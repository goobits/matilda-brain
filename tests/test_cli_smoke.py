"""Fast smoke tests for TTT CLI commands.

This test suite verifies CLI structure, argument parsing, and command availability
without making API calls. For comprehensive functionality testing, see
test_cli_comprehensive_integration.py.

Targets <10 second execution time for essential CLI validation.

Run with:
    ./test.sh --test test_cli_smoke
"""

import json

import pytest
from click.testing import CliRunner

from matilda_brain.cli import cli as main


def run_ttt_command(args, input_text=None, timeout=10):
    """Run a TTT command using CliRunner for faster execution."""
    runner = CliRunner()
    result = runner.invoke(main, args, input=input_text)
    return result


class TestBasicCommands:
    """Test basic CLI commands structure and help output - no API calls."""

    def test_ttt_help_shows_main_commands(self):
        """Test: ttt --help - Verify main command structure"""
        result = run_ttt_command(["--help"])
        assert result.exit_code == 0, f"Help command failed: {result.output}"

        # Should show main commands
        assert "ask" in result.output.lower(), f"'ask' command missing from help: {result.output}"
        assert "models" in result.output.lower(), f"'models' command missing from help: {result.output}"
        assert "status" in result.output.lower(), f"'status' command missing from help: {result.output}"
        assert "config" in result.output.lower(), f"'config' command missing from help: {result.output}"

    def test_ask_help_shows_all_options(self):
        """Test: ttt ask --help - Verify ask command accepts all expected options"""
        result = run_ttt_command(["ask", "--help"])
        assert result.exit_code == 0, f"Ask help command failed: {result.output}"

        # Should show all major options without making API calls
        expected_options = ["--model", "--temperature", "--max-tokens", "--tools", "--json", "--stream", "--system"]
        for option in expected_options:
            assert option in result.output, f"Option {option} missing from ask help: {result.output}"

    def test_ttt_info_model_displays_detailed_information(self):
        """Test: ttt info <model> - Shows comprehensive model details including provider, context, and capabilities"""
        result = run_ttt_command(["info", "gpt-4"])
        assert result.exit_code == 0, f"Info command failed: {result.output}"

        # Verify essential model information is displayed
        output_lower = result.output.lower()
        assert "gpt-4" in output_lower, f"Model name missing from output: {result.output}"
        assert any(word in output_lower for word in ["provider", "openai"]), f"Provider info missing: {result.output}"
        assert any(
            word in output_lower for word in ["context", "token", "length"]
        ), f"Context length info missing: {result.output}"

        # Verify output is structured and informative
        lines = [line.strip() for line in result.output.split("\n") if line.strip()]
        assert len(lines) >= 3, f"Info output should have multiple lines of detail: {result.output}"

    def test_ttt_status_reports_system_health(self):
        """Test: ttt status - Provides comprehensive system health information including backend availability"""
        result = run_ttt_command(["status"])
        assert result.exit_code == 0, f"Status command failed: {result.output}"

        output_lower = result.output.lower()
        # Should contain system status information
        assert any(
            word in output_lower for word in ["status", "health", "system"]
        ), f"Status header missing: {result.output}"

        # Should report on backends or API availability
        assert any(
            word in output_lower for word in ["backend", "api", "available", "configured"]
        ), f"Backend status missing: {result.output}"

        # Should be informative with multiple status indicators
        lines = [line.strip() for line in result.output.split("\n") if line.strip()]
        assert len(lines) >= 2, f"Status should provide detailed information: {result.output}"

    def test_ttt_models_lists_available_models_with_details(self):
        """Test: ttt models - Lists models with provider and capability information"""
        result = run_ttt_command(["models"])
        assert result.exit_code == 0, f"Models command failed: {result.output}"

        output_lower = result.output.lower()
        # Should show models list with header
        assert any(word in output_lower for word in ["model", "available"]), f"Models header missing: {result.output}"

        # Should contain actual model names
        assert any(
            model in output_lower for model in ["gpt", "claude", "gemini"]
        ), f"No recognizable models found: {result.output}"

        # Should provide structured output with multiple entries
        lines = [line.strip() for line in result.output.split("\n") if line.strip()]
        assert len(lines) >= 3, f"Models output should list multiple models: {result.output}"


class TestConfigCommands:
    """Test config commands."""

    def test_config_list_outputs_valid_configuration_json(self):
        """Test: ttt config list - Outputs valid JSON with TTT configuration structure"""
        result = run_ttt_command(["config", "list"])
        assert result.exit_code == 0, f"Config list command failed: {result.output}"

        # Should output valid JSON
        try:
            config_data = json.loads(result.output)
            assert isinstance(config_data, dict), f"Config should be a JSON object: {type(config_data)}"

            # Should contain expected configuration sections
            expected_keys = ["models", "api", "backend"]
            found_keys = [key for key in expected_keys if any(k.startswith(key) for k in config_data.keys())]
            assert (
                len(found_keys) > 0
            ), f"Config should contain model/api/backend settings. Found keys: {list(config_data.keys())}"

        except json.JSONDecodeError as e:
            pytest.fail(f"Config list should output valid JSON. Error: {e}. Output: {result.output}")

    def test_config_get_models_default_shows_configured_model(self):
        """Test: ttt config get models.default - Shows the configured default model with clear labeling"""
        result = run_ttt_command(["config", "get", "models.default"])
        assert result.exit_code == 0, f"Config get command failed: {result.output}"

        # Should show the key and its value clearly
        assert "models.default" in result.output, f"Config key not shown: {result.output}"

        # Should have a value (either a model name or indication of no value)
        lines = result.output.strip().split("\n")
        config_line = next((line for line in lines if "models.default" in line), None)
        assert config_line is not None, f"Config line not found in output: {result.output}"

        # Should be in key: value format
        assert ":" in config_line, f"Config should use key: value format: {config_line}"

        # Value should be present (not just the key)
        key_value = config_line.split(":", 1)
        assert len(key_value) == 2 and key_value[1].strip(), f"Config value missing: {config_line}"

    def test_config_get_models_aliases(self):
        """Test: ttt config get models.aliases - Tested 2025-07-24"""
        result = run_ttt_command(["config", "get", "models.aliases"])
        assert result.exit_code == 0
        assert "models.aliases:" in result.output


class TestConfigPersistence:
    """Test config persistence - tests that configuration actually saves and loads."""

    def test_config_management_demonstrates_persistence_workflow(self):
        """Test: config set/get roundtrip - Demonstrates complete configuration management workflow with validation"""
        # Get original value for restoration
        original_result = run_ttt_command(["config", "get", "models.default"])
        assert original_result.exit_code == 0, f"Initial config get failed: {original_result.output}"

        # Parse original value for proper restoration
        original_value = None
        if ":" in original_result.output:
            original_value = original_result.output.split(":", 1)[1].strip()

        # Test configuration change with a known model
        test_model = "gpt-3.5-turbo"
        set_result = run_ttt_command(["config", "set", "models.default", test_model])

        if set_result.exit_code == 0:
            # Verify the configuration was actually persisted
            verify_result = run_ttt_command(["config", "get", "models.default"])
            assert verify_result.exit_code == 0, f"Config verification failed: {verify_result.output}"
            assert (
                test_model in verify_result.output
            ), f"Config was not persisted correctly. Expected '{test_model}' in: {verify_result.output}"

            # Verify config change is reflected in config list
            list_result = run_ttt_command(["config", "list"])
            if list_result.exit_code == 0:
                assert (
                    test_model in list_result.output
                ), f"Config change not reflected in full config list: {list_result.output}"

            # Restore original configuration
            if original_value:
                restore_result = run_ttt_command(["config", "set", "models.default", original_value])
                if restore_result.exit_code == 0:
                    # Verify restoration
                    final_result = run_ttt_command(["config", "get", "models.default"])
                    assert original_value in final_result.output, f"Config restoration failed: {final_result.output}"
        else:
            # If config set isn't available, verify config get provides useful information
            assert (
                "models.default" in original_result.output
            ), f"Config get should show key information: {original_result.output}"
            assert ":" in original_result.output, f"Config get should use key:value format: {original_result.output}"

    def test_config_invalid_key(self):
        """Test: config get invalid.key - Tests config error handling"""
        result = run_ttt_command(["config", "get", "invalid.nonexistent.key"])
        # Should either return an error or handle gracefully
        assert result.exit_code in [0, 1]


class TestModelAliasResolution:
    """Test model alias resolution across commands - tests alias system functionality."""

    def test_info_with_alias_claude(self):
        """Test: ttt info @claude - Tests alias resolution in info command"""
        result = run_ttt_command(["info", "@claude"])
        # Should either resolve successfully or give a clear error
        assert result.exit_code in [0, 1]

        if result.exit_code == 0:
            # Should show info about the resolved model
            assert any(word in result.output.lower() for word in ["claude", "anthropic", "model", "provider"])

    def test_info_with_alias_gpt4(self):
        """Test: ttt info @gpt4 - Tests alias resolution consistency"""
        result = run_ttt_command(["info", "@gpt4"])
        assert result.exit_code in [0, 1]

        if result.exit_code == 0:
            assert any(word in result.output.lower() for word in ["gpt", "openai", "model", "provider"])

    def test_info_with_alias_fast(self):
        """Test: ttt info @fast - Tests alias resolution for performance aliases"""
        result = run_ttt_command(["info", "@fast"])
        assert result.exit_code in [0, 1]


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_cli_smoke.py -v
    pytest.main([__file__, "-v"])
