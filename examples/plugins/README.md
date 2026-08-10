# Plugin examples

- `echo_backend.py`: minimal backend contract
- `mock_llm_backend.py`: deterministic offline backend with streaming

Load an explicit plugin:

```python
from pathlib import Path

from matilda_brain import ask, load_plugin

load_plugin(Path("examples/plugins/echo_backend.py"))
print(ask("hello", backend="echo"))
```

For automatic discovery, copy a file into `~/.matilda/brain/plugins/` or `./matilda_brain_plugins/`.
