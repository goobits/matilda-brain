# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Information

**Package**: `goobits-matilda-brain` | **Command**: `brain` | **Python**: 3.8+

A professional CLI and Python library for interacting with multiple AI providers (OpenRouter, OpenAI, Anthropic, Google, Ollama).

## Essential Commands

```bash
./setup.sh install --dev         # Development setup (required)
./run-tests.sh                   # Run tests with smart rate limiting
pytest -m unit                   # Unit tests (fast, no API calls)
pytest -m integration --fast     # Integration tests without delays
ruff check src/ tests/           # Lint code
black src/ tests/                # Format code
mypy src/matilda_brain/                    # Type check
pytest tests/path/to/test.py::test_name -v  # Run single test
```

## Architecture Overview

**Request Flow**: User → CLI/API → Router → Backend → Provider → Response

### Key Components

1. **API** (`src/matilda_brain/core/api.py`): Core functions `ask()`, `stream()`, `chat()` with async variants
2. **Backends** (`src/matilda_brain/backends/`):
   - `CloudBackend`: LiteLLM integration for cloud providers
   - `LocalBackend`: Ollama integration for local models
   - Selected automatically by model name patterns
3. **Router** (`src/matilda_brain/core/routing.py`): Manages backend selection and fallbacks
4. **Tools** (`src/matilda_brain/tools/`): `@tool` decorator enables function calling
5. **Config** (`src/matilda_brain/config/`): Hierarchical configuration (defaults → file → env → runtime)
6. **CLI** (`src/matilda_brain/cli.py`): Generated CLI interface (1,492 lines) - **DO NOT EDIT DIRECTLY**
7. **Hooks** (`src/matilda_brain/cli_handlers.py`): Business logic implementation (1,396 lines)

### Self-Hosting Pattern

TTT uses `goobits.yaml` to generate its own CLI infrastructure:
```bash
goobits build  # Regenerates src/matilda_brain/cli.py and setup.sh
```

### Critical Patterns

- **Generated Files**: `cli.py` is auto-generated from `goobits.yaml` - modify hooks in `cli_handlers.py`
- **Hook System**: All CLI business logic lives in `cli_handlers.py`, not the generated CLI
- **Smart Rate Limiting**: `./run-tests.sh` includes provider-specific delays (OpenRouter: 1s, OpenAI: 0.5s)
- **Dual Backend Architecture**: Automatic routing Cloud (LiteLLM) ↔ Local (Ollama)
- **Tool Schema Auto-generation**: Python type hints → OpenAI function calling schemas
- **Provider Auto-detection**: Model names automatically route to correct backend
- **Configuration Hierarchy**: defaults → `config.yaml` → env vars → runtime params

### Testing Notes

- **Smart Testing**: `./run-tests.sh` with intelligent rate limiting is the primary test runner
- **Unit tests**: Use mocked responses (no API costs, fast)
- **Integration tests**: Real API calls with rate limiting (`conftest.py`)
- **Fast mode**: `pytest --fast` bypasses rate limiting for development

## Further Reading

- **Architecture details**: `docs/architecture.md`
- **Testing guide**: `tests/README.md`
- **Development setup**: `docs/development.md`
- **Configuration**: `docs/configuration.md`
- **Code style settings**: `pyproject.toml`

### Temporary Files
When creating temporary debug or test scripts, use `/tmp` directory to keep the project clean.