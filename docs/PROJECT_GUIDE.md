# Unified Inventory Optimizer — Project Guide

A complete walkthrough of what this project does, how it works, and how to run it.

---

## 1. The problem it solves

A retailer sells 50 products in 20 stores, supplied from 3 regional warehouses (DCs), which are
supplied by 5 factories. Every location must decide how much stock to keep:

- **Too little** and shelves go empty, which means lost sales.
- **Too much** and money sits idle in inventory, costing storage and capital (the *holding cost*).

The difficulty is that the locations affect each other. If the Chennai DC keeps a large buffer,
its stores can keep small ones, and the reverse. Optimizing each location separately wastes
money. **Multi-Echelon Inventory Optimization (MEIO)** decides all levels together. An
"echelon" is one level of the chain: suppliers, then DCs, then stores.

---

## 2. The network

```
5 Suppliers ──(1–5 days)──▶ 3 Regional DCs ──(1–2 days)──▶ 20 Stores ──▶ customers
```

| Level | Locations |
|---|---|
| Suppliers | Mysuru Food Processing Unit, Vijayawada Agro Foods, Hosur Consumer Goods Plant, Sriperumbudur Electronics Plant, Tiruppur Garment Unit |
| DCs | Chennai Regional DC, Bengaluru Regional DC, Hyderabad Regional DC |
| Stores | 20 stores across Tamil Nadu, Karnataka, Telangana and Andhra Pradesh (T. Nagar, Koramangala, Banjara Hills, …) |

- Products fall into five categories: Grocery, Personal Care, Home Care, Electronics and Apparel.
- Each product comes only from the supplier that makes it: rice from the food units, chargers
  from the electronics plant. The database records this through **policies**: a location
  carries a product only if it has a policy row for it.
- Grocery is dual-sourced (Mysuru and Vijayawada). This tests the harder case where a DC has two
  suppliers with different transit times.

---

## 3. The database tables

| Table | What it holds |
|---|---|
| `locations` | Suppliers, DCs and stores, with their region |
| `products` | The SKU catalog with unit cost (₹) |
| `lanes` | Who ships to whom: transit days, cost per unit, daily capacity |
| `location_product_policies` | Settings per location × product: target service level, holding and ordering cost, processing time, service-time limits |
| `demand_history` | 120 days of daily sales per store × product, with weekend peaks, slow-moving electronics and festival spikes for apparel |
| `inventory_snapshots` | Current stock: on hand, on order, in transit |
| `demand_forecasts` | Forecasts, with 95% bounds, written by each network run |
| `optimization_results` | Optimized targets per run, location and product |
| `pipeline_runs` | A record of every run: parameters, status, summary |
| `alerts` | Stockout risks, capacity, solver-fallback and transportation problems |
| `lead_time_observations` | Reserved for measured lead times |

---

## 4. What one network run does

This is the core of the project, in `backend/app/services/network.py`. It is started from
**Optimization → Network run** in the UI, from `make run`, or by the nightly workflow.

### Step 1 — Forecast demand for every store × product (1,000 series)

**Classify the demand pattern** using two numbers (the Syntetos–Boylan scheme):

- **ADI** (average demand interval): average days between sales. High means many zero days.
- **CV²**: how much the sale sizes vary.

| | CV² < 0.49 | CV² ≥ 0.49 |
|---|---|---|
| **ADI < 1.32** | Smooth | Erratic |
| **ADI ≥ 1.32** | Intermittent | Lumpy |

**Choose candidate models to suit the pattern:**

| Pattern | Candidate models |
|---|---|
| Smooth / erratic | Naive, Seasonal Naive, Moving Average, SES, damped Holt (adds trend), Holt-Winters (adds the weekly cycle) |
| Intermittent / lumpy | Croston, SBA, TSB, Moving Average, SES |

- **Croston** forecasts the sale size and the gap between sales separately.
- **SBA** (Syntetos–Boylan approximation) is Croston with a bias correction.
- **TSB** (Teunter–Syntetos–Babai) lets the forecast fade if an item stops selling.

Each model's smoothing parameters are fitted automatically by grid search.

**Backtest:** the last 14 days are hidden, each model is fitted on the earlier data, and each is
scored on how well it predicts the hidden days. The score is **MASE** (mean absolute scaled
error): below 1 means the model beats a "same as last week" forecast. The lowest MASE wins, and
that model is refit on all the data.

**Outputs:**

- the forecast for the horizon
- a 95% range around it
- the **forecast error σ**, which matters because safety stock exists to absorb forecast error

On the seeded data, median MASE is about 0.81, and Holt-Winters wins most often (about 400 of
1,000 series) because demand has a weekend peak.

### Step 2 — Roll demand up the network

A DC's demand is the sum of its stores' demand. Its uncertainty adds as
√(σ₁² + σ₂² + …), which is smaller than adding the σ's directly. This is **risk pooling**: one
store's busy day cancels another's slow day, which is why central stock is efficient. A node
with two suppliers splits its demand equally between them.

### Step 3 — Solve the Guaranteed Service Model (GSM) for each product

Each location promises its customers a **service time**, `S_out`: "I'll ship within this many
days". Then:

- **S_in** is how long it waits for its own supplies: the latest supplier promise plus transit
  time.
- **Net replenishment time:** `T = S_in + processing time − S_out`. This is the gap the location
  must cover from its own stock.
- **Safety stock** `= z × σ × √T`, where z comes from the service level (95% → 1.645,
  98% → 2.05).

**OR-Tools CP-SAT** picks the `S_out` values for every node that minimize total safety-stock
holding cost. If it can't finish in time, a greedy heuristic gives a usable fallback.

The run also computes:

- **Reorder point:** `ROP = demand × T + safety stock`
- **Order quantity (EOQ):** `√(2 × demand × ordering cost / holding cost)`

### Step 4 — Check today's stock against the new targets

| Status | Rule |
|---|---|
| Stockout risk | On hand is below safety stock. This raises an alert |
| Reorder | On hand + on order + in transit is at or below the reorder point |
| Excess | On hand is above reorder point + order quantity |
| Healthy | Within policy |
| No plan | No optimization result yet |

Each new run replaces the previous run's stockout alerts instead of piling them up.

### Step 5 — Plan transportation

A linear program (scipy's HiGHS solver) finds the cheapest daily flows on every lane, for every
product, that meet forecast store demand without exceeding any lane's capacity. Lane capacity is
shared across all products, and each product only moves between locations that carry it.

---

## 5. Worked example: Sona Masoori Rice 5 kg

| Node | Demand/day | σ | S_in | S_out | T | Safety stock | Reorder point |
|---|---|---|---|---|---|---|---|
| Bengaluru Regional DC | 104.4 | 8.6 | 7 | 0 | 8 | 39.9 | 875 |
| Adyar Store, Chennai | 14.2 | 3.0 | 1 | 0 | 1 | 6.1 | 20.3 |

- **DC safety stock check:** 1.645 × 8.6 × √8 ≈ 40.
- **DC reorder point check:** 104.4 × 8 + 39.9 ≈ 875.
- **The suppliers hold no stock.** Each promises a 3-day service time, equal to its production
  time, so its T = 0. The Bengaluru DC therefore waits 7 days, because the slower Vijayawada
  supplier takes 3 days to produce plus 4 days in transit.
- **The DC holds the pooled buffer.** It promises stores immediate shipment (`S_out = 0`), so
  each store only needs to cover its 1-day transit.

This is the textbook MEIO result: pool safety stock centrally and keep stores lean.

---

## 6. Architecture

```
React UI (Vite, TanStack Query) ──HTTP/JSON──▶ FastAPI routers (app/api/v1)
                                                   │
                     services        business logic: network, inventory, dashboard, transportation
                     forecasting/ · optimization/ · transportation/   pure algorithms, no database
                     repositories    all SQL ──SQLAlchemy──▶ PostgreSQL (Alembic migrations)
```

| Folder | Role |
|---|---|
| `backend/app/api/v1` | HTTP endpoints and request validation |
| `backend/app/services` | Orchestration and business rules |
| `backend/app/forecasting` | Demand classification, model library, model selection |
| `backend/app/optimization` | GSM network, CP-SAT solver, heuristic fallback, safety stock, ROP, EOQ |
| `backend/app/transportation` | Single- and multi-SKU min-cost flow LPs |
| `backend/app/repositories` | Database queries |
| `backend/app/models` | Table definitions |
| `database/migrations` | Schema history |
| `frontend/src/pages` | One file per UI page |
| `scripts` | Synthetic data generation and seeding |

- **Network runs happen in the background.** The API answers immediately with a run ID, and the
  UI checks `GET /api/v1/runs/{id}` every 1.5 seconds until the run finishes. A second run
  started while one is in progress is rejected with HTTP 409.
- **Tests:** automated tests run in CI on an in-memory database, including tests that check each
  algorithm against a known answer.
- **Optional auth:** set `API_KEY` on the backend and `VITE_API_KEY` on the frontend to require
  a bearer token on POST and PATCH requests.

---

## 7. The pages

| Page | What it shows |
|---|---|
| Dashboard | Inventory value, share of node–product pairs above safety stock, number at risk, open alerts, last network run |
| Network | Suppliers, DCs and stores with regions and at-risk markers |
| Inventory | Stock positions with status, plus location and product lists |
| Demand & Forecast | For a chosen store and product: history, backtest, forecast with 95% band, and every model's score |
| Optimization | **Network run** for the real pipeline; three sandbox tabs for hand-typed networks |
| Transportation | Daily lane flows, cost and capacity use, filterable by SKU |
| Pipeline Runs / Run detail | Run summary plus every node's service times, safety stock, reorder point and EOQ |
| Policies | Edit service levels, costs and processing times; changes feed the next run |
| Alerts | Review and resolve issues raised by runs |

---

## 8. How to run it

From the repository root:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env

sudo docker compose up -d --build   # Postgres + backend + frontend
sudo make migrate                   # apply database migrations
make generate-data                  # optional: regenerate data/synthetic/generated_data.json
sudo make reset-seed                # wipe all data and load the synthetic network
```

Then open:

- **UI:** http://localhost:5173
- **API docs:** http://localhost:8000/docs

Go to **Optimization → Network run** and click **Run network pipeline**. It takes about 5
seconds, after which every page shows real results.

Useful commands:

| Command | Purpose |
|---|---|
| `sudo make test` | Run the backend tests |
| `sudo docker compose logs -f backend` | Follow the backend logs |
| `make run` | Start a network run from the terminal |
| `sudo make seed` | Seed without deleting existing data |

---

## 9. Questions an examiner may ask

**Why not compute one safety stock per store independently?**
That ignores risk pooling. You would hold more total stock for the same service level.

**Why MASE instead of MAPE to choose models?**
MAPE divides by actual demand, so it breaks down on zero-demand days. MASE scales errors by a
naive benchmark and handles zeros.

**Why Croston, SBA or TSB for electronics?**
Electronics sell on few days. Ordinary averaging methods under-forecast right after zero days and
over-forecast right after a sale; these methods model size and frequency separately.

**Why CP-SAT for the GSM?**
The safety-stock cost grows with √T, which is not linear, but T only takes whole-day values. So
the cost of every possible T can be precomputed and the problem solved exactly as an integer
program.

**Why does the forecast error σ drive safety stock, not raw demand variability?**
Safety stock protects against the part of demand you failed to predict. A well-forecast seasonal
pattern needs less buffer than its raw variability suggests.

**What are the main simplifications?**

- Lead times are fixed (the `lead_time_observations` table is reserved for measured lead times).
- Demands at different stores are assumed independent.
- A DC with two suppliers splits its demand equally between them.
