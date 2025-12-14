# TokenBrain Makefile
# Common commands for development

.PHONY: install run test lint format clean help

# Default target
.DEFAULT_GOAL := help

# Python interpreter
PYTHON := python3

# Virtual environment
VENV := venv
VENV_BIN := $(VENV)/bin

# Colors for output
GREEN := \033[0;32m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "TokenBrain - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""

install: ## Install dependencies
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	@echo "$(GREEN)Dependencies installed successfully$(NC)"

install-dev: install ## Install with dev dependencies
	$(PYTHON) -m pip install black isort ruff pre-commit
	pre-commit install
	@echo "$(GREEN)Dev dependencies installed, pre-commit hooks configured$(NC)"

run: ## Run the bot
	$(PYTHON) -m bot.main

test: ## Run tests
	$(PYTHON) -m pytest tests/ -v

test-cov: ## Run tests with coverage
	$(PYTHON) -m pytest tests/ --cov=bot --cov-report=html --cov-report=term-missing

lint: ## Run linters (ruff, black --check, isort --check)
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .
	$(PYTHON) -m isort --check .

format: ## Format code (black, isort)
	$(PYTHON) -m black .
	$(PYTHON) -m isort .
	@echo "$(GREEN)Code formatted$(NC)"

ruff-fix: ## Auto-fix ruff issues
	$(PYTHON) -m ruff check . --fix

clean: ## Clean up cache files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleaned up cache files$(NC)"

docker-build: ## Build Docker image
	docker build -t tokenbrain-bot .

docker-run: ## Run Docker container
	docker run --env-file .env tokenbrain-bot

check: lint test ## Run all checks (lint + test)
	@echo "$(GREEN)All checks passed$(NC)"
