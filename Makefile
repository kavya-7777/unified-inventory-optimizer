.PHONY: help install dev test lint format migrate seed generate-data run docker-up docker-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (local)
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
	cd frontend && npm install

dev: ## Run development servers locally
	(cd backend && ../.venv/bin/uvicorn app.main:app --reload) & (cd frontend && npm run dev)

test: ## Run backend tests (inside Docker)
	docker compose exec backend pytest tests/ -v

lint: ## Lint codebase (inside Docker)
	docker compose exec backend ruff check .
	cd frontend && npm run lint

format: ## Format codebase
	cd backend && ../.venv/bin/ruff format .

makemigrations: ## Generate a new database migration
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

migrate: ## Run database migrations inside Docker container
	docker compose exec backend alembic upgrade head

seed: ## Seed database with initial data
	docker compose exec backend python /scripts/seed_database.py

generate-data: ## Generate synthetic test data locally
	python3 scripts/generate_data.py --size medium

run: ## Run pipeline script
	.venv/bin/python scripts/run_pipeline.py

docker-up: ## Start local docker environment
	docker compose up -d

docker-down: ## Stop local docker environment
	docker compose down
