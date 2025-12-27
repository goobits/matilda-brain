"""Backend implementations for different AI providers."""

from typing import TYPE_CHECKING, Optional, Type, Union

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
        LocalBackend = None  # type: Optional[Type[BaseBackend]]
    HAS_LOCAL_BACKEND = False
    __all__ = ["BaseBackend", "CloudBackend"]
