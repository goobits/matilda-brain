# Configuration Guide

Matilda Brain provides flexible configuration through multiple sources with clear precedence rules.

## Configuration Hierarchy

Configuration is loaded in this order (highest to lowest precedence):

1. **Programmatic configuration** via `configure()`
2. **Environment variables**
3. **Configuration files** (YAML)
4. **Default values**

## Configuration Files

The library searches for configuration files in these locations:

1. `./ai.yaml` or `./ai.yml` - Project-specific config
2. `./.ai.yaml` or `./.ai.yml` - Hidden project config
3. `~/.config/matilda-brain/config.yaml` or `~/.config/matilda-brain/config.yml` - User config
4. `~/.ai.yaml` or `~/.ai.yml` - Hidden user config
5. `config.yaml` - Default configuration (built-in)
6. `.env` - Environment variables and API keys

## Environment Variables

### API Keys
- `OPENROUTER_API_KEY` - Recommended (access to 100+ models)
- `OPENAI_API_KEY` - Direct OpenAI access
- `ANTHROPIC_API_KEY` - Direct Anthropic access
- `GOOGLE_API_KEY` - Direct Google access
- `OLLAMA_BASE_URL` - Local Ollama URL (default: http://localhost:11434)

### System Configuration
- `AI_CONFIG_FILE` - Path to configuration file
- `AI_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

## CLI Configuration

### View Settings
```bash
# View all settings
brain config

# Get specific value
brain config get models.default
brain config get models.aliases
```

### Set Configuration
```bash
# Set API keys (masked when displayed)
brain config set openai_key sk-your-key-here
brain config set anthropic_key sk-ant-your-key-here
brain config set openrouter_key sk-or-v1-your-key-here

# Configure behavior
brain config set models.default gpt-4         # Default model
brain config set backends.default local       # Backend (local/cloud/auto)
brain config set timeout 60                   # Request timeout
brain config set retries 3                    # Max retry attempts

# Create model aliases
brain config set alias.work claude-3-opus
```

### Reset Configuration
```bash
brain config --reset  # Reset to defaults
```

## Common Configurations

| Use Case | Configuration |
|----------|---------------|
| **Privacy-First** | `brain config set backends.default local && brain config set models.default qwen2.5:32b` |
| **Fast Responses** | `brain config set models.default gpt-3.5-turbo` |
| **Coding Assistant** | `brain config set models.default claude-3-sonnet && brain config set backends.default cloud` |
| **Cost-Effective** | `brain config set openrouter_key sk-or-... && brain config set models.default google/gemini-flash` |

## Configuration Schema

### Complete YAML Configuration Example

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
  cheap: gpt-3.5-turbo
  coding: google/gemini-1.5-pro
  local: llama2
  claude: claude-3-sonnet
  gpt4: gpt-4

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
  code_keywords: [code, function, debug, algorithm, implement, syntax]
  speed_keywords: [quick, fast, simple, brief, tldr]
  quality_keywords: [analyze, explain, comprehensive, detailed, thorough]
  
  # Model selection rules
  rules:
    - if: {contains: [code, python]}
      prefer_model: claude-3-sonnet
    - if: {length_gt: 200}
      prefer_model: gpt-4
```

## Model Routing

### Automatic Model Selection

The library automatically selects appropriate models based on:

- **Cloud models**: Patterns like `openrouter/`, `gpt-`, `claude-`, `gemini-`
- **Local models**: Assumes Ollama for non-cloud patterns
- **Default model**: `openrouter/google/gemini-flash-1.5`
- **Model aliases**: `fast`, `best`, `cheap`, `coding`, `local` (defined in config.yaml)

### Using Model Aliases

```bash
# Use predefined aliases
brain ask -m @fast "Quick question"
brain ask -m @best "Complex analysis"
brain ask -m @coding "Write a function"
brain ask -m @claude "Explain this concept"
brain ask -m @local "Private question"

# Create custom aliases
brain config set alias.work claude-3-opus
brain ask -m @work "Work-related task"
```

## Programmatic Configuration

### Python API

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

# Configure with custom settings
configure(
    openrouter_api_key="sk-or-...",
    default_backend="cloud",
    default_model="openrouter/google/gemini-flash-1.5",
    timeout=30,
    max_retries=5
)
```

## Backend Configuration

### Cloud Backend

Uses LiteLLM to provide unified access to multiple AI providers:

- **OpenRouter** (recommended): Access to 100+ models through single API key
- **OpenAI**: GPT-3.5, GPT-4, and newer models
- **Anthropic**: Claude models
- **Google**: Gemini models

### Local Backend

Uses Ollama for privacy-focused local inference:

```bash
# Configure Ollama URL (if not using default)
export OLLAMA_BASE_URL=http://localhost:11434

# Or via config
brain config set ollama_base_url http://custom-server:11434
```

## Advanced Configuration

### Custom Backend Registration

```yaml
# In config file
backends:
  custom:
    class_path: mymodule.MyBackend
    config:
      api_key: xxx
      api_url: https://api.example.com
```

### Provider-Specific Settings

```yaml
backends:
  cloud:
    openai:
      organization: org-xxx
      api_base: https://custom-endpoint.com
    anthropic:
      api_version: 2023-06-01
```

### Rate Limiting Configuration

```yaml
rate_limits:
  openrouter: 60  # requests per minute
  openai: 120
  anthropic: 100
  
retry_config:
  max_attempts: 3
  backoff_factor: 2
  max_wait: 60
```

## Configuration Best Practices

1. **Use environment variables for API keys** - Keep sensitive data out of config files
2. **Create project-specific configs** - Use `./ai.yaml` for project settings
3. **Set reasonable timeouts** - Balance between reliability and responsiveness
4. **Configure model aliases** - Create shortcuts for frequently used models
5. **Enable fallbacks** - Ensure reliability with automatic backend switching

## Troubleshooting

### Check Current Configuration
```bash
# View all settings
brain config

# Check specific backend status
brain status

# List available models
brain models
```

### Common Issues

**API Key Not Found**
```bash
# Check if key is set
echo $OPENAI_API_KEY

# Set via config
brain config set openai_key sk-...

# Or export directly
export OPENAI_API_KEY=sk-...
```

**Wrong Default Model**
```bash
# Check current default
brain config get models.default

# Set new default
brain config set models.default gpt-4
```

**Configuration Not Loading**
```bash
# Check config file locations
ls -la ~/.config/matilda-brain/config.yaml
ls -la ./ai.yaml

# Verify syntax
python -m yaml < ai.yaml
```