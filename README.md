# 🧠 Matilda Brain

Professional command-line interface and Python library for interacting with multiple AI providers including OpenRouter, OpenAI, Anthropic, Google, and local models via Ollama.

## ✨ Key Features

- **🎯 Simple CLI** - Just `brain "your question"` - works instantly
- **🔧 Function Calling** - AI can call your Python functions and tools
- **🌐 Multi-Provider** - OpenRouter (100+ models), OpenAI, Anthropic, Google
- **🤖 Local Support** - Ollama integration for privacy
- **⚡ Fast Setup** - One-command installation
- **🔄 Direct Pipe Support** - `echo "text" | ttt` - no dash needed!

## 🚀 Quick Start

```bash
# Install
./setup.sh install        # For end users
./setup.sh install --dev  # For developers

# Set API key (choose one)
export OPENAI_API_KEY=sk-your-key-here
export OPENROUTER_API_KEY=sk-or-your-key-here
# Or add to .env file

# Start using
brain "What is Python?"
echo "print('Hello world')" | ttt "Explain this code"
echo "Hello world" | ttt

# Use tools
brain "What time is it in Tokyo?" --tools "get_current_time"
brain "Search for Python tutorials" --tools "web_search"
```

## 📚 Python Library

```python
from ttt import ask, stream, chat

# Simple question
response = ask("What is Python?")
print(response)

# Streaming
for chunk in stream("Tell me a story"):
    print(chunk, end="", flush=True)

# Chat sessions
with chat() as session:
    response1 = session.ask("My name is Alice")
    response2 = session.ask("What's my name?")  # Remembers context
```

## 🛠️ Tools & Function Calling

```python
from ttt import ask
from ttt.tools import tool

# Use built-in tools
response = ask(
    "Search for Python tutorials and save results",
    tools=["web_search", "write_file"]
)

# Create custom tools
@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"

response = ask("What's the weather in NYC?", tools=[get_weather])
```

## ⚙️ Configuration

```bash
# View settings
brain config list

# Set configuration
brain config set models.default gpt-4
brain config set api.openai_key sk-...

# Use model aliases
brain -m @fast "Quick question"    # gpt-3.5-turbo
brain -m @best "Complex analysis"   # gpt-4
brain -m @claude "Explain this"     # claude-3-sonnet
```

## 📖 Documentation

- **[Configuration Guide](docs/configuration.md)** - API keys, models, settings
- **[Development Guide](docs/development.md)** - Setup, testing, contributing
- **[API Reference](docs/api-reference.md)** - Python API documentation
- **[Architecture](docs/architecture.md)** - System design and internals
- **[Extensibility](docs/extensibility.md)** - Plugins and customization
- **[Examples](examples/)** - Code examples and tutorials

## 🔗 Related Projects

- **[Matilda](https://github.com/goobits/matilda)** - AI assistant
- **[Matilda Ears](https://github.com/goobits/matilda-ears)** - Speech-to-Text
- **[Matilda Voice](https://github.com/goobits/matilda-voice)** - Text-to-Speech

## 🧪 Development

```bash
# Setup development environment
./setup.sh install --dev

# Run tests
./test.sh                 # Unit tests (fast, free)
./test.sh integration     # Integration tests (requires API keys)

# Code quality
ruff format src/ttt/ tests/
ruff check src/ttt/ tests/
mypy src/ttt/
```

## 📝 License

MIT License - see [LICENSE](LICENSE) for details

## 💡 Support

- Documentation in `docs/`
- Examples in `examples/`
- Report issues on GitHub