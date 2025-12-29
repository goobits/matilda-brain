"""Backend implementations for different AI providers."""

from typing import TYPE_CHECKING, Optional, Type

from .base import BaseBackend
from .cloud import CloudBackend

# Conditionally import local backend
try:
    from .local import LocalBackend

    HAS_LOCAL_BACKEND = True
    __all__ = ["BaseBackend", "CloudBackend", "LocalBackend"]
except ImportError:
    if TYPE_CHECKING:
        from .local import LocalBackend
    else:
        LocalBackend: Optional[Type[BaseBackend]] = None
    HAS_LOCAL_BACKEND = False
    __all__ = ["BaseBackend", "CloudBackend"]
