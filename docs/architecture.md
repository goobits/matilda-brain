# System Architecture

Matilda Brain implements a layered architecture that provides a unified interface to multiple AI providers while maintaining flexibility and extensibility.

## Architecture Overview

The system follows a **CLI → Backend → Provider** abstraction pattern:

```
┌─────────────────────────────────────────────┐
│          User Interface Layer               │
│  • CLI (Click-based)                        │
│  • Python API (sync/async)                  │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│           Core API Layer                    │
│  • ask(), stream(), chat()                  │
│  • Session management                       │
│  • Response objects                         │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│      Backend Abstraction Layer              │
│  • BaseBackend interface                    │
│  • CloudBackend (LiteLLM)                   │
│  • LocalBackend (Ollama)                    │
│  • Custom backends via plugins              │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│         Provider Layer                      │
│  • OpenRouter (100+ models)                 │
│  • OpenAI, Anthropic, Google                │
│  • Local models via Ollama                  │
└─────────────────────────────────────────────┘
```

## Core Components

### 1. API Layer (`src/matilda_brain/core/api.py`)

The main interface providing both synchronous and asynchronous APIs:

- **Core Functions**: `ask()`, `stream()`, `chat()`
- **Async Variants**: `ask_async()`, `stream_async()`, `achat()`
- **Unified Interface**: Same API regardless of backend
- **Response Objects**: AIResponse with metadata

```python
# Synchronous API
response = ask("What is Python?", model="gpt-4")

# Asynchronous API
response = await ask_async("What is Python?", model="gpt-4")
```

### 2. Backend System (`src/matilda_brain/backends/`)

Pluggable backend architecture for different AI providers:

#### BaseBackend (`base.py`)
Abstract interface all backends must implement:
- `ask()` - Generate complete response
- `astream()` - Stream response chunks
- `models()` - List available models
- `status()` - Backend health check
- `name` property - Backend identifier
- `is_available` property - Availability check

#### CloudBackend (`cloud.py`)
Integrates with cloud providers via LiteLLM:
- Unified interface to OpenAI, Anthropic, Google, etc.
- Automatic provider detection from model names
- Built-in retry logic and error handling
- Response streaming support

#### LocalBackend (`local.py`)
Integrates with Ollama for local models:
- Privacy-focused local inference
- No API keys required
- Support for open-source models
- Automatic model management

### 3. Routing System (`src/matilda_brain/core/routing.py`)

Intelligent routing between backends and models:

- **Automatic Backend Selection**: Based on model patterns
- **Model Registry**: Central repository of model metadata
- **Fallback Mechanisms**: Automatic failover between providers
- **Smart Routing**: Query analysis for optimal model selection

```python
# Router automatically selects appropriate backend
response = ask("Code question", model="gpt-4")  # → CloudBackend
response = ask("Private data", model="llama2")  # → LocalBackend
```

### 4. Tool System (`src/matilda_brain/tools/`)

Function calling framework for AI assistants:

#### Components
- **Base Classes** (`base.py`): Tool decorator and interfaces
- **Built-in Tools** (`builtins.py`): Common tools ready to use
- **Registry** (`registry.py`): Central tool registration
- **Executor** (`executor.py`): Safe tool execution engine

#### Tool Creation
```python
@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"
```

### 5. Configuration System (`src/matilda_brain/config/`)

Hierarchical configuration management:

- **Multiple Sources**: Files, environment, programmatic
- **Clear Precedence**: Program > Env > Files > Defaults
- **Backend-Specific**: Per-backend configuration
- **Runtime Updates**: Dynamic configuration changes

### 6. Session Management (`src/matilda_brain/session/`)

Conversation and state management:

- **ChatSession**: Basic conversation tracking
- **PersistentChatSession**: Save/load conversations
- **History Management**: Token counting and pruning
- **Multi-Session**: Manage multiple conversations

## Data Flow

### Request Flow

1. **User Input** → CLI or Python API
2. **API Layer** → Validates and prepares request
3. **Router** → Selects appropriate backend
4. **Backend** → Transforms request for provider
5. **Provider** → Generates AI response
6. **Backend** → Transforms response to standard format
7. **API Layer** → Wraps in AIResponse object
8. **User** → Receives response with metadata

### Tool Execution Flow

1. **Model Request** → AI requests tool execution
2. **Tool Matcher** → Finds requested tool
3. **Argument Parser** → Extracts and validates arguments
4. **Security Check** → Validates safe execution
5. **Tool Executor** → Runs tool function
6. **Result Handler** → Formats tool output
7. **Model** → Receives tool results
8. **Final Response** → Incorporates tool results

## Key Design Patterns

### 1. Abstract Factory (Backends)
```python
backend = Backend.create("cloud", config)
backend = Backend.create("local", config)
```

### 2. Strategy Pattern (Routing)
```python
router = Router()
backend = router.select_backend(model, query)
```

### 3. Decorator Pattern (Tools)
```python
@tool
def my_function(arg: str) -> str:
    return process(arg)
```

### 4. Chain of Responsibility (Config)
```
Program Config → Env Variables → Config Files → Defaults
```

### 5. Observer Pattern (Streaming)
```python
for chunk in stream("Generate text"):
    process_chunk(chunk)
```

## Extension Points

### 1. Custom Backends

Implement BaseBackend interface:

```python
class CustomBackend(BaseBackend):
    @property
    def name(self) -> str:
        return "custom"
    
    async def ask(self, prompt: str, **kwargs) -> AIResponse:
        # Custom implementation
        pass
```

### 2. Custom Tools

Register new tools:

```python
@tool(category="custom")
def domain_specific_tool(param: str) -> str:
    """Tool documentation."""
    return custom_logic(param)
```

### 3. Model Definitions

Add custom models:

```python
model_registry.add_model(ModelInfo(
    name="custom-model",
    provider="custom",
    capabilities=["text", "code"],
    context_length=8192
))
```

### 4. Configuration Sources

Add custom config loaders:

```python
class CustomConfigLoader(ConfigLoader):
    def load(self) -> Dict[str, Any]:
        return load_from_custom_source()
```

## Performance Considerations

### 1. Connection Pooling
- HTTP connections reused across requests
- Configurable pool size and timeout
- Automatic connection management

### 2. Async Architecture
- Non-blocking I/O for all operations
- Concurrent request handling
- Proper async context management

### 3. Caching Strategy
- Model lists cached per backend
- Configuration cached and monitored
- Response caching (optional)

### 4. Resource Management
- Automatic cleanup of resources
- Context managers for sessions
- Proper error handling and recovery

## Security Architecture

### 1. API Key Management
- Keys never logged or displayed
- Environment variable isolation
- Secure configuration storage

### 2. Tool Execution
- Sandboxed execution environment
- Input validation and sanitization
- Permission-based tool access

### 3. File Operations
- Path traversal prevention
- Access control checks
- Safe file handling

### 4. Network Security
- HTTPS only for external APIs
- Certificate validation
- Request/response validation

## Error Handling

### Error Hierarchy

```
AIError (base)
├── APIKeyError - Missing/invalid API keys
├── ModelNotFoundError - Model doesn't exist
├── BackendNotAvailableError - Backend offline
├── RateLimitError - API rate limits
├── ToolExecutionError - Tool failures
└── ConfigurationError - Config issues
```

### Error Recovery

1. **Automatic Retries**: Configurable retry logic
2. **Fallback Backends**: Automatic failover
3. **Graceful Degradation**: Partial functionality
4. **User-Friendly Messages**: Clear error descriptions

## Monitoring and Logging

### Logging Levels
- **DEBUG**: Detailed execution flow
- **INFO**: Normal operations
- **WARNING**: Recoverable issues
- **ERROR**: Failures requiring attention

### Metrics
- Request/response times
- Token usage tracking
- Error rates by backend
- Tool execution statistics

## Future Architecture Considerations

### Planned Enhancements
1. **Plugin Marketplace**: Discover and install plugins
2. **Response Caching**: Intelligent caching layer
3. **Load Balancing**: Distribute across providers
4. **Advanced Routing**: ML-based model selection
5. **Federated Backends**: Distributed processing

### Extensibility Goals
- Maintain backward compatibility
- Support new AI providers easily
- Enable community contributions
- Scale to enterprise usage