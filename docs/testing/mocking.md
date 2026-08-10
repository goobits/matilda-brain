# Integration mocking

Integration tests use deterministic HTTP-level provider mocks by default.

```bash
./scripts/test.py integration
python -m pytest tests/integration -q
```

Real APIs require an explicit switch and credentials:

```bash
./scripts/test.py integration --real-api
REAL_API_TESTS=1 python -m pytest tests/integration/test_integration.py --real-api
```

Key owners:

- `tests/utils/http_mocks.py`: provider HTTP responses
- `tests/conftest.py`: mock activation and external-dependency markers
- `tests/unit/test_mock_verification.py`: proves the default stays offline
- `scripts/test.py`: user-facing test-mode selection
