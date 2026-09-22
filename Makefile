# KubanFy development Makefile
# Usage: make <target>

.PHONY: help dev test lint format migrate seed worker api install clean \
        docker-up docker-down docker-logs

ROOT := $(shell pwd)
API_DIR := $(ROOT)/apps/api
PYTHON := python3
PIP := pip3

help:
	@echo "KubanFy development commands"
	@echo ""
	@echo "  make install     Install API dependencies (editable + dev)"
	@echo "  make api         Run API with uvicorn (reload)"
	@echo "  make worker      Run background worker (placeholder)"
	@echo "  make migrate     Run Alembic migrations"
	@echo "  make seed        Seed development data"
	@echo "  make test        Run pytest"
	@echo "  make lint        Run ruff + mypy"
	@echo "  make format      Format with ruff"
	@echo "  make docker-up   Start Postgres + Redis (+ optional MinIO)"
	@echo "  make docker-down Stop containers"
	@echo "  make docker-logs Follow container logs"
	@echo "  make clean       Remove caches and build artifacts"
	@echo ""

install:
	cd $(API_DIR) && $(PIP) install -e ".[dev]"

api:
	cd $(API_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd $(API_DIR) && PYTHONPATH=. python -m app.workers.runner
	

migrate:
	cd $(API_DIR) && alembic upgrade head

migrate-down:
	cd $(API_DIR) && alembic downgrade -1

migrate-revision:
	@read -p "Revision message: " msg; \
	cd $(API_DIR) && alembic revision --autogenerate -m "$$msg"

seed:
	cd $(API_DIR) && python -m scripts.seed

test:
	cd $(API_DIR) && pytest -v --tb=short

test-cov:
	cd $(API_DIR) && pytest -v --cov=app --cov-report=term-missing

lint:
	cd $(API_DIR) && ruff check app tests
	cd $(API_DIR) && mypy app

format:
	cd $(API_DIR) && ruff format app tests
	cd $(API_DIR) && ruff check --fix app tests

docker-up:
	docker compose -f infrastructure/docker-compose.yml up -d

docker-down:
	docker compose -f infrastructure/docker-compose.yml down

docker-logs:
	docker compose -f infrastructure/docker-compose.yml logs -f

dev: docker-up
	@echo "Infrastructure started. Run 'make api' in another terminal."
	@echo "Or use: docker compose -f infrastructure/docker-compose.yml up"

clean:
	find $(ROOT) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find $(ROOT) -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find $(ROOT) -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find $(ROOT) -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find $(ROOT) -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(API_DIR)/.coverage $(API_DIR)/htmlcov
