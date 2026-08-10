"""Shared fixtures and base classes for CLI tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from matilda_brain.config.manager import clear_config_cache


class IntegrationTestBase:
    """Base class for integration tests with proper isolation."""

    def setup_method(self):
        """Set up isolated test environment."""
        self.runner = CliRunner()

        # Create temporary directories for test isolation
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / ".matilda"
        self.session_dir = self.config_dir / "brain" / "sessions"

        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Set environment variables to use our temp directories
        self.original_env = {}
        env_vars = {
            "MATILDA_CONFIG": str(self.config_dir / "config.toml"),
            "XDG_CONFIG_HOME": str(Path(self.temp_dir)),
            "HOME": str(self.temp_dir),
        }

        for key, value in env_vars.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value
        clear_config_cache()

    def teardown_method(self):
        """Clean up test environment."""
        # Restore original environment
        for key, original_value in self.original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value
        clear_config_cache()

        # Clean up temp directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)


@pytest.fixture
def cli_runner():
    """Provide a Click CLI runner for tests."""
    return CliRunner()


@pytest.fixture
def mock_tool():
    """Provide a mock tool for testing."""
    mock = Mock()
    mock.name = "test_tool"
    mock.description = "Test tool description"
    return mock


@pytest.fixture
def mock_model():
    """Provide a mock model for testing."""
    mock = Mock()
    mock.name = "gpt-4"
    mock.provider = "openai"
    mock.provider_name = "OpenAI"
    mock.context_length = 8192
    mock.cost_per_token = 0.00003
    mock.speed = "fast"
    mock.quality = "high"
    mock.aliases = ["gpt4"]
    mock.capabilities = ["text"]
    return mock
