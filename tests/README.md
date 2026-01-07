# Testing Guide

How to run tests and apply markers in Matilda Brain.

## Quick Start

```bash
# Unit tests only (default)
./test.sh

# Integration-style tests (requires keys/network)
./test.sh integration

# Specific test file
./test.sh --test test_api_core
```

## Markers

Use reasoned markers for external dependencies:

- `unit`: Fast tests with mocking and no external dependencies
- `requires_credentials`: Needs API keys or other credentials
- `requires_network`: Needs external network access
- `requires_service`: Needs local services running
- `requires_gpu`: Needs a GPU
- `slow`: Time-intensive tests
- `asyncio`: Async tests

Unit runs should exclude `requires_*` markers unless explicitly requested.

## Integration-Style Tests

Integration-style tests default to HTTP-level mocks. Run real APIs with:

```bash
./test.sh integration --real-api
REAL_API_TESTS=1 ./test.sh integration
```

## Rate Limiting Fixtures

When hitting real APIs, use fixtures that add delays:

- `delayed_ask`
- `delayed_stream`
- `delayed_chat`
- `rate_limit_delay`

## File Organization

```
tests/
├── conftest.py
├── test_api_*.py
├── test_backends_*.py
├── test_cli_*.py
├── test_tools_*.py
├── test_config_*.py
└── test_integration.py
```

## Writing Tests

```python
import pytest

@pytest.mark.unit
def test_basic_ask(mock_backend):
    response = ask("Hello", backend=mock_backend)
    assert response.succeeded

@pytest.mark.requires_credentials
@pytest.mark.requires_network
def test_real_api_call(delayed_ask):
    response = delayed_ask("Hello", model="gpt-3.5-turbo")
    assert response.succeeded
```
