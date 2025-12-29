# API Reference

Complete Python API documentation for Matilda Brain.

```python
# Common imports
from matilda_brain import ask, stream, chat, configure
from matilda_brain import ChatSession
from matilda_brain.tools import tool
```

## Core Functions

### `ask()`

```python
def ask(
    prompt: str,
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    backend: Optional[Union[str, BaseBackend]] = None,
    **kwargs
) -> AIResponse
```

Send a single prompt and get a complete response.

**Parameters:**
- `prompt` (str): Your question or prompt
- `model` (str, optional): Specific model to use
- `system` (str, optional): System prompt to set context
- `temperature` (float, optional): Sampling temperature (0-1)
- `max_tokens` (int, optional): Maximum tokens to generate
- `backend` (str | BaseBackend, optional): Backend to use ("local", "cloud", "auto", or Backend instance)
- `**kwargs`: Additional backend-specific parameters

**Returns:**
- `AIResponse`: Response object that behaves like a string with metadata

**Example:**
```python
response = ask("What is Python?", model="gpt-4", temperature=0.7)
print(response)  # The response text
print(response.model)  # "gpt-4"
print(response.time)  # 1.23 (seconds)
```

### `stream()`

```python
def stream(
    prompt: str,
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    backend: Optional[Union[str, BaseBackend]] = None,
    **kwargs
) -> Iterator[str]
```

Stream a response token by token.

**Parameters:** Same as `ask()`

**Yields:**
- `str`: Response chunks as they arrive

**Example:**
```python
for chunk in stream("Tell me a story"):
    print(chunk, end="", flush=True)
```

### `chat()`

```python
@contextmanager
def chat(
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    backend: Optional[Union[str, BaseBackend]] = None,
    **kwargs
) -> ChatSession
```

Create a chat session with conversation memory.

**Parameters:**
- `system` (str, optional): System prompt for the session
- `model` (str, optional): Default model for the session
- `backend` (str | BaseBackend, optional): Backend for the session
- `**kwargs`: Additional parameters passed to each request

**Yields:**
- `ChatSession`: Session object with `ask()` and `stream()` methods

**Example:**
```python
with chat(system="You are a helpful assistant") as session:
    response1 = session.ask("Hello!")
    response2 = session.ask("What did I just say?")  # Has context
```

## Configuration Functions

### `configure()`

```python
def configure(
    *,
    openai_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    google_api_key: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
    default_backend: Optional[str] = None,
    default_model: Optional[str] = None,
    timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
    **kwargs
) -> None
```

Configure Matilda Brain programmatically.

**Parameters:**
- `openai_api_key` (str, optional): OpenAI API key
- `anthropic_api_key` (str, optional): Anthropic API key
- `google_api_key` (str, optional): Google API key
- `ollama_base_url` (str, optional): Ollama base URL
- `default_backend` (str, optional): Default backend to use
- `default_model` (str, optional): Default model to use
- `timeout` (int, optional): Request timeout in seconds
- `max_retries` (int, optional): Maximum number of retries
- `**kwargs`: Additional configuration options

**Example:**
```python
configure(
    openai_api_key="sk-...",
    default_backend="cloud",
    timeout=60
)
```

## Plugin Functions

### `register_backend()`

```python
def register_backend(
    name: str,
    backend_class: Type[BaseBackend],
    version: str = "1.0.0",
    description: str = "",
    author: str = "",
    requires: Optional[List[str]] = None
) -> None
```

Register a custom backend.

**Parameters:**
- `name` (str): Backend identifier
- `backend_class` (Type[BaseBackend]): Backend class
- `version` (str): Version string
- `description` (str): Backend description
- `author` (str): Author name
- `requires` (List[str], optional): Required dependencies

**Example:**
```python
register_backend("my-backend", MyBackendClass, version="1.0.0")
```

### `load_plugin()`

```python
def load_plugin(file_path: Path) -> None
```

Load a plugin from a specific file.

**Parameters:**
- `file_path` (Path): Path to the plugin file

**Example:**
```python
load_plugin(Path("my_plugin.py"))
```

### `discover_plugins()`

```python
def discover_plugins() -> None
```

Discover and load all available plugins from standard locations.

## Classes

### `AIResponse`

Response object that extends `str` with metadata.

**Properties:**
- `model` (str): Model that generated the response
- `backend` (str): Backend that was used
- `time` (float): Time taken in seconds (alias for `time_taken`)
- `time_taken` (float): Time taken in seconds
- `tokens_in` (int): Input token count
- `tokens_out` (int): Output token count
- `cost` (float): Estimated cost (if available)
- `succeeded` (bool): Whether the request succeeded
- `failed` (bool): Whether the request failed
- `error` (str): Error message (if failed)
- `metadata` (dict): Additional backend-specific metadata
- `timestamp` (datetime): When the response was created

**Methods:**
All string methods are available (upper(), lower(), split(), etc.)

**Example:**
```python
response = ask("Hello")
print(len(response))  # String length
print(response.upper())  # "HELLO"
print(f"Took {response.time:.2f}s using {response.model}")
```

### `ChatSession`

Manages a conversation with history.

**Methods:**
- `ask(prompt, **kwargs) -> AIResponse`: Ask a question
- `stream(prompt, **kwargs) -> Iterator[str]`: Stream a response
- `clear() -> None`: Clear conversation history

**Properties:**
- `history` (List[Dict]): Conversation history
- `system` (str): System prompt
- `model` (str): Default model
- `backend` (BaseBackend): Backend instance

### `ModelInfo`

Model metadata container.

**Properties:**
- `name` (str): Model identifier
- `provider` (str): Provider name (openai, anthropic, etc.)
- `provider_name` (str): Actual model name used by provider
- `aliases` (List[str]): Alternative names
- `speed` (str): Speed rating (fast, medium, slow)
- `quality` (str): Quality rating (low, medium, high)
- `capabilities` (List[str]): Model capabilities
- `context_length` (int): Maximum context size
- `cost_per_token` (float): Estimated cost

## Model Registry

### `model_registry`

Global model registry instance.

**Methods:**
- `add_model(model: ModelInfo) -> None`: Add a model
- `get_model(name_or_alias: str) -> Optional[ModelInfo]`: Get model info
- `resolve_model_name(name_or_alias: str) -> str`: Resolve alias to name
- `list_models(provider: Optional[str] = None) -> List[str]`: List models
- `list_aliases() -> Dict[str, str]`: List all aliases

## Backend Base Class

### `BaseBackend`

Abstract base class for all backends.

**Required Methods:**
- `ask(prompt, **kwargs) -> AIResponse`: Generate response
- `astream(prompt, **kwargs) -> AsyncIterator[str]`: Stream response
- `models() -> List[str]`: List available models
- `status() -> Dict[str, Any]`: Get status info

**Required Properties:**
- `name -> str`: Backend identifier
- `is_available -> bool`: Availability check

**Configuration Access:**
- `self.config`: Raw configuration dict
- `self.backend_config`: Merged backend-specific config
- `self.timeout`: Timeout setting
- `self.max_retries`: Retry setting
- `self.default_model`: Default model

## Async Support

All core functions have async equivalents:

### `ask_async()`
```python
async def ask_async(prompt: str, **kwargs) -> AIResponse
```

### `stream_async()`
```python
async def stream_async(prompt: str, **kwargs) -> AsyncIterator[str]
```

### `achat()`
```python
@asynccontextmanager
async def achat(**kwargs) -> ChatSession
```

**Example:**
```python
import asyncio

async def main():
    response = await ask_async("Hello")
    print(response)

    async for chunk in stream_async("Tell me a story"):
        print(chunk, end="")

    async with achat() as session:
        response = await session.ask("Hi")

asyncio.run(main())
```

## Environment Variables

- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `GOOGLE_API_KEY`: Google API key
- `OLLAMA_BASE_URL`: Ollama server URL (default: http://localhost:11434)
- `AI_CONFIG_FILE`: Path to configuration file
- `AI_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Error Handling

The library uses `AIResponse` objects for error handling:

```python
response = ask("Question", backend="unavailable-backend")
if response.failed:
    print(f"Error: {response.error}")
else:
    print(f"Success: {response}")
```

Common error scenarios:
- Backend not available
- API key missing
- Model not found
- Timeout exceeded
- Rate limit reached
- Network errors

## Best Practices

1. **Check Response Status**:
   ```python
   response = ask("Question")
   if response.succeeded:
       process(response)
   ```

2. **Use Context Managers**:
   ```python
   with chat() as session:
       # Automatic cleanup
   ```

3. **Handle Streaming Interruption**:
   ```python
   try:
       for chunk in stream("Long response"):
           print(chunk, end="")
   except KeyboardInterrupt:
       print("\nInterrupted")
   ```

4. **Configure Once**:
   ```python
   # At startup
   configure(default_backend="cloud", timeout=60)
   ```

5. **Use Type Hints**:
   ```python
   from matilda_brain import AIResponse

   def process_response(response: AIResponse) -> str:
       return response.upper()
   ```
