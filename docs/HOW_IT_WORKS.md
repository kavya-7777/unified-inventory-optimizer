# How It Works — End to End

This guide teaches the Unified Inventory Optimizer from the ground up. For every step it
answers the same six questions:

- **What** happens?
- **Input** — what goes in?
- **How** — what method is used, with a worked example?
- **Output** — what comes out, and where you can see it?
- **Who** uses it?
- **Why** is it beneficial?

The examples use real numbers from the demo data. The data is regenerated every time you run
`make demo` (so that history always ends yesterday), so your screen will show slightly
different numbers, but the logic is identical.

Related documents:

- [PROJECT_GUIDE.md](PROJECT_GUIDE.md) — a shorter overview and examiner questions
- [DEMO_GUIDE.md](DEMO_GUIDE.md) — the 12-minute presentation script

---

## Contents

1. [The big picture](#1-the-big-picture)
2. [Words you need](#2-words-you-need)
3. [Who uses it](#3-who-uses-it)
4. [The inputs: what the system knows](#4-the-inputs-what-the-system-knows)
5. [One network run, step by step](#5-one-network-run-step-by-step)
6. [Following one product all the way through](#6-following-one-product-all-the-way-through)
7. [Every page: input, output, who, why](#7-every-page-input-output-who-why)
8. [A day in the life](#8-a-day-in-the-life)
9. [Behind the scenes: how a click becomes a result](#9-behind-the-scenes-how-a-click-becomes-a-result)
10. [Benefits, summed up](#10-benefits-summed-up)
11. [Limits and assumptions](#11-limits-and-assumptions)
12. [Check your understanding](#12-check-your-understanding)

---

## 1. The big picture

### The business

A retail chain in South India:

```
5 factories (suppliers) ──▶ 3 regional warehouses (DCs) ──▶ 20 stores ──▶ customers
```

It sells 50 products, from rice and cooking oil to table fans and sarees.

### The question it answers

> **For every product at every location: how much stock should we keep, and when should
> we reorder?**

### Why that's hard

- **Demand is uncertain.** Nobody knows exactly how much oil Koramangala will sell tomorrow.
- **Supply takes time.** A truck from Vijayawada to Bengaluru takes 4 days.
- **The levels affect each other.** If the Bengaluru warehouse keeps a big buffer, its 7
  stores can keep small ones. If it keeps none, every store needs a big buffer of its own.

Deciding each location separately wastes money. This system decides all three levels
together, in one model. That is what "unified" means.

### The whole system on one page

```
INPUTS (database)                    PROCESS (one "network run")                OUTPUTS (database + UI)
─────────────────                    ───────────────────────────                ───────────────────────
Sales history ──────────────┐
                            ├──▶ 1. Forecast demand ──────────────────────▶ Forecasts + accuracy
Locations, products, lanes ─┤    2. Add demand up the chain
                            ├──▶ 3. Optimize stock targets (GSM) ─────────▶ Safety stock, reorder
Policies (service levels,   │                                                point, order quantity
  costs, lead times) ───────┤    4. Compare with today's stock ───────────▶ Stock status + alerts
                            │
Today's stock ──────────────┘    5. Plan truck flows ──────────────────────▶ Transportation plan
                                 6. Save a summary ────────────────────────▶ Run history
```

---

## 2. Words you need

| Term | Plain meaning | Example |
|---|---|---|
| **SKU** | One specific product | GRO-006, Sunflower Oil 1 L |
| **Location / node** | Any place that holds or ships stock | Koramangala Store, Bengaluru |
| **Tier** | One level of the chain: suppliers, DCs or stores | DCs are the middle tier |
| **DC** | Distribution centre — a regional warehouse | Bengaluru Regional DC |
| **Lane** | A shipping route between two locations | Bengaluru DC → Koramangala Store |
| **Transit time** | Days a shipment spends on a lane | 1 day |
| **Processing time** | Days a location needs to handle an order before shipping | DC: 1 day; supplier: 3 days to produce |
| **Policy** | The settings for one product at one location | 98% service level, ₹400 per order |
| **Service level** | Target chance of *not* running out during a replenishment cycle | 98% |
| **On hand** | Units physically on the shelf | 37 |
| **On order / in transit** | Units ordered but not yet arrived | 17 + 13 |
| **Inventory position** | On hand + on order + in transit | 67 |
| **Forecast** | Expected demand per day | 13.4 units/day |
| **Forecast error (σ)** | How wrong forecasts typically are, in units/day | 1.9 units/day |
| **Safety stock** | Extra stock kept only to absorb forecast error | 3.95 units |
| **Reorder point (ROP)** | When the inventory position drops to this, order more | 17.4 units |
| **EOQ** | Economic order quantity — the order size that balances ordering and holding costs | 323 units |
| **Holding cost** | Cost of keeping one unit for one day (storage, capital) | ₹0.10 per unit per day |
| **Ordering cost** | Fixed cost of placing one order | ₹400 |
| **Days of cover** | How many days current stock lasts at forecast demand | 2.8 days |
| **Service time (S_out)** | Days a location promises its customers it will take to ship | DC promises 0 days to stores |
| **Net replenishment time (T)** | Days a location must cover from its own stock | Store: 1 day |
| **Risk pooling** | Combining many uncertain demands reduces total uncertainty | 7 stores' ups and downs partly cancel |
| **MASE** | Forecast accuracy score; below 1 beats a "same as last week" guess | 0.45 |

---

## 3. Who uses it

| Role | What they do with it | Main pages |
|---|---|---|
| **Inventory planner** | Checks which items are at risk each morning and places orders | Dashboard, Inventory, Alerts |
| **Demand planner** | Reviews forecasts and their accuracy; spots odd demand | Demand & Forecast |
| **Supply-chain manager** | Sets service-level targets and cost rules; tests "what if" changes | Policies, Optimization, Run detail |
| **Logistics / transport planner** | Plans daily truck loads within lane capacity | Transportation, Network |
| **Store / regional manager** | Sees their own locations' stock status | Inventory (filtered), Network |
| **IT / data team** | Loads sales and stock data, schedules the nightly run | Demand ingest, API, nightly job |

---

## 4. The inputs: what the system knows

Everything starts from data in the PostgreSQL database. In a real company this would come
from the point-of-sale and warehouse systems; here it is generated by the seed script.

| Input (table) | What it holds | Example row | Who maintains it | How it gets in |
|---|---|---|---|---|
| `locations` | Suppliers, DCs and stores | Koramangala Store, Bengaluru — Store — Karnataka | IT / master data | Seed script |
| `products` | The catalog | GRO-006 Sunflower Oil 1 L — Grocery — ₹150 | IT / master data | Seed script |
| `lanes` | Shipping routes | Bengaluru DC → Koramangala: 1 day, ₹2.48/unit, 612 units/day | Logistics | Seed script |
| `location_product_policies` | Rules per location × product | Koramangala × Sunflower Oil: 98% service, ₹400/order, 0 days processing | Supply-chain manager | Seed script; edited on the **Policies** page |
| `demand_history` | Daily sales per store × product | Koramangala × Sunflower Oil, 11 Oct: 16 units | IT, daily | Seed script; **Demand ingest** form / API |
| `inventory_snapshots` | Today's stock | Koramangala × Sunflower Oil: 37 on hand, 17 on order, 13 in transit | IT, daily | Seed script |

**One important rule:** a location *carries* a product only if it has a policy row for it.
That's how the system knows, for example, that table fans come only from the Sriperumbudur
Electronics Plant: only that supplier has policies for electronics.

---

## 5. One network run, step by step

A **network run** is the main process. It is started by:

- the **Run network pipeline** button on the **Optimization** page,
- `make run` or `make demo` in a terminal, or
- the nightly scheduled job (GitHub Actions workflow).

The code lives in `backend/app/services/network.py`. A full run over all 50 products takes
about 5–10 seconds.

| Step | Input | Output |
|---|---|---|
| 0. Start and record | Run settings | A run record with status "running" |
| 1. Load the network | Locations, products, lanes, policies | An in-memory picture of who supplies whom |
| 2. Forecast demand | 90 days of store sales | 1,000 forecasts + accuracy + forecast error σ |
| 3. Add demand up the chain | Store forecasts, lanes | Demand and σ at every DC and supplier |
| 4. Optimize stock targets | Demand, σ, policies, lanes | Safety stock, reorder point, EOQ for 1,216 location × product pairs |
| 5. Check today's stock | Targets + today's stock | Status per item + stockout alerts |
| 6. Plan transportation | Store forecasts, lanes, capacities | Cheapest daily truck flows |
| 7. Save the summary | Everything above | Run marked "success", with key numbers |

### Step 0 — Start and record

**What:** creates a record of the run, then does the work in the background.

**Input:** settings from the Optimization page:

| Setting | Default | Meaning |
|---|---|---|
| SKUs | All | Which products to optimize |
| Forecast horizon | 14 days | How far ahead to forecast |
| History window | 90 days | How much past sales to learn from |
| Max service time | 30 days | Upper limit on service-time promises |

**How:**

1. The API (`POST /api/v1/network/run`) checks no other run is in progress. If one is, it
   answers "409 – run in progress" and the page follows that run instead.
2. It writes a row to `pipeline_runs` with status `running`.
3. It replies immediately with the run's ID and starts the work in a background thread.
4. The page asks `GET /api/v1/runs/{id}` every 1.5 seconds until the status is `success` or
   `failed`.

**Output:** a run ID and a "running" status shown on the page.

**Who:** whoever clicks the button, or the nightly scheduler.

**Why it's beneficial:** the page never freezes while the maths runs, two runs can't clash,
and every run is recorded for auditing.

### Step 1 — Load the network

**What:** reads the master data into memory.

**Input:** `products`, `locations`, `lanes`, `location_product_policies`.

**How:** for each product it works out:

- **Carriers:** the locations that have a policy for it.
- **Lanes:** the routes whose *both* ends carry it.

For Sunflower Oil, the carriers are the 20 stores, the 3 DCs and the two grocery suppliers
(Mysuru and Vijayawada). The Sriperumbudur electronics plant is excluded.

**Output:** a separate small network for each product.

**Who:** automatic.

**Why it's beneficial:** each product is planned on the network that can actually supply it.
Electronics are never planned to come from a rice mill.

### Step 2 — Forecast demand

**What:** predicts daily demand for every store × product — 1,000 series.

**Input:** the last 90 days of sales for each pair. Missing days count as zero. Example:
Koramangala, Sunflower Oil, last 14 days:

```
28 Sep  29  30  1 Oct  2   3   4   5   6   7   8   9   10  11
  13    11  12   13   18  16  18  10   9  13  13  18  15  16
```

Notice the pattern: higher on Friday, Saturday and Sunday.

**How — four sub-steps** (code: `backend/app/forecasting/`):

**2a. Classify the demand pattern.** Two numbers describe a series:

- **ADI** — average days between sales. Koramangala oil sells every day, so ADI = 1.0.
- **CV²** — how much sale sizes vary. Here it's 0.05, so very steady.

| | Steady sizes (CV² < 0.49) | Variable sizes (CV² ≥ 0.49) |
|---|---|---|
| **Sells most days (ADI < 1.32)** | Smooth | Erratic |
| **Many zero days (ADI ≥ 1.32)** | Intermittent | Lumpy |

Koramangala oil is **smooth**. The Mangaluru table fan sold on only 4 of the last 90 days
(ADI = 90 ÷ 4 = 22.5), so it is **intermittent**.

**2b. Pick candidate models for that pattern.**

| Model | Idea in one line | Used for |
|---|---|---|
| Naive | Tomorrow = today | Smooth / erratic |
| Seasonal Naive | Tomorrow = same weekday last week | Smooth / erratic |
| Moving Average | Average of the last 7, 14 or 28 days | Both |
| SES | Weighted average that favours recent days | Both |
| Holt (damped) | SES plus a trend that flattens out | Smooth / erratic |
| Holt-Winters | Level + trend + weekly pattern | Smooth / erratic |
| Croston | Forecasts sale size and gap between sales separately | Intermittent / lumpy |
| Croston-SBA | Croston with a correction for its known over-forecast | Intermittent / lumpy |
| TSB | Like Croston, but the forecast fades if sales stop | Intermittent / lumpy |

Each model's tuning knobs (for example, how much weight recent days get) are tried over a
grid of values, and the best-fitting setting is kept automatically.

**2c. Backtest and pick the winner.**

1. Hide the last 14 days.
2. Fit every candidate on the earlier days.
3. Make each one forecast the hidden 14 days.
4. Score each on **MASE** = its average error ÷ the error of a "same weekday last week"
   guess. Below 1 means better than that simple guess.
5. The lowest MASE wins, and is refitted on all 90 days.

Koramangala oil, today's scores:

| Model | MASE |
|---|---|
| **Seasonal Naive** ← selected | **0.45** |
| Holt-Winters | 0.61 |
| Moving Average | 0.93 |
| SES | 0.99 |
| Holt (damped) | 1.06 |
| Naive | 1.59 |

The two weekly-pattern models come top, which is exactly what the zig-zag suggests.

**2d. Produce the outputs.**

- **Forecast:** for example 10, 9, 13, 13, 18, 15, 16 units for the next seven days
  (low early in the week, high at the weekend).
- **95% interval:** a range the actual value should fall in 95% of the time. For example,
  the first day is 6.8 to 13.2.
- **demand_mean:** the average forecast per day — 13.4 units.
- **demand_std (σ):** the typical forecast error from the backtest — about 1.9 units/day.
  **This σ is what safety stock is built from.**

**Output:** 14 days × 1,000 series = 14,000 rows in `demand_forecasts`. Shown on the
**Demand & Forecast** page and in the run summary (model and pattern counts, median MASE).

**Who:** demand planners review it; the optimizer consumes it.

**Why it's beneficial:**

- Each item gets the method that suits it, automatically, instead of one formula for
  everything.
- Every forecast comes with a measured accuracy, so you know how much to trust it.
- Safety stock is sized on *forecast error*. A predictable weekly pattern needs less buffer
  than its ups and downs would suggest.

### Step 3 — Add demand up the chain

**What:** works out the demand each DC and supplier faces.

**Input:** every store's forecast mean and σ, plus the lanes.

**How:**

- A DC's demand is the **sum** of its stores' demand. Bengaluru DC serves 7 stores, so its
  Sunflower Oil demand is about 104 units/day.
- Uncertainty adds differently: σ_DC = √(σ₁² + σ₂² + … + σ₇²). That's smaller than
  σ₁ + σ₂ + … + σ₇, because one store's busy day tends to cancel another's slow day. This
  is **risk pooling**. Bengaluru DC's σ is about 7 units/day, against a simple sum of about
  18 — pooling cuts the uncertainty by more than half.
- If a location has two suppliers, each supplier is given half of its demand. Mysuru and
  Vijayawada each see about 150 units/day of Sunflower Oil, half of the three DCs' combined
  demand.

**Output:** demand mean and σ for every location × product (stored with the results).

**Who:** automatic.

**Why it's beneficial:** warehouses are planned on the demand they really face, and pooling
is measured rather than guessed.

### Step 4 — Optimize stock targets (the Guaranteed Service Model)

**What:** decides **where** in the chain to hold safety stock, and how much, at the lowest
holding cost.

**Input:** for each product, each location's demand, σ, policy (service level, holding cost,
processing time, service-time limits) and the lanes' transit times.

**How (code: `backend/app/optimization/`):**

Each location makes a promise to whoever it supplies: "I'll ship within **S_out** days".

1. **S_in** — how long a location waits for its own supply = the slowest of
   (supplier's S_out + lane transit time).
2. **Net replenishment time** T = S_in + processing time − S_out. These are the days the
   location must cover from its own shelf.
3. **Safety stock** = z × σ × √T, where z comes from the service level (90% → 1.28,
   95% → 1.645, 98% → 2.05, 99.5% → 2.58).
4. **Cost** = safety stock × holding cost per day.

The solver (Google OR-Tools **CP-SAT**) tries the possible S_out promises for every location
at once and picks the combination with the **lowest total holding cost**. If it can't finish
within the time limit, a simple "promise as late as allowed" rule gives a valid fallback, and
an alert says so.

Then, for every location:

- **Reorder point** = demand × T + safety stock
- **EOQ** = √(2 × demand × ordering cost ÷ holding cost)

**Worked example — Sunflower Oil, today's result:**

| Location | Demand/day | σ | Service | S_in | S_out | T | Safety stock | Reorder point | EOQ |
|---|---|---|---|---|---|---|---|---|---|
| Mysuru / Vijayawada (suppliers) | 150.1 | 7.3 | 90% | 0 | 3 | 0 | 0 | 0 | 2,703 |
| Bengaluru Regional DC | 103.9 | 7.0 | 95% | 7 | 0 | 8 | 32.3 | 864 | 1,558 |
| Koramangala Store | 13.4 | 1.9 | 98% | 1 | 0 | 1 | 3.95 | 17.4 | 323 |

Read it like this:

- **Suppliers** promise 3 days, equal to their production time, so T = 0 and they need **no
  safety stock**.
- **Bengaluru DC** waits 7 days: Vijayawada takes 3 days to produce plus 4 days in transit,
  and that's slower than Mysuru (3 + 1). The DC promises stores **immediate** shipment
  (S_out = 0), so it must cover all 8 days (7 waiting + 1 processing):
  1.645 × 7.0 × √8 ≈ 32 units.
- **Koramangala** gets stock from the DC in 1 day and promises customers 0 days, so it
  covers just 1 day: 2.05 × 1.9 × √1 ≈ 4 units.

The solver chose to hold the buffer at the DC, where demand is pooled, and keep stores lean.

**Output:** 1,216 rows in `optimization_results`. Shown on **Run detail**, and used by
**Inventory**, **Dashboard** and **Alerts**.

**Who:** supply-chain managers read the targets; planners act on them.

**Why it's beneficial:**

- It finds the cheapest placement of safety stock across the whole chain, not location by
  location.
- It respects each location's service target and real lead times.
- Changing one policy and re-running shows the cost of that decision immediately. For
  example, raising Koramangala's oil from 98% to 99.5% raised its safety stock by about 26%.

### Step 5 — Check today's stock and raise alerts

**What:** compares each item's current stock with its new targets.

**Input:** the latest `inventory_snapshots` row and the new optimization result for each
location × product.

**How:** each item gets one status:

| Status | Rule | Meaning |
|---|---|---|
| **Stockout risk** | On hand < safety stock | Already eating into the buffer — act now |
| **Reorder** | Inventory position ≤ reorder point | Time to place an order |
| **Excess** | On hand > reorder point + EOQ | More than you'd normally ever need |
| **Healthy** | None of the above | Within policy |
| **No plan** | No optimization result yet | Run the pipeline |

For items at risk or due to reorder, a **suggested order** is calculated: the larger of one
EOQ, or enough to bring the inventory position up to reorder point + EOQ.

**Examples (Koramangala, today):**

| Product | On hand | Position | Safety stock | Reorder point | Status | Suggested order |
|---|---|---|---|---|---|---|
| Sunflower Oil 1 L | 37 | 67 | 3.95 | 17.4 | Healthy | — |
| LED Bulb 9 W | 5 | 18 | 12.95 | 18.4 | **Stockout risk** | 241 |

Every "stockout risk" also creates an alert with severity **CRITICAL** (on hand below half
the safety stock) or **WARNING**. Alerts from the previous run for the same products are
marked resolved first, so they don't pile up.

**Output:** a status per item (computed live by `GET /api/v1/inventory/positions`) and rows
in `alerts`.

**Who:** inventory planners and store managers.

**Why it's beneficial:** turns abstract targets into a short to-do list — which items, where,
and how much to order.

### Step 6 — Plan transportation

**What:** decides how many units of each product move on each lane per day, at the lowest
freight cost.

**Input:** each store's forecast demand per product, plus every lane's cost per unit and daily
capacity. A product may only use lanes whose both ends carry it.

**How:** a **linear program** (solved with scipy's HiGHS solver):

- **Minimise:** Σ (units on lane × cost per unit) over all lanes and products.
- **Subject to:**
  - every store receives its forecast demand,
  - a DC sends out exactly what it receives (no stock appears or vanishes),
  - the total of all products on a lane stays within that lane's capacity.

**Example:** Sona Masoori Rice moves from the Bengaluru DC to Koramangala at 17.6 units/day
× ₹2.48 = ₹43.67/day.

**Output:** a daily flow plan with total cost and capacity use. Stored in the run summary and
shown on the **Transportation** page (which recalculates it from the latest forecasts). If the
lanes can't carry the demand, a **CRITICAL** "Transport infeasible" alert is raised.

**Who:** logistics and transport planners.

**Why it's beneficial:** the cheapest routing that still fits truck capacity, for all
products together, so one product's flow can't squeeze out another's.

### Step 7 — Save the summary

**What:** marks the run finished and stores its headline numbers.

**Input:** the outputs of steps 2–6.

**How:** writes a summary to the run record and sets the status to `success`. If anything
failed, the database changes are rolled back, the status is set to `failed` and the error
message is saved.

**Output:** the run summary — SKUs optimized, series forecast, median MASE, safety-stock value,
holding cost per day, stockout alerts, transportation status. Shown on the **Optimization**
page, **Run detail** and the **Dashboard**.

**Who:** managers reviewing what changed; anyone auditing past decisions.

**Why it's beneficial:** every decision can be traced back to the run and the data that
produced it.

---

## 6. Following one product all the way through

Sunflower Oil 1 L at Koramangala Store, Bengaluru:

```
SALES HISTORY      last 90 days, daily; peaks every Fri–Sun
      │
      ▼
CLASSIFY           ADI 1.0, CV² 0.05  →  smooth
      │
      ▼
BACKTEST           Seasonal Naive wins (MASE 0.45)
      │
      ▼
FORECAST           ≈ 13.4 units/day, error σ ≈ 1.9
      │
      ├──────────────────────────────▶ ADD UP THE CHAIN
      │                                Bengaluru DC: 7 stores → 104/day, σ 7.0 (pooled)
      │                                Each grocery supplier: ≈ 150/day
      ▼                                            │
OPTIMIZE (GSM)  ◀──────────────────────────────────┘
      │   Suppliers: T = 0 → no safety stock
      │   DC:        T = 8 → 32 units safety stock, reorder at 864
      │   Store:     T = 1 → 3.95 units safety stock, reorder at 17.4, order 323 at a time
      ▼
CHECK STOCK        on hand 37, position 67  → above both  → Healthy, no alert
      │
      ▼
TRANSPORT          the DC ships the store's daily demand on the 1-day lane
```

---

## 7. Every page: input, output, who, why

### Dashboard

- **Purpose:** the health of the whole network at a glance.
- **You see:** inventory value; % of items above safety stock; number at risk; open alerts;
  last run status; recent runs.
- **You do:** nothing to enter; click through to details or **Run pipeline**.
- **Behind it:** `GET /api/v1/dashboard/summary`, `GET /api/v1/runs`.
- **Who:** managers, every morning.
- **Why:** one screen tells you whether anything needs attention.

### Network

- **Purpose:** what the supply chain looks like.
- **You see:** suppliers, DCs and stores with regions, products stocked and at-risk markers;
  a table of every lane with transit days, cost and capacity.
- **You do:** read only.
- **Behind it:** `GET /api/v1/locations`, `/lanes`, `/policies`, `/alerts`.
- **Who:** logistics planners, managers, new team members.
- **Why:** shows where problems sit physically and how goods flow.

### Inventory

- **Purpose:** what to act on today.
- **You see:** status counts; a table of every location × product with on hand, incoming,
  safety stock, reorder point, days of cover, suggested order and status. Tabs for the raw
  location and product lists.
- **You do:** search; filter by location type and status; page through.
- **Behind it:** `GET /api/v1/inventory/positions` (compares the latest stock with the latest
  run's targets).
- **Who:** inventory planners, store managers.
- **Why:** a prioritised to-do list — stockout risks are listed first.

### Demand & Forecast

- **Purpose:** understand and trust the forecast for any store × product.
- **You see:** pattern, selected model, MASE and MAPE, forecast per day and its error σ; a
  chart of actual sales, the backtest and the forecast with its 95% band; a table comparing
  every model.
- **You do:** choose a store, a product, a history window and a horizon. Below, the **Ingest
  demand** form adds or corrects sales records.
- **Behind it:** `GET /api/v1/demand/forecast` (runs the forecasting engine live; saves
  nothing); `POST /api/v1/demand/ingest`.
- **Who:** demand planners; IT for ingesting data.
- **Why:** you can see *why* a forecast is what it is, and how accurate it has been.

### Optimization

- **Purpose:** run the optimizer.
- **You see / do:**
  - **Network run** tab: choose SKUs, horizon, history window and maximum service time, then
    run the full pipeline (section 5). The result summary appears when it finishes.
  - **Sandbox** tabs: type a small network or sales series as JSON and solve it. Nothing
    affects the real data. Useful for teaching and experiments.
- **Behind it:** `POST /api/v1/network/run`, then polling `GET /api/v1/runs/{id}`. The
  sandboxes use `/optimization/run`, `/forecast/run` and `/pipeline/run`.
- **Who:** supply-chain managers; the nightly job does the same automatically.
- **Why:** recompute every target in seconds after data or policy changes.

### Transportation

- **Purpose:** the daily truck plan.
- **You see:** units per day, cost per day, capacity use, active lanes; a table of flows per
  lane and product with utilisation bars. A badge says whether demand came from the latest
  forecast or from recent history.
- **You do:** filter by product.
- **Behind it:** `GET /api/v1/transportation/plan` (solves the linear program on request).
- **Who:** logistics planners.
- **Why:** cheapest feasible routing, and early warning when lanes run near capacity.

### Pipeline Runs and Run detail

- **Purpose:** history and audit.
- **You see:** every run's type, status, solver and duration; for one run, its summary and the
  full table of targets per location and product (service times, T, safety stock, reorder
  point, EOQ, and the demand and σ used).
- **You do:** filter by product; page through.
- **Behind it:** `GET /api/v1/runs`, `/runs/{id}`, `/runs/{id}/results`.
- **Who:** managers, analysts, examiners.
- **Why:** every number can be explained from its inputs.

### Policies

- **Purpose:** the business rules that drive the optimizer.
- **You see:** a grid of location × product policies.
- **You do:** edit service level, service-time limits, holding and ordering costs, review
  period and processing time; **Save**. Changes take effect on the next run.
- **Behind it:** `GET /api/v1/policies`, `PATCH /api/v1/policies/{id}` (values are validated,
  for example service level must be between 0 and 100%).
- **Who:** supply-chain managers.
- **Why:** lets management set the trade-off between service and cost, and test it before
  committing.

### Alerts

- **Purpose:** problems found by runs.
- **You see:** severity, type (stockout risk, capacity exceeded, solver fallback, transport
  infeasible), message, run and time.
- **You do:** filter; **Resolve** an alert once it's handled.
- **Behind it:** `GET /api/v1/alerts`, `POST /api/v1/alerts/{id}/resolve`.
- **Who:** planners.
- **Why:** problems come to you instead of you hunting for them.

---

## 8. A day in the life

| When | Who | What happens | Page |
|---|---|---|---|
| 02:00 UTC | System | Nightly job starts a network run with yesterday's sales | — |
| 09:00 | Inventory planner | Opens the dashboard: 95 items at risk, 95 alerts | Dashboard |
| 09:05 | Inventory planner | Filters to "Stockout risk", places the suggested orders | Inventory |
| 09:30 | Inventory planner | Resolves the handled alerts | Alerts |
| 10:00 | Logistics planner | Checks tomorrow's truck plan and any lane near capacity | Transportation |
| 11:00 | Demand planner | Investigates a product with a poor MASE | Demand & Forecast |
| 15:00 | Supply-chain manager | Tests raising a key product's service level, re-runs that SKU, compares | Policies → Optimization → Run detail |

---

## 9. Behind the scenes: how a click becomes a result

```
Browser (React page)
   │  1. You click "Run network pipeline"
   ▼
lib/api.ts  ──  POST /api/v1/network/run  (JSON body with your settings)
   ▼
FastAPI router  (backend/app/api/v1)        validates the request, checks no run is active
   ▼
Service  (backend/app/services/network.py)  runs steps 1–7 in a background thread
   │        uses forecasting/, optimization/, transportation/  (pure maths, no database)
   ▼
Repositories  (backend/app/repositories)    all database reads and writes
   ▼
PostgreSQL  (tables in section 4, plus demand_forecasts, optimization_results,
             pipeline_runs, alerts)
```

The page then asks for the run's status every 1.5 seconds and, when it's done, refreshes the
dashboard, inventory, alerts and transportation data automatically.

**Technology used:**

| Layer | Technology |
|---|---|
| UI | React, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts |
| API | FastAPI (Python), Pydantic validation |
| Optimization | Google OR-Tools CP-SAT (stock placement), SciPy HiGHS (transportation) |
| Forecasting | Own implementations of 9 models, with NumPy |
| Database | PostgreSQL, SQLAlchemy, Alembic migrations |
| Running it | Docker Compose; GitHub Actions for tests and the nightly run |

---

## 10. Benefits, summed up

| Benefit | How the system delivers it |
|---|---|
| **Less money tied up in stock** | Safety stock is held where pooling makes it cheapest — usually the DC — instead of everywhere |
| **Fewer empty shelves** | Every item has a target sized to its own forecast error and service level |
| **Better forecasts** | Each series gets the best of nine models, chosen by measured accuracy |
| **Clear daily actions** | Status, suggested orders and alerts replace manual spreadsheet checks |
| **Cheaper transport** | Truck flows minimise freight cost within lane capacity |
| **Informed trade-offs** | Change a policy, re-run in seconds, see the cost of better service |
| **Traceability** | Every run's inputs, outputs and summary are stored |

---

## 11. Limits and assumptions

- **Fixed lead times.** Transit and processing times are treated as exact. Real ones vary (the
  `lead_time_observations` table is ready for measured lead times).
- **Independent demand.** Stores' demands are assumed independent when pooling; real demands
  can move together (for example, during a festival).
- **Equal supplier split.** A location with two suppliers takes half its demand from each.
- **No promotions or holidays.** Forecasts learn only from past sales.
- **Synthetic data.** Realistic patterns, but generated, not real sales.

---

## 12. Check your understanding

1. **Why does the supplier hold no safety stock for Sunflower Oil?**
   Because it promises exactly its production time (S_out = 3 = processing time), so its net
   replenishment time T = 0, and safety stock = z × σ × √0 = 0.

2. **Why is the DC's σ (7.0) smaller than the sum of its stores' σ's (about 18)?**
   Risk pooling: uncertainties add as √(σ₁² + σ₂² + …), because one store's busy day tends to
   cancel another's slow day.

3. **Why isn't safety stock based on how much sales vary day to day?**
   Because a predictable pattern (like a weekend peak) is already in the forecast. Only the
   part the forecast gets wrong needs a buffer, and that is measured by the forecast error σ.

4. **What does MASE = 0.45 mean?**
   The model's errors are 45% of those of a "same weekday last week" guess — it is more than
   twice as accurate as that simple benchmark.

5. **An item has on hand 5, on order 13, safety stock 12.95 and reorder point 18.4. What is
   its status?**
   Stockout risk: on hand (5) is below safety stock (12.95). That rule is checked before the
   reorder rule.

6. **What happens if you raise a store's service level from 98% to 99.5%?**
   z rises from 2.05 to 2.58, so that store's safety stock rises by about 26%. Nothing else in
   the network changes.

7. **Why plan transport for all products together instead of one at a time?**
   Lane capacity is shared. Planning one at a time would let every product assume it has the
   whole truck.
