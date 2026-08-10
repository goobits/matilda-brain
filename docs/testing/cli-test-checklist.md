# CLI coverage matrix

The generated CLI contract is covered by automated tests; this file is a map, not a dated manual checklist.

| Surface | Covered behavior | Primary tests |
| --- | --- | --- |
| Root and help | default `ask`, recursive help, version, debug | `tests/unit/test_cli_smoke.py`, `tests/unit/cli/test_cli_options.py` |
| Ask | prompt/stdin, model aliases, system, temperature, token limit, stream, JSON, tools | `tests/integration/cli/test_cli_parameters.py`, `tests/integration/test_cli_comprehensive_integration.py` |
| Chat | create/resume, history, clear/exit, tool handoff | `tests/unit/cli/test_cli_chat.py`, `tests/unit/test_tools_chat.py` |
| Models/status/info | table and JSON output, alias resolution | `tests/unit/cli/test_cli_models.py`, `tests/unit/cli/test_cli_json.py` |
| Config | get/set/list, nested values, secret redaction | `tests/unit/cli/test_cli_config.py`, `tests/unit/test_config.py` |
| Tools | list/enable/disable and enabled-tool filtering | `tests/unit/cli/test_cli_tools.py`, `tests/unit/test_tools_chat.py` |
| Stateless/server | parameter forwarding and loopback defaults | `tests/unit/test_stateless.py`, `tests/unit/test_project_contracts.py` |

Run the complete contract with:

```bash
make check
```
