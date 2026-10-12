.PHONY: help install dev test lint format migrate seed generate-data run docker-up docker-down reset-seed makemigrations demo

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

seed: ## Seed database with initial data (keeps existing rows)
	docker compose exec backend python /scripts/seed_database.py

reset-seed: ## Wipe all data, including run history, and reseed (history ends yesterday)
	docker compose exec backend python /scripts/seed_database.py --reset

demo: ## Fresh demo: reset data, then run the network pipeline once
	docker compose exec backend python /scripts/seed_database.py --reset
	curl -sS -X POST http://localhost:8000/api/v1/network/run \
		-H "Content-Type: application/json" \
		-H "Authorization: Bearer $${API_KEY}" \
		-d '{}'
	@echo "\nNetwork run started; it finishes in a few seconds. Open http://localhost:5173"


generate-data: ## Export the synthetic dataset to data/synthetic (seeding generates it itself)
	python3 scripts/generate_data.py

run: ## Start a database-driven network pipeline run on the local backend
	curl -sS -X POST http://localhost:8000/api/v1/network/run \
		-H "Content-Type: application/json" \
		-H "Authorization: Bearer $${API_KEY}" \
		-d '{}'

docker-up: ## Start local docker environment
	docker compose up -d

docker-down: ## Stop local docker environment
	docker compose down
