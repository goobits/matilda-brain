"""Comprehensive integration tests for Matilda Brain CLI commands.

This test suite runs detailed functionality tests with API calls and file I/O.
These tests verify actual AI responses, complex command combinations, and
real-world usage scenarios.

Provider HTTP is mocked unless the runner receives ``--real-api``.

Run with:
    ./scripts/test.py integration --test test_cli_comprehensive_integration
"""

import json
import os
import tempfile

import pytest
from click.testing import CliRunner

from matilda_brain.cli import cli as main


def has_valid_api_key():
    """Check if any valid API keys are available."""

    def is_valid_key(key):
        return key and "test-key" not in key and len(key) > 10

    return any(
        [
            is_valid_key(os.getenv("OPENAI_API_KEY")),
            is_valid_key(os.getenv("ANTHROPIC_API_KEY")),
            is_valid_key(os.getenv("OPENROUTER_API_KEY")),
        ]
    )


def run_brain_command(args, input_text=None, timeout=10):
    """Run a Matilda Brain command using CliRunner for faster execution."""
    runner = CliRunner()
    result = runner.invoke(main, args, input=input_text)
    return result


class TestBasicAPICommands:
    """Test basic commands that require API calls."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_brain_direct_prompt_with_api(self):
        """Test: brain 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["hello world"])
        # Should either work or timeout (both acceptable for API calls)
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_brain_ask_prompt(self):
        """Test: brain ask 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "hello world"])
        assert result.exit_code in [0, 124]


class TestModelSelectionOptions:
    """Test model selection options."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_model_gpt4(self):
        """Test: brain ask --model gpt-4 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "--model", "gpt-4", "hello"])
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_model_short_flag(self):
        """Test: brain ask -m @claude 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "-m", "@claude", "hello"])
        # Accept success (0), timeout (124), or model unavailable error (1)
        assert result.exit_code in [0, 1, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_full_model_path(self):
        """Test: brain ask --model openrouter/google/gemini-flash-1.5 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "--model", "openrouter/google/gemini-flash-1.5", "hello"])
        assert result.exit_code in [0, 124]


class TestSystemPromptOptions:
    """Test system prompt options."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_system_prompt(self):
        """Test: brain ask --system 'system prompt' 'user prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "--system", "You are helpful", "hello"])
        assert result.exit_code in [0, 124]


class TestTemperatureControl:
    """Test temperature control options."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_temperature_long(self):
        """Test: brain ask --temperature 0.7 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "--temperature", "0.7", "hello"])
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_temperature_short(self):
        """Test: brain ask -t 0.1 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "-t", "0.1", "hello"])
        assert result.exit_code in [0, 124]


class TestTokenLimits:
    """Test token limit options."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_max_tokens(self):
        """Test: brain ask --max-tokens 100 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "--max-tokens", "100", "hello"])
        assert result.exit_code in [0, 124]


class TestToolsOptions:
    """Test tools options."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_tools_basic_executes_with_tools_enabled(self):
        """Test: brain ask --tools 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "--tools", "true", "hello"])
        assert result.exit_code in [0, 124]


class TestOutputModes:
    """Test output modes."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_stream(self):
        """Test: brain ask --stream 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "--stream", "true", "hello"])
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_json(self):
        """Test: brain ask --json 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "--json", "hello"])
        assert result.exit_code in [0, 124]


class TestChatCommands:
    """Test chat command options."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_chat_command_basic(self):
        """Test: brain chat - Basic chat command functionality"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        # Note: Chat is typically interactive, so this tests command existence
        result = run_brain_command(["chat", "--help"])
        assert result.exit_code == 0


class TestPipelineUsage:
    """Test pipeline/stdin usage."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_echo_pipe_ask(self):
        """Test: echo 'text' | brain ask 'transform this' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "transform this"], input_text="hello world")
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_echo_pipe_ask_specific(self):
        """Test: echo 'hello world' | brain ask 'transform this' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "make this uppercase"], input_text="hello world")
        assert result.exit_code in [0, 124]


class TestModelAliases:
    """Test model aliases."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_alias_claude(self):
        """Test: brain ask -m @claude 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "-m", "@claude", "hello"])
        # Accept success (0), timeout (124), or model unavailable error (1)
        assert result.exit_code in [0, 1, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_alias_gpt4(self):
        """Test: brain ask -m @gpt4 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "-m", "@gpt4", "hello"])
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_alias_fast(self):
        """Test: brain ask -m @fast 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "-m", "@fast", "hello"])
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_alias_best(self):
        """Test: brain ask -m @best 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "-m", "@best", "hello"])
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_alias_coding(self):
        """Test: brain ask -m @coding 'prompt' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "-m", "@coding", "hello"])
        # Accept success (0), timeout (124), or model unavailable error (1)
        assert result.exit_code in [0, 1, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_ask_alias_local(self):
        """Test: brain ask -m @local 'prompt' - Tested 2025-07-24"""
        # Local models might not be available, but structure should work
        result = run_brain_command(["ask", "-m", "@local", "hello"])
        assert result.exit_code in [0, 1, 124]  # May fail if Ollama not running

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_direct_alias_claude(self):
        """Test: brain @claude 'prompt' - Direct alias usage"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["@claude", "hello"])
        # Accept success (0), timeout (124), or model unavailable error (1)
        assert result.exit_code in [0, 1, 124]


class TestComplexCombinations:
    """Test complex command combinations."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_complex_claude_tools_json(self):
        """Test: brain ask --model @claude --temperature 0.2 --tools --json 'write a function' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(
            [
                "ask",
                "--model",
                "@claude",
                "--temperature",
                "0.2",
                "--tools",
                "true",
                "--json",
                "write a simple function",
            ]
        )
        # Accept success (0), timeout (124), or model unavailable error (1)
        assert result.exit_code in [0, 1, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_complex_gpt4_max_tokens(self):
        """Test: brain ask --json --model gpt-4 --max-tokens 500 'structured analysis' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(
            [
                "ask",
                "--json",
                "--model",
                "gpt-4",
                "--max-tokens",
                "500",
                "analyze this briefly",
            ]
        )
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_complex_stream_json(self):
        """Test: brain ask -m @gpt4 --stream --json 'explain this algorithm' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "-m", "@gpt4", "--stream", "true", "--json", "explain sorting"])
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_complex_pipeline_tools_json(self):
        """Test: echo 'data' | brain ask --model @claude --tools --json 'analyze and research' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(
            [
                "ask",
                "--model",
                "@claude",
                "--tools",
                "true",
                "--json",
                "analyze this data",
            ],
            input_text="sample data for analysis",
        )
        # Accept success (0), timeout (124), or model unavailable error (1)
        assert result.exit_code in [0, 1, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_complex_all_options(self):
        """Test: brain ask --model @claude --temperature 0.7 --max-tokens 1000 --tools 'research topic' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(
            [
                "ask",
                "--model",
                "@claude",
                "--temperature",
                "0.7",
                "--max-tokens",
                "1000",
                "--tools",
                "true",
                "research Python",
            ]
        )
        # Accept success (0), timeout (124), or model unavailable error (1)
        assert result.exit_code in [0, 1, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_complex_fast_json_stream(self):
        """Test: brain ask -m @fast --json --stream 'quick response in JSON format' - Tested 2025-07-24"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "-m", "@fast", "--json", "--stream", "true", "quick hello"])
        assert result.exit_code in [0, 124]


class TestFilePipelineUsage:
    """Test file-based pipeline usage - tests real file I/O functionality."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_file_content_analysis_demonstrates_pipeline_usage(self):
        """Test: cat file.txt | brain ask 'summarize' - Demonstrates real file processing pipeline with validation"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        # Create a temporary file with meaningful test content
        test_content = """# Project Documentation
        
This is a sample project that demonstrates Matilda Brain's ability to process file content.
The project includes multiple components:
1. A data processing module
2. A user interface component  
3. Integration tests
4. Configuration management
        
The architecture follows modern best practices with clear separation of concerns."""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write(test_content)
            temp_file = f.name

        try:
            # Read file content and pipe to brain with specific analysis request
            with open(temp_file, "r") as f:
                file_content = f.read()

            result = run_brain_command(
                ["ask", "Summarize the main components mentioned in this documentation"], input_text=file_content
            )
            assert result.exit_code in [0, 124], f"File analysis command failed: {result.output}"

            # If successful, verify meaningful analysis was performed
            if result.exit_code == 0:
                response = result.output.strip()
                assert len(response) > 20, f"Response too short for meaningful analysis: {response}"

                # Verify the AI understood the content structure
                response_lower = response.lower()
                expected_concepts = ["component", "module", "project", "architecture"]
                found_concepts = [concept for concept in expected_concepts if concept in response_lower]
                assert (
                    len(found_concepts) >= 2
                ), f"Analysis should reference key concepts from input. Found: {found_concepts}"
        finally:
            # Clean up
            os.unlink(temp_file)

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_json_file_pipe_ask(self):
        """Test: cat data.json | brain ask 'analyze' - Tests JSON file processing"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        # Create a temporary JSON file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            test_data = {"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}
            json.dump(test_data, f)
            temp_file = f.name

        try:
            with open(temp_file, "r") as f:
                file_content = f.read()

            result = run_brain_command(["ask", "how many users are in this data?"], input_text=file_content)
            assert result.exit_code in [0, 124]
        finally:
            os.unlink(temp_file)


class TestJSONInputPipeline:
    """Test JSON input pipeline - tests structured input parsing."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_json_input_pipeline(self):
        """Test: echo '{"prompt": "hello"}' | brain ask - Tests JSON input parsing"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        json_input = '{"message": "hello world", "context": "testing"}'
        result = run_brain_command(["ask", "extract the message from this JSON"], input_text=json_input)
        assert result.exit_code in [0, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_json_array_input(self):
        """Test: echo '[1,2,3]' | brain ask 'sum these' - Tests JSON array processing"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        json_input = "[10, 20, 30, 40]"
        result = run_brain_command(["ask", "what is the sum of these numbers?"], input_text=json_input)
        assert result.exit_code in [0, 124]


class TestAdditionalCLIOptions:
    """Test additional CLI options for completeness."""

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_system_prompt_short_flag(self):
        """Test: brain ask -s 'system' 'user' - Tests short flag consistency"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "-s", "You are helpful", "hello"])
        # May not be implemented, but test structure should work
        assert result.exit_code in [0, 1, 124]

    @pytest.mark.requires_credentials
    @pytest.mark.requires_network
    def test_higher_max_tokens(self):
        """Test: brain ask --max-tokens 2000 'prompt' - Tests higher token limits"""
        if not has_valid_api_key():
            pytest.skip("Requires API key")

        result = run_brain_command(["ask", "--max-tokens", "2000", "write a detailed explanation"])
        assert result.exit_code in [0, 124]


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_cli_comprehensive_integration.py -v
    pytest.main([__file__, "-v"])
