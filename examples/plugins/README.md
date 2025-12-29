# Matilda Brain Plugin Examples

This directory contains example plugins demonstrating how to extend the Matilda Brain library with custom backends.

## Available Examples

### 1. Echo Backend (`echo_backend.py`)

A simple backend that echoes back the user's prompt. This is the simplest possible backend implementation and serves as a minimal example.

**Features:**
- Echoes user prompts
- Supports streaming
- Always available (no external dependencies)

**Usage:**
```python
from matilda_brain import ask, load_plugin
from pathlib import Path

# Load the plugin
load_plugin(Path("echo_backend.py"))

# Use the backend
response = ask("Hello, world!", backend="echo")
print(response)  # "Echo: Hello, world!"
```

### 2. Mock LLM Backend (`mock_llm_backend.py`)

A more sophisticated backend that generates realistic-looking mock responses without calling any real AI service. Perfect for testing and development.

**Features:**
- Generates contextual mock responses
- Categorizes prompts (greetings, code, explanations)
- Simulates realistic delays and token counts
- Zero cost (no API calls)
- Supports all standard parameters (temperature, max_tokens, etc.)

**Usage:**
```python
from matilda_brain import ask, stream, load_plugin
from pathlib import Path

# Load the plugin
load_plugin(Path("mock_llm_backend.py"))

# Use for testing without API costs
response = ask("Explain quantum computing", backend="mock")
print(response)

# Stream responses
for chunk in stream("Write a Python function", backend="mock"):
    print(chunk, end="", flush=True)
```

## Creating Your Own Plugin

To create a custom backend plugin:

1. **Create a new Python file** with your backend implementation
2. **Inherit from BaseBackend**:
   ```python
   from matilda_brain.backends import BaseBackend

   class MyBackend(BaseBackend):
       # Implementation here
   ```

3. **Implement required methods**:
   - `name` property - Backend identifier
   - `is_available` property - Availability check
   - `ask()` - Synchronous completion
   - `astream()` - Streaming completion
   - `models()` - List available models
   - `status()` - Backend status info

4. **Add a register_plugin function**:
   ```python
   def register_plugin(registry):
       registry.register_backend(
           "my-backend",
           MyBackend,
           version="1.0.0",
           description="My custom backend"
       )
   ```

## Plugin Discovery

Plugins are automatically discovered from these locations:
- `~/.config/matilda-brain/plugins/`
- `~/.ai/plugins/`
- `./ai_plugins/`
- Built-in plugins directory

You can also manually load plugins:
```python
from matilda_brain import load_plugin
load_plugin(Path("/path/to/your/plugin.py"))
```

## Best Practices

1. **Error Handling**: Always handle errors gracefully and return appropriate AIResponse objects
2. **Async Support**: Implement proper async/await patterns
3. **Configuration**: Use the config dict passed to `__init__` for backend-specific settings
4. **Metadata**: Include useful metadata in responses for debugging
5. **Documentation**: Document your backend's capabilities and requirements

## Advanced Example: HTTP API Backend

Here's a template for creating a backend that calls a custom HTTP API:

```python
import httpx
from matilda_brain.backends import BaseBackend
from matilda_brain.models import AIResponse

class HTTPBackend(BaseBackend):
    def __init__(self, config=None):
        super().__init__(config)
        self.api_url = self.backend_config.get("api_url", "http://localhost:8000")
        self.api_key = self.backend_config.get("api_key")

    @property
    def name(self):
        return "http"

    @property
    def is_available(self):
        try:
            response = httpx.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    async def ask(self, prompt, **kwargs):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/complete",
                json={"prompt": prompt, **kwargs},
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            data = response.json()

            return AIResponse(
                data["text"],
                model=data.get("model", "custom"),
                backend=self.name,
                tokens_in=data.get("tokens_in"),
                tokens_out=data.get("tokens_out")
            )

    # ... implement other required methods
```

## Testing Your Plugin

Test your plugin thoroughly:

```python
import asyncio
from matilda_brain import ask, stream, chat
from matilda_brain.plugins import load_plugin

# Load and test
load_plugin(Path("my_plugin.py"))

# Test basic completion
response = ask("Test prompt", backend="my-backend")
assert response.backend == "my-backend"

# Test streaming
chunks = list(stream("Test streaming", backend="my-backend"))
assert len(chunks) > 0

# Test chat sessions
with chat(backend="my-backend") as session:
    response = session.ask("Hello")
    assert len(session.history) == 2
```

## Contributing

If you create a useful plugin, consider contributing it to the community! Submit a pull request with your plugin and documentation.
