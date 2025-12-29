# Extensibility Guide

The AI library is designed to be highly extensible, allowing you to add custom backends, models, and configurations to meet your specific needs.

## Table of Contents

1. [Configuration System](#configuration-system)
2. [Model Registry](#model-registry)
3. [Plugin System](#plugin-system)
4. [Creating Custom Backends](#creating-custom-backends)
5. [Advanced Topics](#advanced-topics)

## Configuration System

### Configuration Hierarchy

The library loads configuration from multiple sources with the following precedence (highest to lowest):

1. **Programmatic configuration** via `configure()`
2. **Environment variables**
3. **Configuration files** (YAML)
4. **Default values**

### Configuration Files

The library searches for configuration files in these locations:
- `./ai.yaml` or `./ai.yml` (current directory)
- `./.ai.yaml` or `./.ai.yml` (hidden file in current directory)
- `~/.config/matilda-brain/config.yaml` or `~/.config/matilda-brain/config.yml`
- `~/.ai.yaml` or `~/.ai.yml`

### Configuration Schema

```yaml
# Basic settings
default_backend: auto  # auto, local, cloud, or custom backend name
default_model: null    # null for auto-selection or specific model
timeout: 30           # Request timeout in seconds
max_retries: 3        # Maximum retry attempts
enable_fallbacks: true # Enable automatic fallback to other backends

# Backend fallback order
fallback_order:
  - cloud
  - local

# Local backend settings
ollama_base_url: http://localhost:11434

# Model aliases for convenience
model_aliases:
  fast: gpt-3.5-turbo
  best: gpt-4
  coding: claude-3-sonnet
  local: llama2

# Custom model definitions
models:
  - name: my-custom-model
    provider: openai
    provider_name: ft:gpt-3.5-turbo:org:custom:id
    aliases: [custom, tuned]
    speed: fast
    quality: high
    capabilities: [text, domain-specific]
    context_length: 4096
    cost_per_token: 0.0001

# Backend-specific configuration
backends:
  local:
    default_model: llama2
    timeout: 60
  cloud:
    default_model: gpt-3.5-turbo
    provider_order: [openai, anthropic, google]

# Smart routing configuration
routing:
  code_keywords: [code, function, debug]
  speed_keywords: [quick, fast, simple]
  quality_keywords: [analyze, explain, comprehensive]
```

### Programmatic Configuration

```python
from matilda_brain import configure

# Update configuration at runtime
configure(
    default_backend="cloud",
    default_model="gpt-4",
    timeout=60,
    openai_api_key="your-key",
    # Any other configuration options
)
```

## Model Registry

The model registry manages all available models and their metadata.

### Accessing the Registry

```python
from matilda_brain import model_registry

# List all models
all_models = model_registry.list_models()

# List models from a specific provider
openai_models = model_registry.list_models(provider="openai")

# Get model information
model_info = model_registry.get_model("gpt-4")
print(f"Speed: {model_info.speed}")
print(f"Quality: {model_info.quality}")
print(f"Capabilities: {model_info.capabilities}")

# List all aliases
aliases = model_registry.list_aliases()
```

### Adding Custom Models

```python
from matilda_brain import model_registry
from matilda_brain.models import ModelInfo

# Add a custom model
model_registry.add_model(ModelInfo(
    name="my-model",
    provider="openai",
    provider_name="gpt-3.5-turbo-16k",
    aliases=["long-context", "16k"],
    speed="fast",
    quality="medium",
    capabilities=["text", "chat"],
    context_length=16384,
    cost_per_token=0.00002
))

# Now you can use it
response = ask("Long document analysis...", model="long-context")
```

### Model Metadata

Models can include the following metadata:
- `name`: Unique identifier
- `provider`: Backend provider (openai, anthropic, google, local)
- `provider_name`: Actual model name used by the provider
- `aliases`: Alternative names for the model
- `speed`: Performance rating (fast, medium, slow)
- `quality`: Output quality rating (low, medium, high)
- `capabilities`: List of capabilities (text, code, reasoning, vision, etc.)
- `context_length`: Maximum context window size
- `cost_per_token`: Estimated cost per token (for cloud models)

## Plugin System

### Plugin Discovery

Plugins are automatically discovered from:
1. `~/.config/matilda-brain/plugins/`
2. `~/.ai/plugins/`
3. `./ai_plugins/`
4. Built-in plugins directory

### Loading Plugins

```python
from matilda_brain import load_plugin, discover_plugins
from pathlib import Path

# Manually load a specific plugin
load_plugin(Path("/path/to/my_plugin.py"))

# Re-run plugin discovery
discover_plugins()

# Plugins are loaded automatically on import
import matilda_brain  # This triggers plugin discovery
```

### Plugin Structure

A plugin must have a `register_plugin` function:

```python
def register_plugin(registry):
    """Called when the plugin is loaded."""
    registry.register_backend(
        "my-backend",
        MyBackendClass,
        version="1.0.0",
        description="My custom backend",
        author="Your Name",
        requires=["dependency1", "dependency2"]
    )
```

## Creating Custom Backends

### Backend Interface

All backends must inherit from `BaseBackend` and implement required methods:

```python
from matilda_brain.backends import BaseBackend
from matilda_brain.models import AIResponse
from typing import AsyncIterator, List, Dict, Any, Optional

class MyBackend(BaseBackend):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        # Your initialization code
        # Access configuration via self.backend_config

    @property
    def name(self) -> str:
        """Backend identifier."""
        return "my-backend"

    @property
    def is_available(self) -> bool:
        """Check if backend is available."""
        # Return True if your backend can be used
        return True

    async def ask(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AIResponse:
        """Generate a complete response."""
        # Your implementation
        response_text = await your_api_call(prompt)

        return AIResponse(
            response_text,
            model=model or "default",
            backend=self.name,
            tokens_in=count_tokens(prompt),
            tokens_out=count_tokens(response_text),
            time_taken=elapsed_time,
            metadata={"custom": "data"}
        )

    async def astream(
        self,
        prompt: str,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream response chunks."""
        async for chunk in your_streaming_api(prompt):
            yield chunk

    async def models(self) -> List[str]:
        """List available models."""
        return ["model1", "model2"]

    async def status(self) -> Dict[str, Any]:
        """Get backend status."""
        return {
            "backend": self.name,
            "available": self.is_available,
            "models": await self.models()
        }
```

### Configuration Access

Backends receive configuration through their constructor:

```python
class ConfigurableBackend(BaseBackend):
    def __init__(self, config=None):
        super().__init__(config)

        # Access merged configuration
        self.api_url = self.backend_config.get("api_url", "https://api.example.com")
        self.api_key = self.backend_config.get("api_key")

        # Backend-specific config takes precedence
        # If config has backends.my-backend.timeout, it overrides global timeout
        self.timeout = self.timeout  # Already set by base class
```

### Error Handling

Always return AIResponse objects, even for errors:

```python
async def ask(self, prompt, **kwargs):
    try:
        result = await self.make_api_call(prompt)
        return AIResponse(
            result.text,
            model=result.model,
            backend=self.name
        )
    except Exception as e:
        # Return empty response with error
        return AIResponse(
            "",
            model=kwargs.get("model", "default"),
            backend=self.name,
            error=str(e)
        )
```

## Advanced Topics

### Backend Registration Methods

1. **Direct Registration**:
   ```python
   from matilda_brain import register_backend
   register_backend("name", BackendClass, version="1.0.0")
   ```

2. **Plugin File**:
   ```python
   # my_plugin.py
   def register_plugin(registry):
       registry.register_backend("name", BackendClass)
   ```

3. **Configuration**:
   ```yaml
   # In config file
   backends:
     custom:
       class_path: mymodule.MyBackend
       config:
         api_key: xxx
   ```

### Dynamic Backend Selection

The router selects backends based on:
1. Explicit backend parameter
2. Model provider (if model specified)
3. Query analysis (code, speed, quality hints)
4. Configuration preferences
5. Availability

### Extending Smart Routing

Customize routing behavior via configuration:

```yaml
routing:
  # Add custom keywords
  code_keywords: [algorithm, implement, syntax]
  speed_keywords: [quick, brief, tldr]
  quality_keywords: [detailed, thorough, comprehensive]

  # Model selection rules
  rules:
    - if: {contains: [code, python]}
      prefer_model: claude-3-sonnet
    - if: {length_gt: 200}
      prefer_model: gpt-4
```

### Testing Custom Backends

```python
import pytest
from matilda_brain import ask, register_backend
from my_backend import MyBackend

@pytest.fixture
def setup_backend():
    register_backend("test", MyBackend)

def test_basic_completion(setup_backend):
    response = ask("Test prompt", backend="test")
    assert response.backend == "test"
    assert not response.failed

def test_streaming(setup_backend):
    chunks = list(stream("Test", backend="test"))
    assert len(chunks) > 0

def test_error_handling(setup_backend):
    response = ask("Cause error", backend="test")
    assert response.failed
    assert response.error is not None
```

### Performance Considerations

1. **Connection Pooling**: Reuse connections for efficiency
2. **Async Operations**: Use proper async/await patterns
3. **Timeout Handling**: Respect configured timeouts
4. **Resource Cleanup**: Clean up resources in destructors
5. **Caching**: Consider caching model lists and status

### Security Best Practices

1. **API Key Handling**: Never log or expose API keys
2. **Input Validation**: Validate and sanitize inputs
3. **Error Messages**: Don't expose sensitive information
4. **Configuration**: Support secure configuration methods
5. **Network Security**: Use HTTPS for external APIs

## Examples

For complete working examples, see:
- [examples/plugins/echo_backend.py](../examples/plugins/echo_backend.py) - Simple echo backend
- [examples/plugins/mock_llm_backend.py](../examples/plugins/mock_llm_backend.py) - Sophisticated mock backend
- [examples/config/ai.yaml](../examples/config/ai.yaml) - Full configuration example
