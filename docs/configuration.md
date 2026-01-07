# Configuration Guide

How configuration is loaded and how to set common options.

## Configuration Hierarchy

Highest to lowest precedence:

1. Programmatic configuration via `configure()`
2. Environment variables
3. Configuration files (YAML)
4. Defaults

## Configuration Files

The library searches these locations:

1. `./ai.yaml` or `./ai.yml`
2. `./.ai.yaml` or `./.ai.yml`
3. `~/.config/matilda-brain/config.yaml` or `~/.config/matilda-brain/config.yml`
4. `~/.ai.yaml` or `~/.ai.yml`
5. `.env`

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
