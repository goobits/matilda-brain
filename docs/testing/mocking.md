# Integration Test Mocking

Integration-style tests use HTTP-level mocks by default to avoid API costs.

## Real API Mode

```bash
python -m pytest tests/test_integration.py --real-api
REAL_API_TESTS=1 python -m pytest tests/test_integration.py
```

## Key Files

- `tests/utils/http_mocks.py`
- `tests/conftest.py`
- `tests/test_mock_verification.py`
