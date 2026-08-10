"""Model registry and compatibility facade for configuration APIs."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..core.models import ModelInfo
from .manager import (
    ConfigManager,
    configure,
    get_config,
    load_config,
    merge_configs,
    save_config,
    set_config,
)

logger = logging.getLogger(__name__)


def load_project_defaults() -> Dict[str, Any]:
    """Compatibility helper returning defaults merged with user settings."""
    return ConfigManager().get_merged_config()


class ModelRegistry:
    """Registry for model metadata and aliases."""

    def __init__(self) -> None:
        self.models: Dict[str, ModelInfo] = {}
        self.aliases: Dict[str, str] = {}
        self._load_default_models()

    def _load_default_models(self) -> None:
        models_config = load_project_defaults().get("models", {})
        available = models_config.get("available", {}) if isinstance(models_config, dict) else {}

        if isinstance(available, dict):
            for model_name, model_config in available.items():
                if not isinstance(model_config, dict):
                    continue
                try:
                    self.add_model(
                        ModelInfo(
                            name=model_name,
                            provider=model_config.get("provider", ""),
                            provider_name=str(model_config.get("provider_name") or model_name),
                            aliases=model_config.get("aliases", []),
                            speed=model_config.get("speed", "medium"),
                            quality=model_config.get("quality", "medium"),
                            capabilities=model_config.get("capabilities", []),
                            context_length=model_config.get("context_length"),
                            cost_per_token=model_config.get("cost_per_token"),
                        )
                    )
                except (TypeError, ValueError) as exc:
                    logger.warning("Failed to load model %s: %s", model_name, exc)

        if not self.models:
            self.add_model(
                ModelInfo(
                    name="gpt-3.5-turbo",
                    provider="openai",
                    provider_name="gpt-3.5-turbo",
                    aliases=["fast", "cheap"],
                    speed="fast",
                    quality="medium",
                    capabilities=["text", "chat"],
                    context_length=4096,
                )
            )
            self.add_model(
                ModelInfo(
                    name="llama2",
                    provider="local",
                    provider_name="llama2",
                    aliases=["local", "private"],
                    capabilities=["text", "chat"],
                    context_length=4096,
                )
            )

    def add_model(self, model: ModelInfo) -> None:
        self.models[model.name] = model
        for alias in model.aliases or []:
            self.aliases[alias] = model.name

    def get_model(self, name_or_alias: str) -> Optional[ModelInfo]:
        model_name = self.aliases.get(name_or_alias, name_or_alias)
        return self.models.get(model_name)

    def resolve_model_name(self, name_or_alias: str) -> str:
        return self.aliases.get(name_or_alias, name_or_alias)

    def list_models(self, provider: Optional[str] = None) -> List[str]:
        return sorted(name for name, model in self.models.items() if provider is None or model.provider == provider)

    def list_aliases(self) -> Dict[str, str]:
        return dict(self.aliases)


_model_registry: Optional[ModelRegistry] = None


def reset_model_registry() -> None:
    global _model_registry
    _model_registry = None


def get_model_registry() -> ModelRegistry:
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
    return _model_registry


class LazyModelRegistry:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_model_registry(), name)


model_registry = LazyModelRegistry()


__all__ = [
    "ConfigManager",
    "ModelRegistry",
    "configure",
    "get_config",
    "get_model_registry",
    "load_config",
    "load_project_defaults",
    "merge_configs",
    "model_registry",
    "reset_model_registry",
    "save_config",
    "set_config",
]
