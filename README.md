# MEIO Platform

Multi-Echelon Inventory Optimization (MEIO) Platform.

## Architecture
```mermaid
graph TD
    A[React Frontend] -->|HTTPS| B(FastAPI Backend)
    B --> C[(PostgreSQL)]
    B --> D[MEIO Optimization Engine]
    D --> E[Forecasting]
    D --> F[GSM]
    D --> G[CP-SAT / LP]
    D --> H[Transportation LP]
```

## Tech Stack
- **Frontend**: React (Vite, TypeScript)
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Optimization**: OR-Tools (CP-SAT/LP), custom modules
- **Infrastructure**: Docker, GitHub Actions

## Repository Structure
- `backend/`: FastAPI application, optimization engine, database migrations (Alembic)
- `frontend/`: React application
- `database/`: Database seed scripts and migrations
- `scripts/`: Data generation and pipeline execution scripts
- `.github/`: CI/CD workflows and issue templates

## Local Setup
1. Clone the repository: `git clone <repo> && cd meio-platform`
2. Set environment variables: `cp .env.example .env` and `cp frontend/.env.example frontend/.env`
3. Start Postgres, FastAPI and React: `sudo docker compose up -d --build`
4. Run migrations: `sudo make migrate`
5. Generate synthetic data and seed it: `make generate-data && sudo make seed`
6. Run tests: `sudo make test`

*(Depending on your Docker group permissions, you may need to prefix Docker and Make commands with `sudo`.)*

Access the apps:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

Trigger a full pipeline run from the terminal with `make run`, or from the Optimization page in the UI.

## Environment Variables
See `.env.example`. Never commit `.env` or any secrets.
Set `API_KEY` to require `Authorization: Bearer <key>` on POST/PATCH endpoints; the frontend sends it from `VITE_API_KEY`.

## Git Workflow
We use a feature branch workflow:
1. `main`: stable, demo-ready
2. `develop`: integration branch
3. `feature/*`: individual development
4. `fix/*`: bug fixes

Use conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `ci:`.

## CI/CD
GitHub Actions run on every push to `develop` and `main`, as well as on PRs.
- `backend-ci.yml`: Python linting, typing, and tests.
- `frontend-ci.yml`: Node linting, typing, and build.
- `deploy.yml`: Staging deployment from `develop`, production from `main`.

## MEIO Pipeline
The pipeline runs daily and executes:
1. Data Validation
2. Demand Classification & Forecast
3. GSM Optimization (Safety Stock, ROP, Order Quantity)
4. Transportation Optimization
5. Alerts Generation

## Team Responsibilities
- [Name 1]: [Roles/Responsibilities]
- [Name 2]: [Roles/Responsibilities]
