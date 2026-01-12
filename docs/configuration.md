# Configuration Guide

How configuration is loaded and how to set common options.

## Configuration Hierarchy

Highest to lowest precedence:

1. Programmatic configuration via `configure()`
2. Environment variables
3. Configuration files (TOML)
4. Defaults

## Configuration Files

Configuration lives in a single shared file:

- `~/.matilda/config.toml` (`[brain]` section)

## Environment Variables

API keys:
- `OPENROUTER_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`

System settings:
- `OLLAMA_BASE_URL`
- `AI_CONFIG_FILE`
- `AI_LOG_LEVEL`

## CLI Configuration

```bash
# View settings
brain config list
brain config get models.default

# Set defaults
brain config set model gpt-4
brain config set openai_api_key sk-...
```

## Programmatic Configuration

```python
from matilda_brain import configure

configure(
    default_backend="cloud",
    default_model="gpt-4",
    timeout=60,
    openai_api_key="your-key",
)
```
