"""Tests for the plugin system."""

from typing import Any, AsyncIterator, Dict, List

import pytest

from matilda_brain import AIResponse, PluginValidationError
from matilda_brain.backends import BaseBackend
from matilda_brain.plugins import BackendPlugin, PluginRegistry, plugin_registry


class MockTestBackend(BaseBackend):
    """A simple test backend for plugin testing."""

    @property
    def name(self) -> str:
        return "test"

    @property
    def is_available(self) -> bool:
        return True

    async def ask(self, prompt: str, **kwargs) -> AIResponse:
        return AIResponse(f"Test response to: {prompt}", model="test-model", backend=self.name)

    async def astream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        for word in f"Test response to: {prompt}".split():
            yield word + " "

    async def models(self) -> List[str]:
        return ["test-model"]

    async def status(self) -> Dict[str, Any]:
        return {"backend": self.name, "available": True}


class TestPluginRegistry:
    """Test the PluginRegistry class."""

    def test_register_plugin(self):
        """Test registering a plugin."""
        registry = PluginRegistry()

        plugin = BackendPlugin(
            name="test-plugin",
            backend_class=MockTestBackend,
            version="1.0.0",
            description="Test plugin",
        )

        registry.register_plugin(plugin)

        assert "test-plugin" in registry.plugins
        assert registry.plugins["test-plugin"].backend_class == MockTestBackend

    def test_register_backend_shortcut(self):
        """Test the register_backend shortcut method."""
        registry = PluginRegistry()

        registry.register_backend("test-backend", MockTestBackend, version="2.0.0", description="Test backend")

        assert "test-backend" in registry.plugins
        assert registry.plugins["test-backend"].version == "2.0.0"

    def test_register_invalid_backend(self):
        """Test that non-BaseBackend classes are rejected."""
        registry = PluginRegistry()

        class NotABackend:
            pass

        with pytest.raises(TypeError):
            registry.register_backend("invalid", NotABackend)

    def test_get_backend_class(self):
        """Test retrieving a backend class."""
        registry = PluginRegistry()
        registry.register_backend("test", MockTestBackend)

        backend_class = registry.get_backend_class("test")
        assert backend_class == MockTestBackend

        # Non-existent backend
        assert registry.get_backend_class("non-existent") is None

    def test_create_backend(self):
        """Test creating a backend instance."""
        registry = PluginRegistry()
        registry.register_backend("test", MockTestBackend)

        backend = registry.create_backend("test", {"timeout": 60})
        assert backend is not None
        assert backend.name == "test"
        assert backend.timeout == 60

        # Non-existent backend
        assert registry.create_backend("non-existent") is None

    def test_list_plugins(self):
        """Test listing all plugins."""
        registry = PluginRegistry()

        registry.register_backend("test1", MockTestBackend, version="1.0.0", author="Test Author")

        plugins = registry.list_plugins()

        # Find our test plugin
        test_plugin = next((p for p in plugins if p["name"] == "test1"), None)
        assert test_plugin is not None
        assert test_plugin["version"] == "1.0.0"
        assert test_plugin["author"] == "Test Author"
        assert test_plugin["class"] == "MockTestBackend"


class TestPluginLoading:
    """Test plugin file loading."""

    def test_load_plugin_from_file(self, tmp_path):
        """Test loading a plugin from a Python file."""
        plugin_file = tmp_path / "test_plugin.py"

        plugin_code = """
from matilda_brain.backends import BaseBackend
from matilda_brain import AIResponse

class FileMockTestBackend(BaseBackend):
    @property
    def name(self):
        return "file-test"

    @property
    def is_available(self):
        return True

    async def ask(self, prompt, **kwargs):
        return AIResponse("File plugin response", model="file-model", backend=self.name)

    async def astream(self, prompt, **kwargs):
        yield "File plugin response"

    async def models(self):
        return ["file-model"]

    async def status(self):
        return {"backend": self.name, "available": True}

def register_plugin(registry):
    registry.register_backend("file-test", FileMockTestBackend, version="1.0.0")
"""

        with open(plugin_file, "w") as f:
            f.write(plugin_code)

        registry = PluginRegistry()
        registry._load_plugin_from_file(plugin_file)

        # Check that plugin was loaded
        assert "file-test" in registry.plugins
        backend = registry.create_backend("file-test")
        assert backend is not None
        assert backend.name == "file-test"

    def test_load_plugin_without_register_function(self, tmp_path):
        """Test loading a file without register_plugin function."""
        plugin_file = tmp_path / "invalid_plugin.py"

        with open(plugin_file, "w") as f:
            f.write("# No register_plugin function")

        registry = PluginRegistry()
        # Should raise PluginValidationError for missing register_plugin
        with pytest.raises(PluginValidationError) as exc_info:
            registry._load_plugin_from_file(plugin_file)

        assert "must define a 'register_plugin' function" in str(exc_info.value)

    def test_load_plugin_package(self, tmp_path):
        """Test loading a plugin from a package directory."""
        package_dir = tmp_path / "test_package"
        package_dir.mkdir()

        # Create __init__.py with plugin
        init_file = package_dir / "__init__.py"

        plugin_code = """
from matilda_brain.backends import BaseBackend
from matilda_brain import AIResponse

class PackageBackend(BaseBackend):
    @property
    def name(self):
        return "package-test"

    @property
    def is_available(self):
        return True

    async def ask(self, prompt, **kwargs):
        return AIResponse("Package response", model="package-model", backend=self.name)

    async def astream(self, prompt, **kwargs):
        yield "Package response"

    async def models(self):
        return ["package-model"]

    async def status(self):
        return {"backend": self.name, "available": True}

def register_plugin(registry):
    registry.register_backend("package-test", PackageBackend)
"""

        with open(init_file, "w") as f:
            f.write(plugin_code)

        registry = PluginRegistry()
        registry._load_plugin_from_package(package_dir)

        # Check that plugin was loaded
        assert "package-test" in registry.plugins

    def test_discover_plugins(self, tmp_path):
        """Test plugin discovery from directory."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create a plugin file
        plugin_file = plugins_dir / "discovered_plugin.py"

        plugin_code = """
from matilda_brain.backends import BaseBackend
from matilda_brain import AIResponse

class DiscoveredBackend(BaseBackend):
    @property
    def name(self):
        return "discovered"

    @property
    def is_available(self):
        return True

    async def ask(self, prompt, **kwargs):
        return AIResponse("Discovered", model="discovered-model", backend=self.name)

    async def astream(self, prompt, **kwargs):
        yield "Discovered"

    async def models(self):
        return ["discovered-model"]

    async def status(self):
        return {"backend": self.name, "available": True}

def register_plugin(registry):
    registry.register_backend("discovered", DiscoveredBackend)
"""

        with open(plugin_file, "w") as f:
            f.write(plugin_code)

        registry = PluginRegistry()
        registry._plugin_paths = [plugins_dir]  # Override default paths
        registry.discover_plugins()

        # Check that plugin was discovered
        assert "discovered" in registry.plugins


class TestGlobalRegistry:
    """Test the global plugin registry."""

    def test_global_registry_exists(self):
        """Test that global registry is available."""
        from matilda_brain.plugins import plugin_registry

        assert plugin_registry is not None
        assert isinstance(plugin_registry, PluginRegistry)

    def test_register_backend_function(self):
        """Test the module-level register_backend function."""
        from matilda_brain.plugins import register_backend

        # Create a unique backend to avoid conflicts
        class UniqueMockTestBackend(MockTestBackend):
            @property
            def name(self):
                return "unique-test"

        register_backend("unique-test", UniqueMockTestBackend, version="1.0.0")

        # Check it was registered in global registry
        assert "unique-test" in plugin_registry.plugins
