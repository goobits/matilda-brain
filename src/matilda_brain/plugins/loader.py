"""Plugin system for custom backends."""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..backends.base import BaseBackend
from ..core.exceptions import PluginLoadError, PluginValidationError
from ..internal.utils import get_logger

logger = get_logger(__name__)


class BackendPlugin:
    """
    Metadata for a backend plugin.
    """

    def __init__(
        self,
        name: str,
        backend_class: Type[BaseBackend],
        version: str = "1.0.0",
        description: str = "",
        author: str = "",
        requires: Optional[List[str]] = None,
    ):
        self.name = name
        self.backend_class = backend_class
        self.version = version
        self.description = description
        self.author = author
        self.requires = requires or []


class PluginRegistry:
    """
    Registry for managing backend plugins.
    """

    def __init__(self) -> None:
        self.plugins: Dict[str, BackendPlugin] = {}
        self._plugin_paths: List[Path] = []
        self._setup_default_paths()

    def _setup_default_paths(self) -> None:
        """Set up default plugin search paths."""
        self._plugin_paths = [
            Path.home() / ".config" / "ai" / "plugins",
            Path.home() / ".ai" / "plugins",
            Path.cwd() / "ai_plugins",
            Path(__file__).parent / "plugins",  # Built-in plugins
        ]

    def add_plugin_path(self, path: Path) -> None:
        """Add a custom plugin search path."""
        if path not in self._plugin_paths:
            self._plugin_paths.append(path)
            logger.debug(f"Added plugin path: {path}")

    def register_plugin(self, plugin: BackendPlugin) -> None:
        """
        Register a backend plugin.

        Args:
            plugin: BackendPlugin instance
        """
        if plugin.name in self.plugins:
            logger.warning(f"Overwriting existing plugin: {plugin.name}")

        self.plugins[plugin.name] = plugin
        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")

    def register_backend(self, name: str, backend_class: Type[BaseBackend], **metadata: Any) -> None:
        """
        Convenience method to register a backend class directly.

        Args:
            name: Backend name
            backend_class: Backend class (must inherit from BaseBackend)
            **metadata: Additional metadata (version, description, etc.)
        """
        if not issubclass(backend_class, BaseBackend):
            raise TypeError("Backend class must inherit from BaseBackend")

        plugin = BackendPlugin(name, backend_class, **metadata)
        self.register_plugin(plugin)

    def get_backend_class(self, name: str) -> Optional[Type[BaseBackend]]:
        """
        Get a backend class by name.

        Args:
            name: Backend name

        Returns:
            Backend class or None if not found
        """
        plugin = self.plugins.get(name)
        return plugin.backend_class if plugin else None

    def create_backend(self, name: str, config: Optional[Dict[str, Any]] = None) -> Optional[BaseBackend]:
        """
        Create a backend instance by name.

        Args:
            name: Backend name
            config: Configuration for the backend

        Returns:
            Backend instance or None if not found
        """
        backend_class = self.get_backend_class(name)
        if backend_class:
            try:
                return backend_class(config)
            except Exception as e:
                raise PluginValidationError(name, f"Failed to instantiate backend: {e}") from e
        return None

    def discover_plugins(self) -> None:
        """
        Discover and load plugins from configured paths.
        """
        for path in self._plugin_paths:
            if path.exists() and path.is_dir():
                self._load_plugins_from_directory(path)

    def _load_plugins_from_directory(self, directory: Path) -> None:
        """
        Load all plugins from a directory.

        Args:
            directory: Directory to search for plugins
        """
        logger.debug(f"Searching for plugins in: {directory}")

        # Look for Python files
        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("_"):
                continue  # Skip private modules

            try:
                self._load_plugin_from_file(py_file)
            except Exception as e:
                logger.warning(f"Failed to load plugin from {py_file}: {e}")

        # Look for plugin packages (directories with __init__.py)
        for subdir in directory.iterdir():
            if subdir.is_dir() and (subdir / "__init__.py").exists():
                try:
                    self._load_plugin_from_package(subdir)
                except Exception as e:
                    logger.warning(f"Failed to load plugin package from {subdir}: {e}")
                    # Don't raise here to allow other plugins to load

    def _load_plugin_from_file(self, file_path: Path) -> None:
        """
        Load a plugin from a Python file.

        Args:
            file_path: Path to the Python file
        """
        module_name = f"ai_plugin_{file_path.stem}"

        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                # Look for register_plugin function
                if hasattr(module, "register_plugin"):
                    module.register_plugin(self)
                    logger.debug(f"Loaded plugin from {file_path}")
                else:
                    raise PluginValidationError(
                        str(file_path),
                        "Plugin must define a 'register_plugin' function",
                    )
            else:
                raise PluginLoadError(str(file_path), "Failed to create module spec")
        except ImportError as e:
            raise PluginLoadError(str(file_path), f"Import error: {e}") from e
        except Exception as e:
            if isinstance(e, (PluginLoadError, PluginValidationError)):
                raise
            raise PluginLoadError(str(file_path), str(e)) from e

    def _load_plugin_from_package(self, package_path: Path) -> None:
        """
        Load a plugin from a package directory.

        Args:
            package_path: Path to the package directory
        """
        # Add parent directory to sys.path temporarily
        parent_dir = str(package_path.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        try:
            module_name = package_path.name
            module = importlib.import_module(module_name)

            # Look for register_plugin function
            if hasattr(module, "register_plugin"):
                module.register_plugin(self)
                logger.debug(f"Loaded plugin package from {package_path}")
            else:
                logger.debug(f"No register_plugin function in {package_path}")

        finally:
            # Remove from sys.path
            if parent_dir in sys.path:
                sys.path.remove(parent_dir)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        List all registered plugins.

        Returns:
            List of plugin information dictionaries
        """
        return [
            {
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "author": plugin.author,
                "requires": plugin.requires,
                "class": plugin.backend_class.__name__,
            }
            for plugin in self.plugins.values()
        ]


# Global plugin registry
plugin_registry = PluginRegistry()


def load_plugin(file_path: Path) -> None:
    """
    Load a plugin from a specific file.

    Args:
        file_path: Path to the plugin file
    """
    plugin_registry._load_plugin_from_file(file_path)


def discover_plugins() -> None:
    """Discover and load all available plugins."""
    plugin_registry.discover_plugins()


def register_backend(name: str, backend_class: Type[BaseBackend], **metadata: Any) -> None:
    """
    Register a custom backend.

    Args:
        name: Backend name
        backend_class: Backend class
        **metadata: Additional metadata
    """
    plugin_registry.register_backend(name, backend_class, **metadata)
