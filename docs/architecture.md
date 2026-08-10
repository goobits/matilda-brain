# Architecture

Matilda Brain exposes one request model through CLI, Python, session, stateless, and HTTP adapters.

```text
CLI / Python / HTTP
        |
        v
  core/request.py ------> tools/loop.py
        |                       |
        v                       v
  core/routing.py ------> tools/policy.py
        |
        v
 cloud / local / Hub backend
        |
        v
    AIResponse
```

## Owners

- `core/request.py` constructs backend parameters and executes complete or streaming requests.
- `core/routing.py` resolves aliases, models, backends, and configured fallbacks.
- `backends/` adapts provider protocols; tool-capable cloud requests use the shared model/tool loop.
- `tools/` owns registration, schema generation, safety policy, execution, retries, and recovery.
- `session/chat.py` adds history, persistence, metadata, and optional memory to the same request pipeline.
- `config/manager.py` is the only owner of defaults, shared TOML, environment overrides, runtime configuration, and persistence.
- `server.py` validates HTTP input and maps the same domain responses into stable Matilda envelopes.

## Boundary rules

- Adapters do not recreate routing or tool policy.
- Backend-specific options enter through `AIRequest.options`; canonical fields win on conflicts.
- Public package exports are lazy to keep import cost and optional-provider side effects low.
- Generated CLI code delegates to `app_hooks.py`; business logic belongs in internal hooks and domain modules.
- Sessions and HTTP clients have explicit close paths.
