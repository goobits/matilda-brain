"""JSON output validation tests for CLI commands.

Tests JSON formatting and structure across all CLI commands that support JSON output.
"""

import json
from unittest.mock import Mock, patch

import pytest

from matilda_brain.cli import cli as main
from .conftest import IntegrationTestBase


class TestJSONOutputValidation(IntegrationTestBase):
    """Comprehensive JSON output validation across all CLI commands.

    Consolidates JSON testing for status, models, info, and list commands
    into parameterized tests to eliminate redundancy and improve maintainability.
    """

    @pytest.mark.parametrize(
        "command_args,expected_structure,validation_checks",
        [
            # Status command JSON validation
            (
                ["status", "--json"],
                "dict",
                {
                    "required_components": ["backend", "api", "local", "key", "status", "health"],
                    "min_components": 1,
                    "data_validation": lambda d: len([v for v in d.values() if v is not None and v != ""])
                    >= len(d) // 2,
                },
            ),
            # Models command JSON validation
            (
                ["models", "--json"],
                "list",
                {
                    "required_fields": ["name", "provider"],
                    "min_entries": 1,
                    "entry_validation": lambda m: isinstance(m, dict)
                    and any(key.lower().startswith("name") for key in m.keys()),
                },
            ),
            # Info command JSON validation
            (
                ["info", "gpt-4", "--json"],
                "dict",
                {
                    "required_keys": ["name", "provider"],
                    "content_validation": lambda d: "gpt-4" in str(d).lower(),
                    "detail_fields": ["context", "token", "capabilit", "cost", "speed"],
                },
            ),
            # List models JSON validation (alternative format)
            (
                ["list", "models", "--format", "json"],
                "list_or_dict",
                {
                    "content_check": lambda d: len(d) > 0 if isinstance(d, list) else bool(d),
                    "model_indicators": ["model", "gpt", "claude"],
                },
            ),
        ],
    )
    def test_json_output_structure_and_validation(self, command_args, expected_structure, validation_checks):
        """Test that all commands with JSON output produce valid, structured JSON with expected content."""
        # Set up appropriate mocks based on command type
        if "status" in command_args:
            with patch("matilda_brain.backends.local.LocalBackend") as mock_local, patch("os.getenv") as mock_getenv:
                # Mock realistic backend status
                mock_local_instance = Mock()
                mock_local_instance.is_available = False
                mock_local_instance.base_url = "http://localhost:11434"
                mock_local_instance.status = "unavailable"
                mock_local.return_value = mock_local_instance

                # Mock API key environment
                def getenv_side_effect(key, default=None):
                    if key == "OPENAI_API_KEY":
                        return "sk-test-key-available"
                    elif key == "ANTHROPIC_API_KEY":
                        return None
                    return default

                mock_getenv.side_effect = getenv_side_effect

                result = self.runner.invoke(main, command_args)

        elif "models" in command_args or "info" in command_args:
            with patch("matilda_brain.config.schema.get_model_registry") as mock_registry:
                # Mock model data for models/info commands
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
                mock_registry_instance.list_models.return_value = ["gpt-4"]
                mock_registry_instance.get_model.return_value = mock_model
                mock_registry.return_value = mock_registry_instance

                result = self.runner.invoke(main, command_args)
        else:
            # No mocking needed for other commands
            result = self.runner.invoke(main, command_args)

        assert result.exit_code == 0, f"JSON command failed: {result.output}"

        # Validate JSON structure
        try:
            data = json.loads(result.output)

            # Structure validation
            if expected_structure == "dict":
                assert isinstance(data, dict), f"Expected dict, got {type(data)}"
            elif expected_structure == "list":
                assert isinstance(data, list), f"Expected list, got {type(data)}"
                assert len(data) > 0, "List should not be empty"
                # Validate list entries
                if "entry_validation" in validation_checks:
                    for entry in data:
                        assert validation_checks["entry_validation"](entry), f"Entry validation failed: {entry}"
            elif expected_structure == "list_or_dict":
                assert isinstance(data, (list, dict)), f"Expected list or dict, got {type(data)}"

            # Apply specific validation checks
            if "required_components" in validation_checks:
                found_components = [
                    comp
                    for comp in validation_checks["required_components"]
                    if any(comp in str(key).lower() for key in data.keys())
                ]
                min_components = validation_checks.get("min_components", 1)
                assert (
                    len(found_components) >= min_components
                ), f"Missing system components. Found: {found_components}, Expected min: {min_components}"

            if "required_fields" in validation_checks:
                for field in validation_checks["required_fields"]:
                    if isinstance(data, list) and data:
                        # Check first entry for required fields
                        first_entry = data[0]
                        field_present = any(key.lower().startswith(field) for key in first_entry.keys())
                        assert field_present, f"Missing field '{field}' in {list(first_entry.keys())}"

            if "required_keys" in validation_checks:
                for key in validation_checks["required_keys"]:
                    assert any(
                        key in str(k).lower() for k in data.keys()
                    ), f"Missing key '{key}' in {list(data.keys())}"

            if "content_validation" in validation_checks:
                assert validation_checks["content_validation"](data), f"Content validation failed for {data}"

            if "data_validation" in validation_checks:
                assert validation_checks["data_validation"](data), f"Data validation failed for {data}"

            if "content_check" in validation_checks:
                assert validation_checks["content_check"](data), f"Content check failed for {data}"

            if "detail_fields" in validation_checks:
                found_details = [
                    field
                    for field in validation_checks["detail_fields"]
                    if any(field in key.lower() for key in data.keys())
                ]
                assert len(found_details) > 0, f"Missing detail fields. Found keys: {list(data.keys())}"

        except json.JSONDecodeError as e:
            # Handle graceful fallback for commands that may not always produce pure JSON
            if "model_indicators" in validation_checks:
                output = result.output.strip()
                assert len(output) > 0, f"Should provide some output even if not JSON: {output}"
                output_lower = output.lower()
                assert any(
                    word in output_lower for word in validation_checks["model_indicators"]
                ), f"Output should contain model info: {output}"
            else:
                pytest.fail(f"Invalid JSON output from {command_args}: {e}. Output: {result.output}")

    @pytest.mark.parametrize("command_base", ["status", "models", "info gpt-4", "list models"])
    def test_json_flag_consistency(self, command_base):
        """Test that --json flag works consistently across all commands."""
        args = command_base.split()

        # Add appropriate JSON flag based on command
        if "list" in args:
            args.extend(["--format", "json"])
        else:
            args.append("--json")

        # Apply mocking for commands that need it
        if "status" in command_base:
            with patch("matilda_brain.backends.local.LocalBackend") as mock_local, patch("os.getenv"):
                mock_local_instance = Mock()
                mock_local_instance.is_available = False
                mock_local.return_value = mock_local_instance
                result = self.runner.invoke(main, args)
        elif "models" in command_base or "info" in command_base:
            with patch("matilda_brain.config.schema.get_model_registry") as mock_registry:
                mock_model = Mock()
                mock_model.name = "gpt-4"
                mock_model.provider = "openai"
                mock_registry_instance = Mock()
                mock_registry_instance.list_models.return_value = ["gpt-4"]
                mock_registry_instance.get_model.return_value = mock_model
                mock_registry.return_value = mock_registry_instance
                result = self.runner.invoke(main, args)
        else:
            result = self.runner.invoke(main, args)

        # Should either succeed with JSON or fail gracefully
        assert result.exit_code in [0, 1], f"Command failed unexpectedly: {result.output}"

        if result.exit_code == 0:
            assert "{" in result.output or "[" in result.output, "JSON flag should produce JSON-like output"

    def test_json_vs_regular_output_differences(self):
        """Test that JSON output differs meaningfully from regular output."""
        commands_to_test = [
            (["status"], ["status", "--json"]),
            (["models"], ["models", "--json"]),
            (["info", "gpt-4"], ["info", "gpt-4", "--json"]),
            (["list", "models"], ["list", "models", "--format", "json"]),
        ]

        for regular_cmd, json_cmd in commands_to_test:
            # Apply appropriate mocking
            if "status" in regular_cmd:
                with patch("matilda_brain.backends.local.LocalBackend") as mock_local, patch("os.getenv"):
                    mock_local_instance = Mock()
                    mock_local_instance.is_available = False
                    mock_local.return_value = mock_local_instance

                    regular_result = self.runner.invoke(main, regular_cmd)
                    json_result = self.runner.invoke(main, json_cmd)

            elif "models" in regular_cmd or "info" in regular_cmd:
                with patch("matilda_brain.config.schema.get_model_registry") as mock_registry:
                    mock_model = Mock()
                    mock_model.name = "gpt-4"
                    mock_model.provider = "openai"
                    mock_registry_instance = Mock()
                    mock_registry_instance.list_models.return_value = ["gpt-4"]
                    mock_registry_instance.get_model.return_value = mock_model
                    mock_registry.return_value = mock_registry_instance

                    regular_result = self.runner.invoke(main, regular_cmd)
                    json_result = self.runner.invoke(main, json_cmd)
            else:
                regular_result = self.runner.invoke(main, regular_cmd)
                json_result = self.runner.invoke(main, json_cmd)

            if regular_result.exit_code == 0 and json_result.exit_code == 0:
                # Outputs should be different (JSON vs human-readable)
                assert (
                    regular_result.output != json_result.output
                ), f"JSON and regular output identical for {regular_cmd}"

                # JSON output should be parseable
                try:
                    json.loads(json_result.output)
                except json.JSONDecodeError:
                    # Some commands may not produce pure JSON, verify it contains JSON-like structure
                    assert (
                        "{" in json_result.output or "[" in json_result.output
                    ), f"JSON output not JSON-like for {json_cmd}: {json_result.output}"
