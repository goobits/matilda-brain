# Changelog

All notable changes to Matilda Brain will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-01-12

### Added
- **Memory Integration** - Connect to matilda-memory service for persistent agent knowledge
- **Identity Fetching** - Agent identity with TTL cache and precedence logic
- **Cerebras Support** - Added zai-glm-4.7 model to provider registry
- **Memory CLI Commands** - Debug commands for memory inspection

### Changed
- **TOML Configuration** - Migrated from YAML to shared TOML format
- **Public API** - Exported core types and improved module structure
- **CLI Hooks** - Rewired through goobits with improved defaults

### Fixed
- Tool system critical issues (found by Cerebras review)
- Recovery system critical issues (found by Cerebras review)
- Exception handling replaces sys.exit for better error propagation

### Removed
- Legacy YAML configuration support
- ChatSession backward compatibility alias

## [1.0.3] - 2025-11-01

### Added
- Initial stable release with multi-provider AI chat
- Support for OpenRouter, OpenAI, Anthropic, Google, Ollama
- Function calling with @tool decorator
- Streaming responses
- Session management

[1.1.0]: https://github.com/goobits/matilda-brain/compare/v1.0.3...v1.1.0
[1.0.3]: https://github.com/goobits/matilda-brain/releases/tag/v1.0.3
