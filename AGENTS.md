# AGENTS.md

Local guidance for Matilda Brain. Monorepo-level instructions still apply.

## Project

- Package: `goobits-matilda-brain`
- Import: `matilda_brain`
- Command: `brain` (`ttt` is a compatibility entry point)
- Python: 3.11-3.13
- Format/lint/types: Black, Ruff, mypy

## Commands

```bash
./scripts/setup.sh install --dev
make check
make test-unit
make test-integration
./scripts/test.py integration --real-api --force
```

`make check` is the canonical offline gate. Mocked integration tests are free and deterministic; real-provider tests require the explicit `--real-api` flag and credentials.

## Generated files

Do not edit these directly:

- `src/matilda_brain/cli.py`
- `scripts/setup.sh`

Change `goobits.yaml` and `src/matilda_brain/app_hooks.py`, run `goobits build`, then verify the generated diff. Keep `py.typed` as the only packaged data file; `setup.sh` is not wheel data.

## Architecture

- `core/request.py`: canonical request construction and backend execution
- `core/routing.py`: backend/model selection and fallback
- `backends/`: cloud, local, and Hub adapters
- `tools/`: registry, policy, executor, recovery, and model tool loop
- `session/`: conversational state and CLI persistence
- `config/manager.py`: sole config discovery, merge, and persistence owner
- `server.py`: authenticated aiohttp adapter for the Matilda protocol
- `app_hooks.py`: stable bridge from generated CLI commands to internal hooks

## Contracts

- Configuration lives in `~/.matilda/config.toml` under `[brain]`; `MATILDA_CONFIG` overrides the path.
- Defaults < TOML < environment < `configure()` runtime overrides.
- New sessions use `~/.matilda/brain/sessions/`; legacy `~/.ttt/sessions/` remains readable.
- Tool names disabled in config must not be exposed through `--tools`.
- Server defaults to `127.0.0.1:8772`, requires bearer auth outside health/preflight, and denies CORS unless explicitly allowed.
- Preserve the single request pipeline for sync, async, session, stateless, server, and tool-loop paths.

## Change discipline

- Read before editing and keep changes scoped.
- Do not add parallel config, request, policy, or session owners.
- Add behavior-focused regression tests for contract changes.
- Never commit unless explicitly requested.
- Shared macOS/Linux checkouts should use `core.filemode=false`; record executable bits with `git update-index --chmod=+x PATH` when needed.
