# Development Guide

Setup, testing, and code quality for Matilda Brain.

## Setup

```bash
./scripts/setup.sh install --dev
```

## Testing

```bash
just brain test
just brain test-unit
export OPENROUTER_API_KEY=your-key-here
just brain test-integration
```

```bash
./scripts/test.sh
./scripts/test.sh unit
./scripts/test.sh integration
```

For marker details and local testing guidance, see `matilda-brain/tests/README.md`.

## Formatting and Linting

```bash
black src/matilda_brain/ tests/
ruff src/matilda_brain/ tests/
mypy src/matilda_brain/
```
