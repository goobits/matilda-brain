# Matilda Brain Development Makefile

.PHONY: help test test-unit test-integration test-fast lint format type-check quality clean install dev

help: ## Show this help message
	@echo "Matilda Brain Development Commands:"
	@echo "===================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

test: ## Run all tests with smart rate limiting
	@./scripts/test.sh

test-unit: ## Run unit tests only (fast, no API calls)
	@./scripts/test.sh unit

test-integration: ## Run integration tests (real API calls)
	@./scripts/test.sh integration

test-fast: ## Run tests without rate limiting delays
	@python3 -m pytest tests/ -x -q --fast

lint: ## Run linting with ruff
	@echo "Running linter..."
	@ruff check src/matilda_brain/ tests/

format: ## Format code with black
	@echo "Formatting code..."
	@black src/matilda_brain/ tests/ --line-length 120

type-check: ## Run type checking with mypy
	@echo "Running type checker..."
	@mypy src/matilda_brain/

quality: format lint type-check ## Run all code quality checks
	@echo "All quality checks completed!"

clean: ## Clean up build artifacts and cache
	@echo "Cleaning up..."
	@rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete

install: ## Install package with pipx
	@./scripts/setup.sh install

dev: ## Install in development mode
	@./scripts/setup.sh install --dev
