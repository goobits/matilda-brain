# Extensibility Guide

Add custom backends, tools, and plugins.

## Custom Backends

Implement `BaseBackend` and register it:

```python
from matilda_brain.backends import BaseBackend
from matilda_brain.models import AIResponse

class MyBackend(BaseBackend):
    @property
    def name(self) -> str:
        return "my-backend"

    @property
    def is_available(self) -> bool:
        return True

    async def ask(self, prompt: str, **kwargs) -> AIResponse:
        return AIResponse("ok", model="my-model", backend=self.name)
```

Register in a plugin or via configuration. See `matilda-brain/docs/api-reference.md`.

## Custom Tools

```python
from matilda_brain.tools import tool

@tool
def my_tool(value: str) -> str:
    return f"Value: {value}"
```

## Plugins

Plugins are discovered from:

- `~/.config/matilda-brain/plugins/`
- `~/.ai/plugins/`
- `./ai_plugins/`

Manual load:

```python
from matilda_brain import load_plugin
from pathlib import Path

load_plugin(Path("my_plugin.py"))
```

See `matilda-brain/examples/plugins/` for full examples.
