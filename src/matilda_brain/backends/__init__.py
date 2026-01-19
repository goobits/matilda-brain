"""Backend implementations for different AI providers."""

from typing import TYPE_CHECKING, Optional, Type

from .base import BaseBackend
from .cloud import CloudBackend
from .hub import HubBackend

# Conditionally import local backend
try:
    from .local import LocalBackend

    HAS_LOCAL_BACKEND = True
    __all__ = ["BaseBackend", "CloudBackend", "LocalBackend", "HubBackend"]
except ImportError:
    if TYPE_CHECKING:
        from .local import LocalBackend
    else:
        LocalBackend: Optional[Type[BaseBackend]] = None
    HAS_LOCAL_BACKEND = False
    __all__ = ["BaseBackend", "CloudBackend", "HubBackend"]
