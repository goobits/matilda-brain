# System Architecture

Matilda Brain provides a unified API and CLI over multiple AI providers.

## Overview

```
CLI / Python API -> Core API -> Router -> Backends -> Providers
```

## Core Components

- `src/matilda_brain/api.py`: `ask`, `stream`, `chat` entry points
- `src/matilda_brain/session/`: chat sessions and history
- `src/matilda_brain/core/routing.py`: model/backend selection
- `src/matilda_brain/backends/`: cloud and local backends
- `src/matilda_brain/tools/`: tool registry and execution
- `src/matilda_brain/config/`: configuration loading and merge logic

## Request Flow

1. CLI or Python API receives input.
2. Router resolves model and backend.
3. Backend performs request and returns `AIResponse`.
4. API returns response or streams chunks.
