# Matilda Brain

One CLI and Python API for cloud and local language models, streaming conversations, function calling, persistent sessions, and the Matilda HTTP protocol.

## Install

```bash
./scripts/setup.sh install
# Development checkout
./scripts/setup.sh install --dev
```

Python 3.11-3.13 is supported. The command is `brain`.

## CLI

```bash
brain "What is Python?"
brain ask --model @fast --stream "Explain this repository"
echo "print('hello')" | brain ask "Review this code"
brain chat --model @claude

brain models
brain status
brain tools list
brain --help
```

`brain ask --tools` and `brain chat --tools` expose all registered tools except names disabled with `brain tools disable NAME`.

## Python API

```python
from matilda_brain import ask, chat, stream

response = ask("What is Python?", model="@fast")
print(response)
print(response.model, response.backend)

for chunk in stream("Tell me a short story"):
    print(chunk, end="", flush=True)

with chat(system="Answer concisely") as session:
    session.ask("My name is Alice")
    print(session.ask("What is my name?"))
```

### Function calling

```python
from matilda_brain import ask
from matilda_brain.tools import tool


@tool
def get_weather(city: str) -> str:
    """Return the current weather for a city."""
    return f"Weather in {city}: sunny"


response = ask("What is the weather in Seattle?", tools=[get_weather])
print(response)
```

Tools run through a central policy that bounds file access, blocks private-network requests by default, constrains code execution, and supports approval thresholds. See [Extensibility](docs/extensibility.md).

## Configuration

The single configuration owner is `~/.matilda/config.toml`, under the `[brain]` section. Override the file path with `MATILDA_CONFIG`.

```bash
brain config list
brain config get models.default
brain config set models.default openai/gpt-4o-mini
brain config set alias.fast openrouter/openai/gpt-4o-mini

export OPENAI_API_KEY=sk-...
export OPENROUTER_API_KEY=sk-or-...
```

See the [Configuration Guide](docs/configuration.md) for precedence, supported environment variables, and tool policy settings.

## HTTP server

```bash
export MATILDA_API_TOKEN="$(openssl rand -hex 32)"
brain serve                         # 127.0.0.1:8772
```

`GET /health` is public. Other endpoints require `Authorization: Bearer $MATILDA_API_TOKEN`. Cross-origin access is denied unless `ALLOWED_ORIGINS` is configured.

## State

- New CLI sessions are written to `~/.matilda/brain/sessions/`.
- Plugins are discovered first from `~/.matilda/brain/plugins/` and `./matilda_brain_plugins/`, then from the legacy `ai` plugin locations.
- Legacy YAML configuration is not loaded; use the shared TOML file.

## Development

```bash
make check             # formatting, lint, types, offline tests, coverage floor
make test-unit
make test-integration  # deterministic HTTP mocks, no provider charges
./scripts/test.py integration --real-api --force  # explicit paid/network run
```

The complete workflow is in [Development](docs/development.md), with runnable examples in [examples](examples/README.md).

## Related projects

- [Matilda](https://github.com/goobits/matilda) - orchestrator and desktop app
- [Matilda Ears](https://github.com/goobits/matilda-ears) - speech to text
- [Matilda Voice](https://github.com/goobits/matilda-voice) - text to speech

## License

MIT - see [LICENSE](LICENSE).
