# Python API

The package root lazily exposes the stable application API:

```python
from matilda_brain import (
    AIResponse,
    ImageInput,
    PersistentChatSession,
    StatelessResponse,
    achat,
    ask,
    ask_async,
    chat,
    configure,
    stateless,
    stream,
    stream_async,
)
```

## Requests

### `ask`

```python
response = ask(
    prompt,
    *,
    model=None,
    system=None,
    temperature=None,
    max_tokens=None,
    backend=None,
    tools=None,
    **backend_options,
)
```

`prompt` is a string or a list containing strings and `ImageInput` values. `backend` accepts `"cloud"`, `"local"`, `"hub"`, or a `BaseBackend` instance. The return value is an `AIResponse` string subclass.

```python
response = ask("Explain dependency inversion", model="@coding", temperature=0.2)
print(response)
print(response.model, response.backend, response.time_taken)
```

### `stream`

`stream()` accepts the same request fields and yields text chunks:

```python
for chunk in stream("Write a haiku"):
    print(chunk, end="", flush=True)
```

### `chat`

```python
with chat(system="Be concise", model="@fast", tools=[my_tool]) as session:
    first = session.ask("Remember the number 42")
    second = session.ask("What number did I give you?")
```

The yielded `PersistentChatSession` owns conversation history, response metadata, optional Matilda Memory access, and explicit cleanup. Useful methods include:

- `ask()` / `ask_async()`
- `stream()` / `stream_async()`
- `clear()`
- `save(path)` / `PersistentChatSession.load(path)`
- `export_messages("text" | "markdown" | "json")`
- `get_summary()`
- `close()`

Session files use JSON. Loading pickle sessions is intentionally rejected.

### `stateless`

```python
response = stateless(
    "Continue the analysis",
    history=[
        {"role": "user", "content": "Analyze this design"},
        {"role": "assistant", "content": "The main boundary is..."},
    ],
    tools=["calculate"],
)
print(response.content)
```

`stateless()` does not create or mutate a session. It returns `StatelessResponse(content, tool_calls, finish_reason, usage, model)`.

## Async API

```python
import asyncio

from matilda_brain import achat, ask_async, stream_async


async def main() -> None:
    print(await ask_async("Hello"))

    async for chunk in stream_async("Tell me a story"):
        print(chunk, end="")

    async with achat(system="Answer briefly") as session:
        print(await session.ask_async("Why is the sky blue?"))


asyncio.run(main())
```

## Images

```python
from matilda_brain import ImageInput, ask

response = ask(
    ["Describe this image", ImageInput("diagram.png")],
    model="openai/gpt-4o",
)
```

`ImageInput` accepts a local path, HTTP(S) URL, or bytes plus an optional MIME type.

## Tools

```python
from matilda_brain import ask
from matilda_brain.tools import tool


@tool(category="weather")
def forecast(city: str, days: int = 1) -> str:
    """Return a short forecast."""
    return f"{city}: sunny for {days} day(s)"


response = ask("Forecast Seattle for two days", tools=[forecast])
```

Decorated functions stay directly callable. The registry also exposes `get_tool`, `list_tools`, `resolve_tools`, `register_tool`, and `unregister_tool`. Built-ins live in `matilda_brain.tools.builtins`.

Tool-capable models may request multiple rounds. Brain executes each round through the central policy and returns final text plus `AIResponse.tool_calls` metadata.

## `AIResponse`

`AIResponse` behaves like `str` and provides:

- `model`, `backend`, `metadata`, `timestamp`
- `tokens_in`, `tokens_out`, `cost`, `time_taken` (`time` alias)
- `succeeded`, `failed`, `error`
- `tools_called`, `tool_calls`, `tools_succeeded`

## Configuration

```python
from matilda_brain import configure

configure(default_backend="cloud", default_model="openai/gpt-4o-mini", timeout=60)
```

Runtime configuration is process-local. Persistent configuration belongs in the shared `[brain]` TOML section; see [Configuration](configuration.md).

## Backends and plugins

Public backend classes are `CloudBackend`, `LocalBackend`, and `HubBackend`. Custom backend packages implement `BaseBackend` and register through:

```python
from pathlib import Path

from matilda_brain import load_plugin, register_backend

load_plugin(Path("my_plugin.py"))
register_backend("custom", CustomBackend)
```

See [Extensibility](extensibility.md) and the [plugin examples](../examples/plugins/README.md).

## Exceptions

Domain exceptions are exported from `matilda_brain`, including:

- `BackendError`, `BackendNotAvailableError`, `BackendTimeoutError`
- `ModelError`, `ModelNotFoundError`, `ModelNotSupportedError`
- `ConfigurationError`, `ConfigFileError`, `APIKeyError`
- `ValidationError`, `InvalidPromptError`, `InvalidParameterError`
- `RateLimitError`, `QuotaExceededError`
- `PluginError`, `SessionError`, and their load/save specializations

Catch the narrowest useful exception:

```python
from matilda_brain import BackendTimeoutError, ask

try:
    response = ask("Long task")
except BackendTimeoutError:
    response = ask("Short summary", model="@fast")
```
