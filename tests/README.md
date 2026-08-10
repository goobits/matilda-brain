# Testing

## Commands

```bash
./scripts/test.py                     # unit suite
./scripts/test.py integration         # mocked HTTP integration
./scripts/test.py all --coverage      # combined, accumulating coverage
./scripts/test.py --test test_routing # targeted pattern
make check                            # canonical offline gate
```

Real provider calls are never the default:

```bash
./scripts/test.py integration --real-api
```

The runner requires a supported provider key and asks for confirmation unless `--force` is supplied.

## Markers

- `unit`: isolated behavior
- `integration`: multi-module or adapter behavior
- `requires_credentials`: external credentials required
- `requires_network`: external network required
- `requires_service`: local service required
- `requires_gpu`: GPU required
- `slow`: intentionally time-consuming

The offline gate sets `BRAIN_RUN_CRED_TESTS=0` and `REAL_API_TESTS=0`. The mocked integration runner explicitly includes the external-marker test shapes while intercepting provider HTTP.

## Layout

```text
tests/
├── unit/                 # domain, adapter, CLI, packaging, and policy tests
├── integration/          # mocked CLI flows plus opt-in real-provider tests
├── utils/http_mocks.py   # deterministic provider protocol fixtures
└── conftest.py           # isolation, markers, and real/mock mode selection
```

## Expectations

- Test observable behavior, not implementation trivia.
- Add a regression test with every repaired contract.
- Keep normal tests free of provider cost, ambient credentials, and local services.
- Use `MATILDA_CONFIG` or existing fixtures for isolated configuration.
- Keep the complete offline coverage result at or above 70%.
