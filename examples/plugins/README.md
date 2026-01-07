# Plugin Examples

Example plugins for custom backends:

- `echo_backend.py`
- `mock_llm_backend.py`

## Load a Plugin

```python
from matilda_brain import load_plugin
from pathlib import Path

load_plugin(Path("echo_backend.py"))
```
