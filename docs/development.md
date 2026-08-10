# Development

## Setup

```bash
./scripts/setup.sh install --dev
```

## Verification

```bash
make check             # format check + Ruff + mypy + offline coverage suite
make quality           # static checks only
make test-unit
make test-integration  # HTTP mocks, no provider charges
make test-coverage     # complete offline suite, 70% floor
```

For a targeted run:

```bash
./scripts/test.py unit --test test_routing
python -m pytest tests/unit/test_routing.py -q
```

Real-provider integration is opt-in:

```bash
./scripts/test.py integration --real-api
```

The runner checks credentials and warns before paid/network requests. CI and normal local checks use mocks.

## Generated CLI workflow

`src/matilda_brain/cli.py` and `scripts/setup.sh` are generated.

1. Edit `goobits.yaml` and, when behavior changes, `src/matilda_brain/app_hooks.py`.
2. Run `goobits build`.
3. Inspect generated changes and remove any unintended package-metadata drift.
4. Run `make check`.

## Style

```bash
make format
make lint
make type-check
```

Black uses 120-character lines. Ruff and mypy cover runtime code, tests, and `scripts/test.py`; generated `cli.py` is excluded in favor of its sources.
