# Unified Inventory Optimizer

Unified Inventory Optimization platform: forecasting, safety-stock placement and transportation planning across suppliers, DCs and stores in one model.

## Architecture
```mermaid
graph TD
    A[React Frontend] -->|HTTPS| B(FastAPI Backend)
    B --> C[(MySQL 8)]
    B --> D[Unified Optimization Engine]
    D --> E[Forecasting]
    D --> F[GSM]
    D --> G[CP-SAT / LP]
    D --> H[Transportation LP]
```

## Tech Stack
- **Frontend**: React 19 with TypeScript (Vite, Tailwind CSS, TanStack Query, Recharts)
- **Backend**: FastAPI (Python 3.11), SQLAlchemy, Alembic
- **Database**: MySQL 8 (PyMySQL driver); hosted on Aiven's free plan in production
- **Forecasting & optimization**: NumPy, SciPy (LP), Google OR-Tools (CP-SAT), statistical forecasting models implemented in-house
- **Auth**: bcrypt password hashing, JWT bearer tokens, role-based access
- **Excel**: openpyxl (import template, validation, results export)
- **Infrastructure**: Docker, GitHub Actions, Render (backend), Aiven (MySQL), Vercel (frontend)

## Features
- **Sign-in with roles**: Admin, Planner and Viewer (see [Roles](#roles)).
- **Excel import**: download a template, upload `.xlsx`/`.csv`, see every invalid row before anything is saved; imports are all-or-nothing and recorded in an import history.
- **Excel export**: targets, inventory positions, transport plan and open alerts in one workbook.
- **First-run setup**: an empty deployment guides the admin to import data or load the demo network.
- **Activity log**: who ran the pipeline, edited policies, resolved alerts, imported data or changed users.
- **Works on phones**: collapsible navigation and scrollable tables.

## Repository Structure
- `backend/`: FastAPI application, optimization engine, demo-data generator
- `backend/migrations/`: Database migrations (Alembic), applied automatically on start
- `frontend/`: React application (`vercel.json` holds the Vercel config)
- `scripts/`: Command-line wrappers to seed demo data and run the pipeline
- `render.yaml`: Render Blueprint for the backend
- `.github/`: CI/CD workflows and issue templates

## Local Setup
1. Clone the repository: `git clone <repo> && cd unified-inventory-optimizer`
2. Set environment variables: `cp .env.example .env` and `cp frontend/.env.example frontend/.env`
3. Start MySQL, FastAPI and React: `sudo docker compose up -d --build` (migrations run automatically)
4. Load the demo data and run the pipeline once: `sudo make demo`
5. Sign in at http://localhost:5173 as **admin@example.com / admin12345** (the local default; change it with `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `.env` before the first start)
6. Run tests: `sudo make test`

*(Depending on your Docker group permissions, you may need to prefix Docker and Make commands with `sudo`.)*

Access the apps:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

Trigger a full pipeline run from the terminal with `make run`, or from the Optimization page in the UI.

## Deployment
The backend deploys to Render, the MySQL database to Aiven's free plan and the frontend to Vercel. Step-by-step guide:
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Roles
| | Viewer | Planner | Admin |
|---|:-:|:-:|:-:|
| Dashboard, Network, Inventory, Demand, Transportation, Runs, Alerts, Policies (view), Excel export | ✅ | ✅ | ✅ |
| Run the pipeline, Optimization page | | ✅ | ✅ |
| Edit policies, resolve alerts | | ✅ | ✅ |
| Data Import (Excel/CSV) and import history | | ✅ | ✅ |
| Users, Activity log, load/reset demo data | | | ✅ |

The backend enforces every rule; the UI only hides what a role can't use.

Project overview: [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md) · How it works, step by step: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) · Demo script: [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md)

## Environment Variables
See `.env.example`. Never commit `.env` or any secrets.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | MySQL connection, e.g. `mysql+pymysql://user:pass@host:3306/db`. Aiven's `mysql://…?ssl-mode=REQUIRED` Service URI works as is and turns on TLS |
| `DATABASE_SSL_CA` | Optional: the database provider's CA certificate (PEM text or path) to verify the server |
| `CORS_ORIGINS` | Comma-separated frontend URLs allowed to call the API |
| `JWT_SECRET` | Signs session tokens; required (32+ chars) when `APP_ENV=production` |
| `JWT_EXPIRE_MINUTES` | Session length (default 480 = 8 hours) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME` | First admin, created while no users exist |
| `API_KEY` | Machine token for the nightly GitHub Action (acts as a planner named "system") |
| `VITE_API_URL` (frontend) | Backend base URL |

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
- `nightly-pipeline.yml`: Nightly network run against the deployed backend.
- Deployment itself is done by Render and Vercel, which rebuild on every push to `main`.

## Optimization Pipeline
`POST /api/v1/network/run` (the Optimization page's **Network run**, `make run`, or the nightly
workflow) runs in the background on the data in the database:
1. **Forecast** every store × SKU series: classify the demand pattern (ADI / CV²), backtest
   Naive, Seasonal Naive, Moving Average, SES, damped Holt, Holt-Winters, Croston, SBA and TSB on
   a holdout window, keep the lowest-MASE model and forecast with a 95% interval.
2. **Roll demand up** the network: each DC and supplier sees the demand it serves downstream.
3. **Optimize** each SKU with the Guaranteed Service Model (CP-SAT, heuristic fallback) to get
   service times, safety stock, reorder point and EOQ per node.
4. **Alert** where on-hand stock is below the new safety stock.
5. **Plan transportation** with a multi-SKU min-cost LP that respects lane capacities.

Poll `GET /api/v1/runs/{id}` for progress; results are at `/api/v1/runs/{id}/results`.

## Database Tables
| Table | Holds |
|---|---|
| `locations` | Suppliers, DCs and stores |
| `products` | SKU catalog with unit cost |
| `lanes` | Transport links between locations (transit days, cost, capacity) |
| `location_product_policies` | Per location × SKU settings: service level, service-time bounds, costs, processing time. A location carries a SKU only if it has a policy for it |
| `demand_history` | Daily sales per store × SKU |
| `inventory_snapshots` | On hand / on order / in transit per location × SKU |
| `demand_forecasts` | Forecasts (with 95% bounds) written by each network run |
| `optimization_results` | Optimized targets per run, location and SKU |
| `pipeline_runs` | Run audit trail: parameters, status, summary, who started it |
| `alerts` | Stockout risks, capacity, fallback and transport issues |
| `lead_time_observations` | Reserved for measured lead times |
| `users` | Accounts: email, name, bcrypt password hash, role, active flag |
| `audit_events` | Activity log: who did what, when |
| `data_imports` | Committed Excel/CSV imports with per-sheet counts |

## Team Responsibilities
- [Name 1]: [Roles/Responsibilities]
- [Name 2]: [Roles/Responsibilities]
