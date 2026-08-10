# Changelog

All notable changes to Matilda Brain are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- CHANGELOG audit cutoff: 2026-08-10. commit 0b69896 on main. -->

## [Unreleased]

### 🌟 Highlights

- 📦 One request contract now powers sync, async, chat, stateless, server, and tool-enabled calls.
- 🎯 Model-requested tools now execute through a bounded multi-round loop with complete result metadata.
- 🔒 Tool policy now restricts filesystem, network, and Python execution with optional approvals.
- 🌐 HTTP requests now receive authenticated, validated, stable response and SSE envelopes.
- ☁️ Brain-owned session storage keeps legacy `~/.ttt/sessions/` data readable.
- 🧪 The canonical offline gate now enforces formatting, lint, types, packaging, tests, and coverage.

### ✨ Added

- 📦 Package-root `stateless()` and `StatelessResponse` exports for session-free requests.
- 📦 `ttt` console entry point for backward-compatible command invocation.
- 🎯 Multi-round model tool execution with parallel calls, approvals, retry recovery, and response metadata.

### 🔧 Changed

- ☁️ Configuration now has one owner with `defaults < [brain] TOML < environment < runtime` precedence.
- ☁️ CLI sessions now write to `~/.matilda/brain/sessions/` while reading and deleting legacy sessions safely.
- 📦 Request fields and backend selection now stay consistent across every public adapter.
- 📚 Public guidance and runnable examples now match the supported CLI, TOML, tools, plugins, server, and test contracts.

### 🐛 Fixed

- 🎯 `brain ask --tools` and `brain chat --tools` now pass every enabled registry tool and honor disabled names.
- 🌐 Streaming, Hub, session, and server adapters now preserve resolved models, messages, metadata, and cleanup behavior.
- 📦 Built wheels now include typed runtime modules and entry points without packaging generated setup scripts.

### 🔒 Security

- 🎯 Tool execution now blocks path escapes, private-network targets, unsafe Python capabilities, oversized output, and unapproved high-risk calls.
- 🌐 Server access now defaults to loopback, bearer authentication, explicit CORS origins, bounded bodies, strict validation, and non-sensitive errors.
- 👤 Persistent API tokens and shared configuration writes now use private, symlink-resistant storage.

### 🏠 Internal

- 🧪 Offline verification now type-checks runtime modules and examples, builds and imports the wheel, exercises mocked integration, and enforces a 70% coverage floor.
- 📚 Obsolete YAML, removed APIs, invalid helper commands, and the one-off reproduction script were removed from maintained guidance.

## [1.1.0] - 2026-01-12

### ✨ Added

- ☁️ Matilda Memory integration for persistent agent knowledge.
- 👤 Agent identity fetching with TTL caching and precedence logic.
- 📦 Cerebras `zai-glm-4.7` model support.
- ☁️ Memory inspection commands for the CLI.

### 🔧 Changed

- ☁️ Shared TOML configuration replaced legacy YAML.
- 📦 Core types became available from the public package surface.
- 📦 Goobits hooks became the owner of generated CLI behavior.

### 🐛 Fixed

- 🎯 Tool execution and recovery failures now propagate through domain exceptions.
- 📦 Library paths no longer terminate the host process with `sys.exit`.

### 🗑️ Removed

- ☁️ Legacy YAML configuration loading.
- 📦 `ChatSession` backward-compatibility alias.

## [1.0.3] - 2025-11-01

### ✨ Added

- 📦 Initial multi-provider chat API for OpenRouter, OpenAI, Anthropic, Google, and Ollama.
- 🎯 Function calling through the `@tool` decorator.
- 📦 Streaming responses and persistent chat sessions.

[Unreleased]: https://github.com/goobits/matilda-brain/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/goobits/matilda-brain/compare/v1.0.3...v1.1.0
[1.0.3]: https://github.com/goobits/matilda-brain/releases/tag/v1.0.3
