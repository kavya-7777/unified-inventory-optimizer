# Demo Guide

A 12-minute live walkthrough of the Unified Inventory Optimizer, with what to click, what to
say, and what to do if something goes wrong. For the theory behind each step, see
[PROJECT_GUIDE.md](PROJECT_GUIDE.md).

Commands below assume your user is in the `docker` group. If not, prefix them with `sudo`.

---

## 1. Preparation

### The day before

```bash
git pull
docker compose up -d --build
make migrate
make demo
```

Then click through every page once (section 2) so nothing surprises you on the day.
Record a short screen capture of the full walkthrough as a backup.

### 30 minutes before

```bash
docker compose ps        # all three containers "Up", postgres "healthy"
make demo                # fresh data (history ends yesterday) + one network run
```

- Open http://localhost:5173 and check the top-right pill says **Backend online**.
- Zoom the browser to 110–125% so the room can read the tables.
- Keep a terminal open with `docker compose logs -f backend` in case you need it.
- Keep [PROJECT_GUIDE.md](PROJECT_GUIDE.md) open for questions.

`make demo` wipes all data, including run history, and loads a clean dataset. Run it
before every demo, and again afterwards to undo any live changes.

---

## 2. The walkthrough

| # | Time | Page | Purpose |
|---|---|---|---|
| 1 | 1 min | Dashboard | State the problem |
| 2 | 1.5 min | Network | Show the supply chain |
| 3 | 2.5 min | Demand & Forecast | Show forecasting and model selection |
| 4 | 2 min | Optimization → Network run | Run the whole pipeline live |
| 5 | 2 min | Run detail | Explain where stock should sit and why |
| 6 | 1.5 min | Inventory | Turn targets into actions |
| 7 | 1.5 min | Policies → re-run | Live what-if |
| 8 | 1 min | Transportation, Alerts | Close the loop |

### Step 1 — Dashboard: the problem (1 min)

**Show:** the Dashboard.

**Say:**
> "A retailer has 5 factories, 3 regional warehouses and 20 stores selling 50 products. Every
> location has to decide how much stock to hold. Too little and shelves go empty; too much and
> money sits idle. The catch is that the levels affect each other — a big buffer at the
> warehouse lets stores hold less. This platform decides all levels together. That's called
> unified inventory optimization."

Point at the tiles: inventory value, share of stock above safety stock, items at risk, open
alerts.

### Step 2 — Network: the supply chain (1.5 min)

**Click:** **Network**.

**Show:** the three columns (suppliers, DCs, stores), then scroll to the **Lanes** table.

**Say:**
> "Each product comes from the factory that makes it — groceries from Mysuru and Vijayawada,
> electronics from Sriperumbudur. Each lane has a transit time, a freight cost and a daily
> capacity. Grocery is dual-sourced, which the optimizer has to handle."

### Step 3 — Demand & Forecast (2.5 min)

**Click:** **Demand & Forecast**. Select **Koramangala Store, Bengaluru** and
**GRO-006 — Sunflower Oil 1 L**.

**Point at:**

- The zig-zag in the chart: sales peak every Friday to Sunday.
- **Selected model:** usually **Holt-Winters**, the model that captures a weekly cycle (the
  winner can change from day to day, since the data is regenerated when you seed).
- **MASE below 1**: it beats a "same as last week" forecast.
- The orange dashed **Backtest** line over the last two weeks, and the shaded **95% interval**
  on the forecast.
- The **Model comparison** table below the chart.

**Say:**
> "The system classifies each series by its pattern, then backtests every suitable model on
> the last two weeks and picks the most accurate one. That's done automatically for all
> 1,000 store-product combinations."

**Then select:** **Hampankatta Store, Mangaluru** and **ELE-008 — Table Fan 400 mm**. The
pattern badge shows **INTERMITTENT** and the selected model is from the Croston family
(Croston, Croston-SBA or TSB).

**Say:**
> "A table fan sells on very few days. That's intermittent demand, so the system switches to
> Croston-family models, which forecast how much sells and how often separately. And note the
> error σ under the forecast — that number, not raw demand, is what drives safety stock."

### Step 4 — Optimization: run the pipeline live (2 min)

**Click:** **Optimization**. On the **Network run** tab, leave **All SKUs** and click
**Run network pipeline**.

**While it runs (5–10 seconds), say:**
> "This uses the data in the database. It forecasts every store and product, adds demand up
> through the warehouses to the factories, solves an optimization model per product to decide
> where safety stock should sit, checks today's stock against the new targets, and plans the
> cheapest truck flows."

**When it finishes, point at:** SKUs optimized (50/50), series forecast with the median MASE,
safety stock value, stockout risks, and the demand-pattern and model breakdown.

### Step 5 — Run detail: where stock should sit (2 min)

**Click:** **Open run details**. In the SKU filter, choose **GRO-001 — Sona Masoori Rice 5 kg**.

**Compare three rows:** a supplier (Mysuru), **Bengaluru Regional DC**, and a store
(for example Adyar).

**Say:**
> "The factories quote a 3-day service time equal to their production time, so they hold no
> safety stock. The Bengaluru DC waits 7 days for the slower supplier and promises its stores
> immediate delivery, so it holds the buffer. Stores only cover their one-day transit. That's
> risk pooling: one store's busy day cancels another's slow day, so one central buffer is
> cheaper than twenty separate ones."

If asked how the number is computed: safety stock = z × σ × √T, for example
1.645 × 8.4 × √8 ≈ 39 at the DC.

### Step 6 — Inventory: from targets to actions (1.5 min)

**Click:** **Inventory**. Point at the five status tiles, then set the status filter to
**Stockout risk**.

**Say:**
> "Each row compares today's stock with the targets we just computed. Stockout risk means on
> hand is below safety stock; Reorder means stock plus incoming orders has hit the reorder
> point. The Suggested order column tops it back up to the reorder point plus one economic
> order quantity."

### Step 7 — Live what-if (1.5 min)

1. **Click:** **Policies**. Choose **Koramangala Store, Bengaluru** in the location filter and
   type **Sunflower** in the search box.
2. Change **Service level %** from **98** to **99.5**. Click **Save**.
3. **Click:** **Optimization**. In **SKUs**, choose **GRO-006 — Sunflower Oil 1 L** and click
   **Run network pipeline**. It finishes in about a second.
4. **Click:** **Open run details**. Find **Koramangala Store, Bengaluru**.

**Say:**
> "Its safety stock rose by about a quarter — from roughly 4 to 5 units — while every other
> node stayed the same. Going from 98% to 99.5% service needs z to go from 2.05 to 2.58. The
> last one and a half percent of service is expensive, and this lets a planner see that
> trade-off before committing to it."

### Step 8 — Transportation and alerts: close the loop (1 min)

**Click:** **Transportation**. Point at the **DEMAND: LATEST FORECAST** badge, total cost per
day and capacity utilization. Choose **APP-002 — Cotton Saree** in the SKU filter: only the
Tiruppur Garment Unit ships it.

**Click:** **Alerts**. Resolve one alert.

**Closing line:**
> "So in one run the platform forecasts demand, decides where stock should sit across all
> three levels, flags what needs action today, and plans the trucks — and every setting is
> editable, so planners can test decisions before making them."

### Optional extras (if time allows)

- **API docs** at http://localhost:8000/docs: every endpoint is documented and callable.
- **Tests:** `make test` runs the automated test suite, including known-answer checks for every
  algorithm.

---

## 3. If something goes wrong

| Symptom | Fix |
|---|---|
| Pill says **Backend unreachable** | `docker compose ps`, then `docker compose restart backend` |
| Pages are empty or show "No plan" | No network run yet: run `make demo` |
| Network run shows **failed** | Read the error on the run page; `docker compose logs backend --tail 50`; then `make demo` |
| "Run … is still running" | A run is in progress; the page follows it automatically. Wait a few seconds |
| Forecast dates look old | The data was seeded on an earlier day: run `make demo` |
| `docker` permission denied | Use `sudo`, or check only one Docker is installed (`snap list docker` should find nothing) |
| Anything else | Switch to the backup screen recording and keep talking |

---

## 4. After the demo

```bash
make demo     # undo the what-if change and reset to a clean state
```

---

## 5. Questions you may get

The main technical questions are answered in section 9 of [PROJECT_GUIDE.md](PROJECT_GUIDE.md).
A few more that come up in demos:

**Is this real data?**
No — it's synthetic, generated with a fixed random seed so it is reproducible. It is designed to
look realistic: weekend peaks for groceries, rare sales for electronics, festival spikes for
apparel, and slow trends.

**How fast is it?**
One full run forecasts 1,000 series and optimizes 1,216 location-product targets in about 5–10
seconds on a laptop. A single-product what-if takes under a second.

**What would change for a real company?**
Load their sales, stock and network into the same tables (or through the demand ingest API),
set their policies, and schedule the nightly run. The algorithms don't change.

**What would you add next?**
Measured, variable lead times (the `lead_time_observations` table is ready for it), automatic
purchase orders from the suggested-order column, and promotion and holiday inputs for the
forecasts.
