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

reset-seed: ## Wipe planning data and run history (users kept) and reseed (history ends yesterday)
	docker compose exec backend python /scripts/seed_database.py --reset

demo: ## Fresh demo: reset planning data (users are kept), then run the network pipeline once
	docker compose exec backend python /scripts/seed_database.py --reset
	docker compose exec backend python /scripts/run_pipeline.py
	@echo "Open http://localhost:5173 and sign in (default admin@example.com / admin12345)."

generate-data: ## Export the synthetic dataset to data/synthetic (seeding generates it itself)
	docker compose exec backend python /scripts/generate_data.py

run: ## Run the database-driven network pipeline once (inside the backend container)
	docker compose exec backend python /scripts/run_pipeline.py

docker-up: ## Start local docker environment
	docker compose up -d

docker-down: ## Stop local docker environment
	docker compose down
