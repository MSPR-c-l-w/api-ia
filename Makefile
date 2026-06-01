.DEFAULT_GOAL := help
.PHONY: help install setup-hooks lint format test test-unit test-integration test-e2e \
        docker-build docker-run clean

# ── Setup ──────────────────────────────────────────────────────────────────────

install: ## Install all dev dependencies
	pip install --no-cache-dir -r requirements-dev.txt

setup-hooks: ## Install pre-commit hooks (pre-commit + pre-push)
	pre-commit install --hook-type pre-commit
	pre-commit install --hook-type pre-push
	@echo "Hooks installed: pre-commit (lint/format) + pre-push (unit tests)"

# ── Code quality ───────────────────────────────────────────────────────────────

lint: ## Run ruff linter
	ruff check .

lint-fix: ## Run ruff linter with auto-fix
	ruff check --fix .

format: ## Format code with ruff
	ruff format .

format-check: ## Check formatting without modifying files
	ruff format --check .

# ── Tests ──────────────────────────────────────────────────────────────────────

test: ## Run all tests except e2e
	pytest -m "not e2e" --tb=short -q

test-unit: ## Run unit tests with coverage report
	pytest -m "not integration and not e2e" \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=html \
		--tb=short \
		-q

test-integration: ## Run integration tests (requires MongoDB on localhost:27017)
	pytest -m "integration" --tb=short -v

test-e2e: ## Run e2e tests (requires full stack)
	pytest -m "e2e" --tb=short -v

# ── Docker ─────────────────────────────────────────────────────────────────────

docker-build: ## Build the Docker image locally
	docker build -t healthai-coach-api:local .

docker-run: ## Run the full stack with docker compose
	docker compose up --build

docker-run-detached: ## Run the full stack in the background
	docker compose up --build -d

# ── Utilities ─────────────────────────────────────────────────────────────────

clean: ## Remove Python caches and build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	rm -rf .pytest_cache .coverage coverage.xml htmlcov .ruff_cache

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
