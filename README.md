# 🧠 Matilda Brain

CLI and Python library for AI providers: OpenRouter, OpenAI, Anthropic, Google, and Ollama.

## ✨ Key Features

- **🎯 Simple CLI** - `brain "your question"` with instant responses
- **🔧 Function Calling** - AI invokes Python functions via `@tool` decorator
- **🌐 Multi-Provider** - OpenRouter (100+ models), OpenAI, Anthropic, Google
- **🤖 Local Models** - Ollama integration for offline/private usage
- **🔄 Pipe Support** - `echo "text" | brain` works directly

## 🚀 Quick Start

```bash
# Install
./setup.sh install        # Production
./setup.sh install --dev  # Development

# Configure API key
export OPENAI_API_KEY=sk-your-key
# Or: export OPENROUTER_API_KEY=sk-or-your-key

# Use
brain "What is Python?"
brain "What time is it in Tokyo?" --tools  # Enable built-in tools
echo "print('Hello')" | brain "Explain this code"
```

## 📚 Python Library

```python
from matilda_brain import ask, stream, chat

# Single question
response = ask("What is Python?")

# Streaming response
for chunk in stream("Tell me a story"):
    print(chunk, end="", flush=True)

# Conversation with context
with chat() as session:
    session.ask("My name is Alice")
    session.ask("What's my name?")  # Remembers context
```

## 🛠️ Function Calling

```python
from matilda_brain import ask
from matilda_brain.tools import tool
from matilda_brain.tools.builtins import web_search, write_file

# Built-in tools (pass function references)
response = ask(
    "Search for Python tutorials and save results",
    tools=[web_search, write_file]
)

# Custom tools
@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72F"

response = ask("What's the weather in NYC?", tools=[get_weather])
```

## ⚙️ Configuration

```bash
# View settings
brain config list

# Set defaults
brain config set models.default gpt-4
brain config set openai_api_key sk-...

# Model aliases (via OpenRouter)
brain -m @fast "Quick question"     # openrouter/openai/gpt-3.5-turbo
brain -m @best "Complex analysis"   # openrouter/openai/gpt-4
brain -m @claude "Explain this"     # openrouter/anthropic/claude-3-sonnet
```

## 📖 Documentation

- **[Configuration Guide](docs/configuration.md)** - API keys, models, settings
- **[API Reference](docs/api-reference.md)** - Python API documentation
- **[Architecture](docs/architecture.md)** - System design and internals
- **[Examples](examples/)** - Code examples and tutorials

## 🔗 Related Projects

- **[Matilda](https://github.com/goobits/matilda)** - Voice assistant orchestrator
- **[Matilda Ears](https://github.com/goobits/matilda-ears)** - Speech-to-Text
- **[Matilda Voice](https://github.com/goobits/matilda-voice)** - Text-to-Speech

## 🧪 Development

```bash
./setup.sh install --dev

# Tests
./test.sh                   # Run tests with coverage

# Code quality
ruff check src/ tests/
ruff format src/ tests/
mypy src/
```

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.
