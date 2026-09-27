# MEIO Platform — Frontend

React + TypeScript + Vite dashboard for the Multi-Echelon Inventory Optimization (MEIO) backend.

## Stack

- **Vite 8** + **React 19** + **TypeScript**
- **Tailwind CSS v4** (via `@tailwindcss/vite`) for styling
- **TanStack Query** for data fetching/caching against the FastAPI backend
- **React Router** for client-side routing
- **Recharts** for the demand-history chart
- **lucide-react** for icons

## Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard — backend health, quick counts, recent pipeline runs |
| `/inventory` | Paginated Locations and Products tables |
| `/demand` | Query demand history (chart + table) and bulk-ingest new demand records |
| `/optimization` | Run the GSM solver, demand forecast, or the full daily pipeline, with JSON editors for nodes/edges/history |
| `/runs` | Pipeline run history |
| `/runs/:runId` | Single run detail |

All API calls live in [`src/lib/api.ts`](src/lib/api.ts), typed against the backend's Pydantic schemas in [`src/lib/types.ts`](src/lib/types.ts).

## Setup

```bash
npm install
cp .env.example .env   # defaults to http://localhost:8000
npm run dev
```

The app runs at `http://localhost:5173`. It expects the backend (see `../backend`) running at `VITE_API_URL` (default `http://localhost:8000`), with `CORS_ORIGINS` on the backend including `http://localhost:5173`.

Bring up the full stack (Postgres + backend + frontend) from the repo root with:

```bash
docker compose up
```

## Scripts

- `npm run dev` — start the Vite dev server
- `npm run build` — type-check (`tsc -b`) and build for production
- `npm run preview` — preview the production build locally
- `npm run lint` — run oxlint
