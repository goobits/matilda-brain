# Configuration

Matilda Brain has one configuration owner and one persistent file.

## Precedence

Lowest to highest:

1. Library defaults
2. `~/.matilda/config.toml` under `[brain]`
3. Environment variables, including the first discovered `.env`
4. Runtime overrides through `configure()`

Set `MATILDA_CONFIG=/path/to/config.toml` to use another shared TOML file.

## TOML shape

```toml
[brain.models]
default = "openai/gpt-4o-mini"

[brain.models.aliases]
fast = "openrouter/openai/gpt-4o-mini"

[brain.backends]
default = "cloud"
enable_fallbacks = true
fallback_order = ["cloud", "local"]

[brain.backends.local]
base_url = "http://localhost:11434"
timeout = 60

[brain.tools]
disabled = ["write_file"]

[brain.tools.policy]
allow_private_networks = false
file_roots = ["~/Projects"]
require_approval = false

[brain.api_keys]
openrouter_api_key = "sk-or-..."
```

Brain preserves other top-level sections in the shared Matilda file when it writes `[brain]`. Files written by the CLI use owner-only permissions.

## CLI

```bash
brain config list
brain config get models.default
brain config set models.default openai/gpt-4o-mini
brain config set backends.enable_fallbacks true
brain config set alias.fast openrouter/openai/gpt-4o-mini
brain config set openai_api_key sk-...
```

Use dotted keys for nested values. API-key keys are stored under `[brain.api_keys]` and mapped to their provider environment variables.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `MATILDA_CONFIG` | Shared TOML path |
| `OPENROUTER_API_KEY` | OpenRouter credentials |
| `OPENAI_API_KEY` | OpenAI credentials |
| `ANTHROPIC_API_KEY` | Anthropic credentials |
| `GOOGLE_API_KEY` | Google credentials |
| `OLLAMA_BASE_URL` | Local Ollama endpoint |
| `AI_DEFAULT_BACKEND` | Default backend |
| `AI_DEFAULT_MODEL` | Default model |
| `AI_TIMEOUT` | Request timeout in seconds |
| `AI_MAX_RETRIES` | Retry limit |
| `AI_ENABLE_FALLBACKS` | Enable backend fallback |

Environment credentials override values loaded from TOML.

## Python

```python
from matilda_brain import configure

configure(
    default_backend="cloud",
    default_model="openai/gpt-4o-mini",
    timeout=60,
)
```

`configure()` changes the current process only; use the CLI or edit TOML for persistent settings.

## Migration

Legacy YAML and `AI_CONFIG_FILE` are no longer configuration inputs. Move values into the `[brain]` TOML section and use `MATILDA_CONFIG` when a non-default path is required.
