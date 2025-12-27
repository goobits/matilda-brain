"""Core data models for the AI library."""

import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from matilda_brain.tools.base import ToolResult


class AIResponse(str):
    """
    AI response that behaves like a string but contains rich metadata.

    This class extends str so it can be used anywhere a string is expected,
    while providing additional metadata about the AI response.
    """

    def __new__(cls, content: str, **kwargs: Any) -> "AIResponse":
        """Create new AIResponse instance."""
        obj = str.__new__(cls, content)
        return obj

    def __init__(
        self,
        content: str,
        *,
        model: Optional[str] = None,
        backend: Optional[str] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        time_taken: Optional[float] = None,
        cost: Optional[float] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        tool_result: Optional["ToolResult"] = None,
    ):
        """
        Initialize AIResponse.

        Args:
            content: The response text
            model: Model ID that generated the response
            backend: Backend that handled the request (local/cloud)
            tokens_in: Input tokens used
            tokens_out: Output tokens generated
            time_taken: Time taken in seconds
            cost: Estimated cost in USD
            error: Error message if request failed
            metadata: Additional metadata
            timestamp: When the response was generated
            tool_result: Result of any tool calls made during this response
        """
        super().__init__()
        self.model = model
        self.backend = backend
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.time_taken = time_taken
        self.cost = cost
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now()
        self.tool_result = tool_result

    @property
    def failed(self) -> bool:
        """True if the request failed."""
        return self.error is not None

    @property
    def succeeded(self) -> bool:
        """True if the request succeeded."""
        return self.error is None

    @property
    def time(self) -> Optional[float]:
        """Alias for time_taken."""
        return self.time_taken

    @property
    def tools_called(self) -> bool:
        """True if tools were called during this response."""
        return self.tool_result is not None and len(self.tool_result.calls) > 0

    @property
    def tool_calls(self) -> List[Any]:
        """Get list of tool calls made during this response."""
        if self.tool_result is None:
            return []
        return cast(List[Any], self.tool_result.calls)

    @property
    def tools_succeeded(self) -> bool:
        """True if all tool calls succeeded."""
        if not self.tools_called:
            return True  # No tools called means no tool failures
        return self.tool_result is not None and self.tool_result.succeeded

    def __repr__(self) -> str:
        """String representation showing metadata."""
        return (
            f"AIResponse('{str(self)[:50]}...', "
            f"model='{self.model}', "
            f"backend='{self.backend}', "
            f"time={self.time_taken:.2f}s)"
        )


@dataclass
class ModelInfo:
    """Information about an available AI model."""

    name: str
    provider: str
    provider_name: str
    aliases: Optional[list[str]] = None
    speed: str = "medium"  # fast, medium, slow
    quality: str = "medium"  # low, medium, high
    capabilities: Optional[list[str]] = None
    context_length: Optional[int] = None
    cost_per_token: Optional[float] = None

    def __post_init__(self) -> None:
        if self.aliases is None:
            self.aliases = []
        if self.capabilities is None:
            self.capabilities = []


class ConfigModel(BaseModel):
    """Configuration model for the AI library."""

    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    api_keys: Dict[str, str] = Field(default_factory=dict)

    # Ollama Configuration
    ollama_base_url: Optional[str] = None

    # Default Settings
    default_backend: Optional[str] = None
    default_model: Optional[str] = None
    model: Optional[str] = None  # User-specified model (alias for default_model)
    timeout: Optional[int] = None
    max_retries: Optional[int] = None

    # Tool Configuration
    tools_config: Dict[str, Any] = Field(default_factory=dict)

    # Backend Configuration
    backend_config: Dict[str, Any] = Field(default_factory=dict)

    # Chat Configuration
    chat_config: Dict[str, Any] = Field(default_factory=dict)

    # Model Aliases
    model_aliases: Dict[str, str] = Field(default_factory=dict)

    # Fallback Configuration
    enable_fallbacks: bool = True
    fallback_order: List[str] = Field(default_factory=lambda: ["cloud", "local"])

    # Top-level config sections from config.yaml
    models: Dict[str, Any] = Field(default_factory=dict)
    backends: Dict[str, Any] = Field(default_factory=dict)
    tools: Dict[str, Any] = Field(default_factory=dict)
    chat: Dict[str, Any] = Field(default_factory=dict)
    logging: Dict[str, Any] = Field(default_factory=dict)
    paths: Dict[str, Any] = Field(default_factory=dict)
    env_mappings: Dict[str, Any] = Field(default_factory=dict)
    routing: Dict[str, Any] = Field(default_factory=dict)
    files: Dict[str, Any] = Field(default_factory=dict)
    constants: Dict[str, Any] = Field(default_factory=dict)  # Centralized constants

    model_config = ConfigDict(extra="forbid")


class ImageInput:
    """Represents an image input for multi-modal AI models."""

    def __init__(self, source: Union[str, Path, bytes], mime_type: Optional[str] = None):
        """
        Initialize ImageInput.

        Args:
            source: Image source - can be file path, URL, or raw bytes
            mime_type: MIME type (e.g., 'image/jpeg', 'image/png')
        """
        self.source = source
        self.mime_type = mime_type
        self._base64_cache: Optional[str] = None

    @property
    def is_path(self) -> bool:
        """Check if source is a file path."""
        return isinstance(self.source, (str, Path)) and Path(self.source).exists()

    @property
    def is_url(self) -> bool:
        """Check if source is a URL."""
        return isinstance(self.source, str) and (
            self.source.startswith("http://") or self.source.startswith("https://")
        )

    @property
    def is_bytes(self) -> bool:
        """Check if source is raw bytes."""
        return isinstance(self.source, bytes)

    def to_base64(self) -> str:
        """Convert image to base64 string."""
        if self._base64_cache:
            return self._base64_cache

        if self.is_bytes:
            assert isinstance(self.source, bytes)
            self._base64_cache = base64.b64encode(self.source).decode("utf-8")
        elif self.is_path:
            try:
                with open(self.source, "rb") as f:
                    self._base64_cache = base64.b64encode(f.read()).decode("utf-8")
            except FileNotFoundError:
                raise FileNotFoundError(f"Image file not found: {self.source}")
            except PermissionError:
                raise PermissionError(f"Permission denied reading image file: {self.source}")
            except IsADirectoryError:
                raise IsADirectoryError(f"Path is a directory, not a file: {self.source}")
            except OSError as e:
                raise OSError(f"Error reading image file {self.source}: {e}")
            except Exception as e:
                raise RuntimeError(f"Unexpected error reading image file {self.source}: {e}")
        elif self.is_url:
            # URL images typically sent as-is to APIs
            return str(self.source)
        else:
            raise ValueError("Invalid image source type")

        return self._base64_cache

    def get_mime_type(self) -> str:
        """Get or infer MIME type."""
        if self.mime_type:
            return self.mime_type

        if self.is_path:
            assert isinstance(self.source, (str, Path))
            path = Path(self.source)
            ext = path.suffix.lower()

            # Try to get mime types from config
            try:
                from ..config.schema import load_project_defaults

                project_defaults = load_project_defaults()
                default_mime_types = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                    ".bmp": "image/bmp",
                }
                mime_map: Dict[str, str] = project_defaults.get("files", {}).get("mime_types", default_mime_types)
            except (ImportError, AttributeError, KeyError, TypeError):
                # Fallback to hardcoded if config loading fails
                mime_map = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                    ".bmp": "image/bmp",
                }

            mime_type = mime_map.get(ext, "image/jpeg")
            return mime_type

        return "image/jpeg"  # Default
