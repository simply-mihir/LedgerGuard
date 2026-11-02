.PHONY: setup lint format typecheck test db-up db-down migrate status help

PYTHON ?= uv run python
PYTEST ?= uv run pytest
RUFF ?= uv run ruff
MYPY ?= uv run mypy

help:
	@echo "LedgerGuard Development Commands:"
	@echo "  make setup      - Install Python dependencies with uv"
	@echo "  make db-up      - Start PostgreSQL 17 containers via Docker Compose"
	@echo "  make db-down    - Stop PostgreSQL containers"
	@echo "  make migrate    - Apply all pending database migrations"
	@echo "  make lint       - Run ruff linter"
	@echo "  make format     - Run ruff formatter"
	@echo "  make typecheck  - Run mypy typechecker"
	@echo "  make test       - Run test suite"
	@echo "  make status     - Inspect container and Git status"

setup:
	uv sync --extra dev

db-up:
	docker compose up -d postgres-coordinator postgres-ledger1 postgres-ledger2

db-down:
	docker compose down

migrate:
	$(PYTHON) -m ledgerguard.cli migrate --target all

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

typecheck:
	$(MYPY) src

test:
	$(PYTEST) -v

status:
	@echo "=== Docker Containers ==="
	@docker compose ps
	@echo "=== Git Status ==="
	@git status --short
