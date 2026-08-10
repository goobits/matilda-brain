# Extensibility

## Custom tools

```python
from matilda_brain import ask
from matilda_brain.tools import tool


@tool(name="lookup_order", category="orders")
def lookup_order(order_id: str) -> str:
    """Return the status of an order."""
    return f"{order_id}: shipped"


print(ask("Where is order A123?", tools=[lookup_order]))
```

Type hints and the docstring become the model-facing tool schema. The decorated function remains callable as normal.

Built-in tools:

```python
from matilda_brain import ask
from matilda_brain.tools.builtins import calculate, get_current_time

response = ask("What time is it in UTC, and what is 17 * 23?", tools=[get_current_time, calculate])
```

## Safety policy

Every model-requested tool call passes through `ToolPolicy` and `ExecutionConfig`.

- File paths must stay inside configured roots.
- HTTP tools reject credentials in URLs and private/local targets by default.
- Python execution uses a restricted subprocess, import allowlist, timeout, and output bound.
- Risky calls can require approval.

Persistent policy belongs in TOML:

```toml
[brain.tools.policy]
file_roots = ["~/Projects/safe-workspace"]
allow_private_networks = false
require_approval = true
```

Use the narrowest roots and do not enable private networks unless the calling application explicitly owns that authority.

## Custom backend plugin

```python
from collections.abc import AsyncIterator
from typing import Any

from matilda_brain import AIResponse
from matilda_brain.backends import BaseBackend


class EchoBackend(BaseBackend):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def is_available(self) -> bool:
        return True

    async def ask(self, prompt: str, **kwargs: Any) -> AIResponse:
        return AIResponse(str(prompt), model="echo", backend=self.name)

    async def astream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        yield str(prompt)

    async def models(self) -> list[str]:
        return ["echo"]

    async def status(self) -> dict[str, Any]:
        return {"backend": self.name, "available": True}


def register_plugin(registry) -> None:
    registry.register_backend("echo", EchoBackend, version="1.0.0")
```

## Discovery and migration

Brain searches these locations in order:

1. `~/.matilda/brain/plugins/`
2. `./matilda_brain_plugins/`
3. Legacy `~/.config/ai/plugins/`, `~/.ai/plugins/`, and `./ai_plugins/`
4. Built-in plugin directory

Each Python file or package must expose `register_plugin(registry)`. Load an explicit file with:

```python
from pathlib import Path

from matilda_brain import load_plugin

load_plugin(Path("echo_backend.py"))
```

Runnable plugin implementations are in [`examples/plugins`](../examples/plugins/README.md).
