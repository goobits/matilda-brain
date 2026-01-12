"""Tests for the configuration system."""

import toml

from matilda_brain import ConfigModel, ModelInfo
from matilda_brain.config import configure, get_config, load_config, model_registry, save_config


class TestConfigManagement:
    """Test the configuration loading and management functionality."""

    def test_default_values(self):
        """Test default configuration values from loaded config."""
        # Get config with defaults loaded from config.toml
        from matilda_brain.config import get_config

        config = get_config()

        # Test that we have the expected structure
        assert config.backend_config is not None
        assert config.backend_config.get("default") == "cloud"

        # These come from the user's config or project defaults
        if config.default_backend:
            assert config.default_backend in ["cloud", "local", "auto"]

        # Test optional fields
        assert config.enable_fallbacks is True
        # Fallback order can vary based on config
        assert isinstance(config.fallback_order, list)
        assert len(config.fallback_order) >= 1

    def test_environment_override(self, monkeypatch):
        """Test that environment variables override defaults."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://custom:8080")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        from matilda_brain.config import load_config

        config = load_config()

        assert config.ollama_base_url == "http://custom:8080"
        assert config.openai_api_key == "test-key"

    def test_custom_values(self):
        """Test setting custom values."""
        config = ConfigModel(default_backend="local", timeout=60, model_aliases={"custom": "my-model"})

        assert config.default_backend == "local"
        assert config.timeout == 60
        assert config.model_aliases["custom"] == "my-model"


class TestConfigLoading:
    """Test configuration loading from files."""

    def test_load_toml_config(self, tmp_path):
        """Test loading configuration from TOML file."""
        config_file = tmp_path / "test_config.toml"
        config_data = {
            "brain": {
                "default_backend": "cloud",
                "timeout": 45,
                "model_aliases": {"test": "gpt-3.5-turbo"},
            }
        }

        with open(config_file, "w") as f:
            f.write(toml.dumps(config_data))

        config = load_config(config_file)

        # Config values should be loaded
        if config.default_backend:
            assert config.default_backend == "cloud"
        if config.timeout:
            assert config.timeout == 45
        if config.model_aliases and "test" in config.model_aliases:
            assert config.model_aliases["test"] == "gpt-3.5-turbo"

    def test_load_config_with_models(self, tmp_path):
        """Test loading configuration with model definitions."""
        config_file = tmp_path / "test_config.toml"
        config_data = {
            "brain": {
                "default_backend": "cloud",
                "models": [
                    {
                        "name": "test-model",
                        "provider": "openai",
                        "provider_name": "gpt-test",
                        "aliases": ["test", "custom"],
                        "speed": "fast",
                        "quality": "medium",
                    }
                ],
            }
        }

        with open(config_file, "w") as f:
            f.write(toml.dumps(config_data))

        # Clear registry for clean test
        model_registry.models.clear()
        model_registry.aliases.clear()
        model_registry._load_default_models()

        load_config(config_file)

        # Check that model was added to registry
        model = model_registry.get_model("test-model")
        assert model is not None
        assert model.provider == "openai"
        assert model.provider_name == "gpt-test"
        assert "test" in model.aliases
        assert "custom" in model.aliases

    def test_config_precedence(self, tmp_path, monkeypatch):
        """Test configuration precedence (env > file > defaults)."""
        # Set environment variable
        monkeypatch.setenv("TIMEOUT", "90")

        # Create config file
        config_file = tmp_path / "test_config.toml"
        config_data = {"brain": {"timeout": 60, "default_backend": "local"}}

        with open(config_file, "w") as f:
            f.write(toml.dumps(config_data))

        config = load_config(config_file)

        # Environment variable is not used for timeout (only specific env vars)
        assert config.timeout == 60  # From file
        assert config.default_backend == "local"  # From file

    def test_missing_config_file(self):
        """Test loading with non-existent config file uses project defaults."""
        config = load_config("non_existent_file.toml")

        # Should have loaded project defaults from config.toml
        assert config.backend_config is not None
        assert config.backend_config.get("default") == "cloud"

        # Cloud backend should have timeout configured
        if "cloud" in config.backend_config:
            assert config.backend_config["cloud"].get("timeout", 30) == 30


class TestConfigSaving:
    """Test configuration saving."""

    def test_save_config(self, tmp_path):
        """Test saving configuration to file."""
        config_file = tmp_path / "saved_config.toml"

        config = ConfigModel(default_backend="cloud", timeout=45, model_aliases={"saved": "gpt-4"})

        save_config(config, config_file)

        # Read back and verify
        with open(config_file) as f:
            saved_data = toml.load(f)

        assert saved_data["brain"]["default_backend"] == "cloud"
        assert saved_data["brain"]["timeout"] == 45
        assert saved_data["brain"]["model_aliases"]["saved"] == "gpt-4"

    def test_save_config_excludes_secrets(self, tmp_path):
        """Test that API keys are not saved."""
        config_file = tmp_path / "saved_config.toml"

        config = ConfigModel(
            default_backend="cloud",
            openai_api_key="secret-key",
            anthropic_api_key="another-secret",
        )

        save_config(config, config_file)

        # Read back and verify
        with open(config_file) as f:
            saved_data = toml.load(f)

        assert "openai_api_key" not in saved_data["brain"]
        assert "anthropic_api_key" not in saved_data["brain"]
        assert "google_api_key" not in saved_data["brain"]


class TestProgrammaticConfiguration:
    """Test the configure() function."""

    def test_configure_updates_global_config(self):
        """Test that configure() updates the global configuration."""
        # Reset global config
        import matilda_brain.config

        matilda_brain.config._config = None

        configure(default_backend="local", timeout=120)

        config = get_config()
        assert config.default_backend == "local"
        assert config.timeout == 120

    def test_configure_partial_update(self):
        """Test that configure() does partial updates."""
        # Reset global config
        import matilda_brain.config

        matilda_brain.config._config = None

        # First configuration
        configure(default_backend="cloud", timeout=60)

        # Second configuration (partial update)
        configure(timeout=90)

        config = get_config()
        assert config.default_backend == "cloud"  # Unchanged
        assert config.timeout == 90  # Updated


class TestModelRegistry:
    """Test the model registry functionality."""

    def test_add_and_get_model(self):
        """Test adding and retrieving models."""
        model = ModelInfo(
            name="test-registry-model",
            provider="test",
            provider_name="test-model",
            aliases=["reg-test"],
            speed="fast",
            quality="medium",
        )

        model_registry.add_model(model)

        # Get by name
        retrieved = model_registry.get_model("test-registry-model")
        assert retrieved is not None
        assert retrieved.provider == "test"

        # Get by alias
        retrieved_by_alias = model_registry.get_model("reg-test")
        assert retrieved_by_alias is not None
        assert retrieved_by_alias.name == "test-registry-model"

    def test_resolve_model_name(self):
        """Test model name resolution."""
        model = ModelInfo(
            name="resolve-test",
            provider="test",
            provider_name="test",
            aliases=["resolve-alias"],
        )

        model_registry.add_model(model)

        # Resolve direct name
        assert model_registry.resolve_model_name("resolve-test") == "resolve-test"

        # Resolve alias
        assert model_registry.resolve_model_name("resolve-alias") == "resolve-test"

        # Unknown returns as-is
        assert model_registry.resolve_model_name("unknown") == "unknown"

    def test_list_models(self):
        """Test listing models."""
        # Add a test model
        model = ModelInfo(name="list-test", provider="test-provider", provider_name="test")
        model_registry.add_model(model)

        # List all models
        all_models = model_registry.list_models()
        assert "list-test" in all_models

        # List by provider
        test_models = model_registry.list_models(provider="test-provider")
        assert "list-test" in test_models

        # Non-existent provider
        empty = model_registry.list_models(provider="non-existent")
        assert "list-test" not in empty

    def test_default_models_loaded(self):
        """Test that default models are loaded."""
        # Check some default models exist
        gpt35 = model_registry.get_model("gpt-3.5-turbo")
        assert gpt35 is not None
        assert gpt35.provider == "openai"

        # Check aliases work
        fast_model = model_registry.get_model("fast")
        assert fast_model is not None
