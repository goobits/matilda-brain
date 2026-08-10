# Examples

The examples are intentionally small and use only supported public APIs.

| File | Demonstrates |
| --- | --- |
| `01_basic_usage.py` | complete responses, streaming, conversation history |
| `02_tools_and_workflows.py` | built-in tools, `@tool`, tool-enabled chat |
| `03_chat_and_persistence.py` | JSON save/load, summary, export, cleanup |
| `04_advanced_features.py` | async calls, images, runtime config, domain errors |
| `config/matilda.toml` | shared `[brain]` configuration shape |
| `plugins/` | loadable backend plugins |

From the repository root:

```bash
python examples/01_basic_usage.py
python examples/02_tools_and_workflows.py
python examples/03_chat_and_persistence.py
python examples/04_advanced_features.py
```

The numbered scripts make provider requests. Configure a supported API key or a local Ollama backend first. Persistence output is written under `.artifacts/examples/`.
