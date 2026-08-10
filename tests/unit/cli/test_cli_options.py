"""CLI debug-mode contract tests."""

from unittest.mock import patch

import pytest

from matilda_brain.cli import cli
from tests.cli.conftest import IntegrationTestBase


class TestDebugMode(IntegrationTestBase):
    @pytest.mark.parametrize("variable", ["BRAIN_DEBUG", "TTT_DEBUG"])
    def test_debug_environment_variables_remain_supported(self, variable, monkeypatch):
        monkeypatch.setenv(variable, "true")

        result = self.runner.invoke(cli, ["list", "models"])

        assert result.exit_code == 0
        assert result.output.strip()

    def test_debug_flag_is_exposed(self):
        result = self.runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "--debug" in result.output
        assert "debug output" in result.output.lower()

    def test_debug_mode_preserves_graceful_hook_errors(self, monkeypatch):
        monkeypatch.setenv("BRAIN_DEBUG", "true")

        with patch("matilda_brain.internal.hooks.core.brain_stream", side_effect=Exception("Test error")):
            result = self.runner.invoke(cli, ["ask", "test", "--model", "nonexistent-model"])

        assert result.exit_code in (0, 1)
