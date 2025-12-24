# Integration Test Mocking System

## Overview

The integration tests in `test_integration.py` use a smart HTTP-level mocking system that:

- **Mocks by default**: Avoids rate limiting and API costs during development
- **Preserves real behavior**: Tests all business logic, error handling, and response processing  
- **Allows real API testing**: Can be bypassed for actual API verification
- **Provides realistic responses**: Matches real API response patterns and timing

## Usage

### Default Behavior (Mocked)

```bash
# Run integration tests with mocks (fast, no API costs)
python -m pytest tests/test_integration.py
```

All integration tests use realistic HTTP mocks by default. This is ideal for:
- Development and CI/CD pipelines
- Testing business logic without API dependencies
- Avoiding rate limits and API costs

### Real API Testing

```bash
# Use real APIs with command line flag
python -m pytest tests/test_integration.py --real-api

# Or with environment variable
REAL_API_TESTS=1 python -m pytest tests/test_integration.py
```

This bypasses all mocking and hits real APIs. Requires:
- Valid API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY)
- Rate limiting delays are preserved
- API costs will be incurred

## Mock Features

### Realistic Response Patterns

The mocks understand and respond appropriately to:

- **Math questions**: "What is 2+2?" → "4"
- **Chat context**: Remembers names and context across conversation turns
- **Counting requests**: "Count from 1 to 3" → "1\n2\n3"
- **Code generation**: Requests for Python functions return realistic code
- **Model-specific responses**: Different providers return appropriate responses

### Error Simulation

Error scenarios are also mocked realistically:

- Rate limit errors with retry-after headers
- Authentication failures 
- Model not found errors
- Service unavailable errors
- Timeout errors

### Streaming Support

Streaming tests work with realistic chunked responses:

```python
# Streaming responses are broken into realistic chunks
for chunk in delayed_stream("Count from 1 to 3", model="gpt-3.5-turbo"):
    chunks.append(chunk)
```

## Architecture

### HTTP-Level Mocking

The system mocks at the `litellm.acompletion` level, which means:

- ✅ All TTT business logic runs normally
- ✅ Error handling and response processing is tested
- ✅ Model routing and fallback logic works
- ✅ Rate limiting logic is preserved (but skipped in mocks)
- ❌ No actual HTTP requests are made

### Smart Context Awareness

The mocks understand conversation context for chat sessions:

```python
with delayed_chat(model="gpt-3.5-turbo") as session:
    session.ask("My name is Alice")  # Establishes context
    response = session.ask("What's my name?")  # Returns "Your name is Alice"
```

## Implementation Details

### Key Files

- `tests/utils/http_mocks.py` - Core mocking infrastructure
- `tests/conftest.py` - Auto-mocking fixture and configuration
- `tests/test_mock_verification.py` - Tests to verify mocking works correctly

### Mock Response Structure

Responses match LiteLLM's actual structure:

```python
response.content  # The AI response text
response.model    # Model name used
response.choices  # Array of choice objects
response.usage    # Token usage information
response._hidden_params  # Cost information
```

### Conditional Bypass Logic

```python
def _should_use_real_api(config=None, env_override=None):
    # Check command line --real-api flag
    # Check REAL_API_TESTS=1 environment variable
    # Return False by default (use mocks)
```

## Performance Impact

**Before (with real APIs and rate limiting):**
- 13 tests could take 30+ seconds
- Rate limiting delays between requests
- API costs and quota consumption
- Potential for rate limit failures

**After (with mocks):**
- 13 tests run in ~1.35 seconds
- No rate limiting delays
- No API costs
- Consistent, reliable results
- All assertions and logic preserved

## Testing the Mocking System

Run the mock verification tests to ensure everything works:

```bash
python -m pytest tests/test_mock_verification.py -v
```

This verifies:
- Mocks are active by default
- Context awareness works in chat sessions
- Streaming responses work correctly
- Different model names are handled
- Real API bypass logic functions properly