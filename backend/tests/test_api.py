"""
Unified Inventory Optimizer Backend Test Suite.
Covers: API endpoints, optimizer known-answer tests, and forecasting accuracy.
"""
import math

from app.models.inventory import Alert, DemandForecast, OptimizationResult, PipelineRun

THREE_TIER = {
    "nodes": [
        {"id": "Supplier", "type": "Supplier", "processing_time": 2, "holding_cost": 1.0},
        {"id": "DC1", "type": "DC", "processing_time": 1, "holding_cost": 2.0},
        {"id": "Store1", "type": "Store", "processing_time": 0, "holding_cost": 5.0,
         "demand_std": 10.0, "max_s_out": 0},
    ],
    "edges": [
        {"source": "Supplier", "target": "DC1", "transit_time": 3, "cost_per_unit": 2.5,
         "capacity": 1000},
        {"source": "DC1", "target": "Store1", "transit_time": 1, "cost_per_unit": 5.0,
         "capacity": 500},
    ],
}


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready(client):
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_get_products(client):
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == ["P1"]


def test_get_locations_paginated(client):
    response = client.get("/api/v1/locations", params={"skip": 1, "limit": 1})
    assert response.status_code == 200
    assert [loc["id"] for loc in response.json()] == ["ST1"]


def test_pagination_limits_enforced(client):
    assert client.get("/api/v1/locations", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/locations", params={"skip": -1}).status_code == 422


def test_optimization_run_returns_pipeline_id(client, db_session):
    response = client.post("/api/v1/optimization/run", json={})
    assert response.status_code == 200
    data = response.json()
    run = db_session.get(PipelineRun, data["pipeline_run_id"])
    assert run.status == "success"
    assert run.solver == "cp-sat"


def test_invalid_network_returns_422_and_marks_run_failed(client, db_session):
    payload = {
        "nodes": [
            {"id": "A", "type": "DC", "processing_time": 1},
            {"id": "B", "type": "Store", "processing_time": 0},
        ],
        "edges": [
            {"source": "A", "target": "B", "transit_time": 1},
            {"source": "B", "target": "A", "transit_time": 1},
        ],
    }
    response = client.post("/api/v1/optimization/run", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_NETWORK"
    run = db_session.query(PipelineRun).one()
    assert run.status == "failed"


def test_unknown_location_reference_rejected(client):
    payload = {
        "nodes": [{"id": "X", "type": "Store", "processing_time": 0, "location_id": "NOPE"}],
        "edges": [],
    }
    response = client.post("/api/v1/optimization/run", json=payload)
    assert response.status_code == 422
    assert "Unknown location_id 'NOPE'." in response.json()["detail"]["errors"]


def test_schema_rejects_bad_service_level(client):
    payload = {"nodes": [{"id": "X", "type": "Store", "processing_time": 0, "service_level": 1.0}]}
    assert client.post("/api/v1/optimization/run", json=payload).status_code == 422


def test_schema_rejects_inverted_service_bounds(client):
    payload = {"nodes": [{"id": "X", "type": "Store", "processing_time": 0,
                          "min_s_out": 5, "max_s_out": 2}]}
    response = client.post("/api/v1/optimization/run", json=payload)
    assert response.status_code == 422


def test_results_persisted_for_mapped_nodes(client, db_session):
    payload = {
        "nodes": [
            {"id": "DC1", "type": "DC", "processing_time": 1, "demand_std": 5, "holding_cost": 1,
             "location_id": "DC1", "product_id": "P1"},
            {"id": "ST1", "type": "Store", "processing_time": 0, "demand_std": 5,
             "holding_cost": 2, "max_s_out": 0, "location_id": "ST1", "product_id": "P1"},
        ],
        "edges": [{"source": "DC1", "target": "ST1", "transit_time": 2}],
    }
    response = client.post("/api/v1/optimization/run", json=payload)
    assert response.status_code == 200, response.text
    run_id = response.json()["pipeline_run_id"]

    rows = db_session.query(OptimizationResult).filter_by(pipeline_run_id=run_id).all()
    assert {r.location_id for r in rows} == {"DC1", "ST1"}

    page = client.get(f"/api/v1/runs/{run_id}/results").json()
    assert page["total"] == 2
    assert {r["location_name"] for r in page["items"]} == {"Distribution Center 1", "Store 1"}


def test_get_run_not_found(client):
    assert client.get("/api/v1/runs/missing").status_code == 404
    assert client.get("/api/v1/runs/missing/results").status_code == 404


def test_api_key_guard(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    assert client.post("/api/v1/optimization/run", json={}).status_code == 401
    headers = {"Authorization": "Bearer s3cret"}
    assert client.post("/api/v1/optimization/run", json={}, headers=headers).status_code == 200
    assert client.get("/api/v1/runs").status_code == 200


# ─────────────────────────────────────────────
# Safety Stock / ROP / EOQ Known-Answer Tests
# ─────────────────────────────────────────────

def test_safety_stock_zero_demand_std():
    from app.optimization.safety_stock import calculate_safety_stock
    ss = calculate_safety_stock(
        service_level_z=1.645, lead_time_mean=5, lead_time_std=0, demand_mean=100, demand_std=0
    )
    assert ss == 0.0


def test_safety_stock_known_answer():
    """Z=1.645, LT_mean=4, LT_std=0, D_std=10 → SS = 1.645 * sqrt(4) * 10 = 32.9"""
    from app.optimization.safety_stock import calculate_safety_stock
    ss = calculate_safety_stock(
        service_level_z=1.645, lead_time_mean=4, lead_time_std=0.0, demand_mean=50, demand_std=10
    )
    assert abs(ss - 32.9) < 0.01


def test_safety_stock_combined_variance():
    from app.optimization.safety_stock import calculate_safety_stock
    z, lt_mean, lt_std, d_mean, d_std = 1.645, 4, 1.0, 50, 10
    expected = z * math.sqrt(lt_mean * d_std**2 + d_mean**2 * lt_std**2)
    assert abs(calculate_safety_stock(z, lt_mean, lt_std, d_mean, d_std) - expected) < 0.01


def test_reorder_point_known_answer():
    from app.optimization.reorder_point import calculate_reorder_point
    assert calculate_reorder_point(demand_mean=100, lead_time_mean=2, safety_stock=30) == 230.0


def test_eoq_known_answer():
    from app.optimization.reorder_point import calculate_order_quantity
    eoq = calculate_order_quantity(annual_demand=1000, ordering_cost=50, holding_cost_per_unit=5)
    assert abs(eoq - math.sqrt(20000)) < 0.01


def test_z_score_exact():
    from app.optimization.service_time import get_z_score
    assert abs(get_z_score(0.95) - 1.6449) < 1e-3
    assert abs(get_z_score(0.93) - 1.4758) < 1e-3


def test_net_replenishment_time():
    from app.optimization.gsm import GSMNetwork, GSMNode
    from app.optimization.service_time import compute_net_replenishment_times
    network = GSMNetwork(nodes=[GSMNode(id="DC1", type="DC", processing_time=2)], edges=[])
    net_times = compute_net_replenishment_times(network, s_in={"DC1": 5}, s_out={"DC1": 3})
    assert net_times["DC1"] == 4


# ─────────────────────────────────────────────
# GSM Solver Tests
# ─────────────────────────────────────────────

def test_cp_sat_handles_multi_sourcing():
    """A DC fed by two suppliers with different transit times must remain feasible."""
    from app.optimization.cp_sat import run_gsm_solver
    from app.optimization.gsm import GSMEdge, GSMNetwork, GSMNode
    network = GSMNetwork(
        nodes=[
            GSMNode(id="S1", type="Supplier", processing_time=1, max_s_out=5),
            GSMNode(id="S2", type="Supplier", processing_time=1, max_s_out=5),
            GSMNode(id="DC", type="DC", processing_time=1, demand_std=10, holding_cost=1),
            GSMNode(id="ST", type="Store", processing_time=0, demand_std=10, holding_cost=3,
                    max_s_out=0),
        ],
        edges=[
            GSMEdge("S1", "DC", 2),
            GSMEdge("S2", "DC", 5),
            GSMEdge("DC", "ST", 1),
        ],
    )
    result = run_gsm_solver(network, max_time=30, timeout_seconds=10)
    assert result["status"] == "OPTIMAL"
    nodes = result["nodes"]
    assert nodes["DC"]["s_in"] == max(nodes["S1"]["s_out"] + 2, nodes["S2"]["s_out"] + 5)


def test_cp_sat_uses_node_service_level():
    from app.optimization.cp_sat import run_gsm_solver
    from app.optimization.gsm import GSMNetwork, GSMNode
    from app.optimization.service_time import get_z_score

    def solve(sl):
        net = GSMNetwork(nodes=[GSMNode(id="ST", type="Store", processing_time=4,
                                        demand_std=10, holding_cost=1, max_s_out=0,
                                        service_level=sl)])
        return run_gsm_solver(net, max_time=10, timeout_seconds=5)["objective_value"]

    assert abs(solve(0.99) - get_z_score(0.99) * 10 * 2) < 0.01
    assert solve(0.99) > solve(0.90)


def test_cp_sat_beats_or_matches_heuristic():
    from app.optimization.cp_sat import run_gsm_solver
    from app.optimization.gsm import build_network_from_dicts
    from app.optimization.heuristic import run_heuristic_solver
    network = build_network_from_dicts(THREE_TIER["nodes"], THREE_TIER["edges"])
    exact = run_gsm_solver(network, max_time=30, timeout_seconds=10)["objective_value"]
    greedy = run_heuristic_solver(network)["objective_value"]
    assert exact <= greedy + 0.01


def test_heuristic_fallback_returns_feasible(client, db_session):
    payload = {
        "run_type": "manual",
        "max_service_time": 5,
        "nodes": [
            {"id": "Supplier", "type": "Supplier", "processing_time": 2, "max_s_out": 2},
            {"id": "DC1", "type": "DC", "processing_time": 1, "max_s_out": 2},
            {"id": "Store1", "type": "Store", "processing_time": 0, "max_s_out": 0},
        ],
        "edges": [
            {"source": "Supplier", "target": "DC1", "transit_time": 10},
            {"source": "DC1", "target": "Store1", "transit_time": 1},
        ],
    }
    response = client.post("/api/v1/optimization/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["solver"] == "heuristic"
    assert data["fallback_used"] is True
    assert data["status"] == "FEASIBLE"
    alert_types = {a.alert_type for a in db_session.query(Alert).all()}
    assert "SOLVER_FALLBACK" in alert_types


def test_network_validation_errors():
    from app.optimization.gsm import build_network_from_dicts
    network = build_network_from_dicts(
        [{"id": "A", "type": "DC", "processing_time": 1},
         {"id": "A", "type": "DC", "processing_time": 1},
         {"id": "C", "type": "Store", "processing_time": 0}],
        [{"source": "A", "target": "Z", "transit_time": 1}],
    )
    errors = network.validate()
    assert "Duplicate node id 'A'." in errors
    assert "Edge target 'Z' not in nodes." in errors


def test_capacity_violation_creates_alert(client, db_session):
    payload = {**THREE_TIER, "node_capacities": {"Store1": 1.0}}
    response = client.post("/api/v1/optimization/run", json=payload)
    assert response.status_code == 200
    assert response.json()["capacity_violations"]
    alerts = client.get("/api/v1/alerts", params={"resolved": False}).json()
    capacity = [a for a in alerts if a["alert_type"] == "CAPACITY_EXCEEDED"]
    assert len(capacity) == 1

    resolved = client.post(f"/api/v1/alerts/{capacity[0]['id']}/resolve")
    assert resolved.json()["resolved"] is True


# ─────────────────────────────────────────────
# Transportation Tests
# ─────────────────────────────────────────────

def test_transportation_counts_demand_only_at_sinks():
    from app.transportation.optimizer import optimize_transportation
    nodes = [
        {"id": "S", "demand_mean": 0},
        {"id": "DC", "demand_mean": 500},
        {"id": "ST", "demand_mean": 100},
    ]
    edges = [
        {"source": "S", "target": "DC", "cost_per_unit": 1.0},
        {"source": "DC", "target": "ST", "cost_per_unit": 2.0},
    ]
    result = optimize_transportation(nodes, edges)
    assert result["status"] == "OPTIMAL"
    assert result["flows"] == {"S->DC": 100.0, "DC->ST": 100.0}
    assert result["total_cost"] == 300.0


def test_transportation_infeasible_capacity():
    from app.transportation.optimizer import optimize_transportation
    nodes = [{"id": "S"}, {"id": "ST", "demand_mean": 100}]
    edges = [{"source": "S", "target": "ST", "capacity": 10}]
    assert optimize_transportation(nodes, edges)["status"] == "INFEASIBLE"


# ─────────────────────────────────────────────
# Demand Classification & Forecasting Tests
# ─────────────────────────────────────────────

def test_smooth_demand_classification():
    from app.forecasting.classifier import DemandPattern, classify_demand
    assert classify_demand([10, 12, 9, 11, 10, 13, 10, 11]) == DemandPattern.SMOOTH


def test_intermittent_demand_classification():
    from app.forecasting.classifier import DemandPattern, classify_demand
    history = [0, 0, 10, 0, 0, 8, 0, 0, 0, 12, 0]
    assert classify_demand(history) == DemandPattern.INTERMITTENT


def test_ses_constant_demand():
    from app.forecasting.models import ses
    fit = ses([100.0] * 10, 3, alpha=0.3)
    assert all(abs(f - 100.0) < 0.01 for f in fit.forecast)


def test_holt_forecast_never_negative():
    from app.forecasting.models import holt
    assert min(holt([50, 40, 30, 20, 10, 5], 10).forecast) >= 0.0


def test_holt_winters_recovers_weekly_pattern():
    from app.forecasting.models import holt_winters
    week = [10, 10, 10, 10, 10, 30, 30]
    fit = holt_winters(week * 8, 7)
    assert [round(v) for v in fit.forecast] == week


def test_croston_known_answer():
    """[0, 0, 10, 0, 10] with alpha=0: size 10, first interval 3 → 10 / 3"""
    from app.forecasting.models import croston
    assert round(croston([0.0, 0.0, 10.0, 0.0, 10.0], 1, alpha=0.0).forecast[0], 4) == 3.3333


def test_sba_applies_bias_correction():
    from app.forecasting.models import croston, sba
    y = [0, 4, 0, 0, 6, 0, 5, 0, 0, 0, 7]
    assert abs(sba(y, 1, 0.2).forecast[0] - 0.9 * croston(y, 1, 0.2).forecast[0]) < 1e-9


def test_tsb_decays_after_demand_stops():
    from app.forecasting.models import croston, tsb
    y = [5, 0, 6, 0, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    assert tsb(y, 1, 0.3, 0.1).forecast[0] < croston(y, 1, 0.3).forecast[0]


def test_engine_all_zero_series():
    from app.forecasting.engine import forecast_series
    result = forecast_series([0.0] * 30, 5)
    assert result["method"] == "Zero"
    assert result["forecast"] == [0.0] * 5


def test_engine_selects_seasonal_model_for_weekly_demand():
    import random

    from app.forecasting.engine import forecast_series
    rng = random.Random(1)
    week = [20, 18, 19, 21, 25, 45, 40]
    history = [week[t % 7] + rng.gauss(0, 1.5) for t in range(84)]
    result = forecast_series(history, 14)
    assert result["pattern"] == "smooth"
    assert result["method"] in ("Holt-Winters", "Seasonal Naive")
    assert result["metrics"]["mase"] < 1
    assert len(result["leaderboard"]) >= 5
    assert all(lo <= f <= hi for lo, f, hi in
               zip(result["lower"], result["forecast"], result["upper"]))


def test_engine_routes_intermittent_to_intermittent_models():
    from app.forecasting.engine import forecast_series
    history = [0, 0, 10, 0, 0, 8, 0, 0, 12, 0] * 3
    result = forecast_series(history, 4)
    assert result["pattern"] == "intermittent"
    assert {m["method"] for m in result["leaderboard"]} >= {"Croston", "Croston-SBA", "TSB"}


def test_forecasting_runner_shape():
    from app.forecasting.runner import run_forecast_pipeline
    items = [{"id": "SKU1", "history": [0, 0, 10, 0, 0, 8, 0, 0, 12, 0]}]
    result = run_forecast_pipeline(items, horizon=4)[0]
    assert result["method"] in ("Croston", "Croston-SBA", "TSB", "Moving Average", "SES")
    assert len(result["forecast"]) == len(result["lower"]) == len(result["upper"]) == 4


def test_forecast_endpoint(client):
    payload = {"items": [{"id": "A", "history": [5, 5, 5, 5]}, {"id": "B", "history": [7]}],
               "horizon": 2}
    response = client.post("/api/v1/forecast/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["forecasts"][1]["forecast"] == [7.0, 7.0]


# ─────────────────────────────────────────────
# Demand Ingestion Tests
# ─────────────────────────────────────────────

def test_ingest_demand_counts_inserts_and_updates(client):
    first = {"records": [
        {"location_id": "ST1", "product_id": "P1", "date": "2024-01-01", "quantity": 10},
        {"location_id": "ST1", "product_id": "P1", "date": "2024-01-02", "quantity": 15},
    ]}
    data = client.post("/api/v1/demand/ingest", json=first).json()
    assert (data["inserted_count"], data["updated_count"]) == (2, 0)

    second = {"records": [
        {"location_id": "ST1", "product_id": "P1", "date": "2024-01-02", "quantity": 20},
        {"location_id": "ST1", "product_id": "P1", "date": "2024-01-03", "quantity": 5},
        {"location_id": "ST1", "product_id": "P1", "date": "2024-01-03", "quantity": 6},
        {"location_id": "BAD", "product_id": "P1", "date": "2024-01-03", "quantity": 1},
    ]}
    data = client.post("/api/v1/demand/ingest", json=second).json()
    assert data["inserted_count"] == 1
    assert data["updated_count"] == 1
    assert data["ignored_count"] == 2
    assert data["errors"] == ["Unknown location_id 'BAD'"]

    history = client.get(
        "/api/v1/demand/history", params={"location_id": "ST1", "product_id": "P1"}
    ).json()
    assert [(h["date"], h["quantity"]) for h in history] == [
        ("2024-01-01", 10.0), ("2024-01-02", 20.0), ("2024-01-03", 6.0),
    ]


def test_demand_history_date_filter(client):
    records = [
        {"location_id": "ST1", "product_id": "P1", "date": f"2024-01-0{d}", "quantity": d}
        for d in range(1, 6)
    ]
    client.post("/api/v1/demand/ingest", json={"records": records})
    params = {"location_id": "ST1", "product_id": "P1",
              "start_date": "2024-01-02", "end_date": "2024-01-04"}
    history = client.get("/api/v1/demand/history", params=params).json()
    assert [h["quantity"] for h in history] == [2.0, 3.0, 4.0]

    params["start_date"] = "2024-02-01"
    assert client.get("/api/v1/demand/history", params=params).status_code == 422


def test_ingest_rejects_negative_quantity(client):
    payload = {"records": [
        {"location_id": "ST1", "product_id": "P1", "date": "2024-01-01", "quantity": -1}
    ]}
    assert client.post("/api/v1/demand/ingest", json=payload).status_code == 422


# ─────────────────────────────────────────────
# E2E Pipeline Tests
# ─────────────────────────────────────────────

def test_end_to_end_pipeline(client):
    payload = {
        "run_type": "daily_batch",
        "horizon": 4,
        "max_service_time": 30,
        **THREE_TIER,
        "items_history": [{"id": "Store1", "history": [100.0, 110.0, 90.0, 105.0, 100.0, 110.0]}],
    }
    response = client.post("/api/v1/pipeline/run", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "SUCCESS"

    assert data["stages"]["forecast"]["status"] == "SUCCESS"
    assert data["stages"]["forecast"]["count"] == 1
    assert data["stages"]["gsm"]["status"] == "OPTIMAL"

    transport = data["stages"]["transportation"]
    assert transport["status"] == "OPTIMAL"
    flows = transport["flows"]
    assert flows["Supplier->DC1"] == flows["DC1->Store1"]
    assert 90.0 < flows["DC1->Store1"] < 110.0

    run = client.get(f"/api/v1/runs/{data['pipeline_run_id']}").json()
    assert run["status"] == "success"


def test_pipeline_defaults_without_network(client):
    response = client.post("/api/v1/pipeline/run", json={"run_type": "scheduled"})
    assert response.status_code == 200, response.text
    assert response.json()["stages"]["transportation"]["status"] == "OPTIMAL"


def test_pipeline_persists_forecasts_for_mapped_nodes(client, db_session):
    payload = {
        "nodes": [
            {"id": "DC1", "type": "DC", "processing_time": 1, "location_id": "DC1",
             "product_id": "P1"},
            {"id": "ST1", "type": "Store", "processing_time": 0, "max_s_out": 0,
             "location_id": "ST1", "product_id": "P1"},
        ],
        "edges": [{"source": "DC1", "target": "ST1", "transit_time": 1}],
        "items_history": [{"id": "ST1", "history": [10, 12, 11, 9, 10]}],
        "horizon": 3,
    }
    response = client.post("/api/v1/pipeline/run", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["stages"]["forecast"]["saved"] == 3
    assert db_session.query(DemandForecast).count() == 3
    assert data["node_results"]["ST1"]["safety_stock"] > 0


# ─────────────────────────────────────────────
# Lanes / Policies / Dashboard / Transportation Plan
# ─────────────────────────────────────────────

def _seed_network(db, days=7):
    from datetime import timedelta

    from app.models.base import utcnow
    from app.models.inventory import DemandHistory, Lane, LocationProductPolicy

    db.add_all([
        Lane(id="L1", source_id="SUP1", target_id="DC1", transit_time=5, cost_per_unit=1.0,
             capacity=1000),
        Lane(id="L2", source_id="DC1", target_id="ST1", transit_time=1, cost_per_unit=2.0,
             capacity=1000),
        LocationProductPolicy(id="POL0", location_id="SUP1", product_id="P1", max_s_out=10,
                              processing_time=2, holding_cost=0.5),
        LocationProductPolicy(id="POLD", location_id="DC1", product_id="P1", max_s_out=5,
                              processing_time=1, holding_cost=1.0),
        LocationProductPolicy(id="POL1", location_id="ST1", product_id="P1", service_level=0.95,
                              max_s_out=0, processing_time=0, holding_cost=2.0),
    ])
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    db.add_all(
        DemandHistory(location_id="ST1", product_id="P1", date=today - timedelta(days=d),
                      quantity=float(8 + (d * 7) % 5))
        for d in range(1, days + 1)
    )
    db.commit()


def test_get_lanes(client, db_session):
    _seed_network(db_session)
    lanes = client.get("/api/v1/lanes").json()
    assert {(lane["source_id"], lane["target_id"]) for lane in lanes} == {
        ("SUP1", "DC1"), ("DC1", "ST1"),
    }
    assert lanes[0]["source_name"]


def test_policies_list_filter_and_update(client, db_session):
    _seed_network(db_session)
    assert len(client.get("/api/v1/policies", params={"q": "Store"}).json()) == 1
    assert client.get("/api/v1/policies", params={"q": "nomatch"}).json() == []

    updated = client.patch("/api/v1/policies/POL1", json={"service_level": 0.9, "max_s_out": 3})
    assert updated.status_code == 200
    assert (updated.json()["service_level"], updated.json()["max_s_out"]) == (0.9, 3)

    assert client.patch("/api/v1/policies/POL1", json={"min_s_out": 5}).status_code == 422
    assert client.patch("/api/v1/policies/POL1", json={"service_level": 1.5}).status_code == 422
    assert client.patch("/api/v1/policies/missing", json={"service_level": 0.9}).status_code == 404


def test_dashboard_summary(client, db_session):
    _seed_network(db_session)
    client.post("/api/v1/optimization/run", json={})
    data = client.get("/api/v1/dashboard/summary").json()
    assert data["total_policies"] == 3
    assert data["last_run"]["status"] == "success"
    assert data["measured_pairs"] == 0


def test_transportation_plan(client, db_session):
    assert client.get("/api/v1/transportation/plan").json()["status"] == "NO_EDGES"
    _seed_network(db_session)
    plan = client.get("/api/v1/transportation/plan").json()
    assert plan["status"] == "OPTIMAL"
    assert plan["active_lanes"] == 2
    daily = sum(8 + (d * 7) % 5 for d in range(1, 8)) / 7
    assert plan["demand_basis"] == "history"
    assert plan["total_cost"] == round(daily * (1.0 + 2.0), 2)
    assert all(f["product_name"] == "Product 1" for f in plan["lane_flows"])


def test_transportation_plan_no_demand(client, db_session):
    _seed_network(db_session, days=0)
    plan = client.get("/api/v1/transportation/plan").json()
    assert plan["status"] == "NO_DEMAND_DATA"


def test_transportation_history_window_ends_at_last_sale(client, db_session):
    """Old history still plans: the trailing window counts back from the last recorded day."""
    from datetime import datetime, timedelta

    from app.models.inventory import DemandHistory
    _seed_network(db_session, days=0)
    last = DemandHistory(location_id="ST1", product_id="P1", quantity=12.0,
                         date=datetime(2024, 1, 31))
    db_session.add_all([last, DemandHistory(location_id="ST1", product_id="P1", quantity=99.0,
                                            date=datetime(2024, 1, 31) - timedelta(days=60))])
    db_session.commit()
    plan = client.get("/api/v1/transportation/plan", params={"days": 28}).json()
    assert plan["status"] == "OPTIMAL"
    assert plan["planned_units"] == 24.0


def test_multi_sku_shares_lane_capacity():
    from app.transportation.optimizer import optimize_transportation_multi_sku
    lanes = [
        {"id": "cheap", "source_id": "S", "target_id": "ST", "cost_per_unit": 1, "capacity": 10},
        {"id": "pricey", "source_id": "S", "target_id": "ST", "cost_per_unit": 5},
    ]
    skus = [
        {"product_id": "A", "demand_by_location": {"ST": 8}},
        {"product_id": "B", "demand_by_location": {"ST": 8}},
    ]
    result = optimize_transportation_multi_sku(lanes, skus)
    assert result["status"] == "OPTIMAL"
    assert result["total_cost"] == 10 * 1 + 6 * 5


# ─────────────────────────────────────────────
# Database-driven network pipeline
# ─────────────────────────────────────────────

def _seed_snapshot(db, on_hand):
    from app.models.inventory import InventorySnapshot
    db.add_all([
        InventorySnapshot(location_id="ST1", product_id="P1", on_hand=on_hand, on_order=0,
                          in_transit=0),
        InventorySnapshot(location_id="DC1", product_id="P1", on_hand=500, on_order=0,
                          in_transit=0),
    ])
    db.commit()


def test_echelon_demand_pools_variance():
    from types import SimpleNamespace

    from app.services.network import echelon_demand
    lanes = [SimpleNamespace(source_id="DC", target_id=s) for s in ("A", "B")]
    lanes.append(SimpleNamespace(source_id="S1", target_id="DC"))
    lanes.append(SimpleNamespace(source_id="S2", target_id="DC"))
    demand = echelon_demand({"S1", "S2", "DC", "A", "B"}, lanes,
                            {"A": (10.0, 3.0), "B": (20.0, 4.0)})
    assert demand["DC"] == (30.0, 5.0)
    assert demand["S1"] == (15.0, 2.5)


def test_network_run_end_to_end(client, db_session):
    _seed_network(db_session, days=60)
    _seed_snapshot(db_session, on_hand=0)

    response = client.post("/api/v1/network/run", json={"horizon": 7, "history_days": 56})
    assert response.status_code == 202
    run_id = response.json()["pipeline_run_id"]

    run = client.get(f"/api/v1/runs/{run_id}").json()
    assert run["status"] == "success", run["error"]
    summary = run["summary"]
    assert summary["products_optimized"] == 1
    assert summary["series_forecast"] == 1
    assert summary["nodes_optimized"] == 3
    assert summary["stockout_alerts"] == 1
    assert summary["transportation"]["status"] == "OPTIMAL"

    results = client.get(f"/api/v1/runs/{run_id}/results").json()
    by_loc = {r["location_id"]: r for r in results["items"]}
    assert set(by_loc) == {"SUP1", "DC1", "ST1"}
    assert by_loc["DC1"]["demand_mean"] == by_loc["ST1"]["demand_mean"] > 0
    assert by_loc["ST1"]["sku"] == "SKU-1"

    alerts = client.get("/api/v1/alerts", params={"resolved": False}).json()
    assert [a["alert_type"] for a in alerts] == ["STOCKOUT_RISK"]
    assert alerts[0]["location_id"] == "ST1"

    positions = client.get("/api/v1/inventory/positions").json()
    assert positions["total"] == 2
    store = next(p for p in positions["items"] if p["location_id"] == "ST1")
    assert store["status"] == "STOCKOUT_RISK"
    assert store["recommended_order"] > 0
    assert positions["counts"]["STOCKOUT_RISK"] == 1

    plan = client.get("/api/v1/transportation/plan").json()
    assert plan["demand_basis"] == "forecast"

    client.post("/api/v1/optimization/run", json={"nodes": [{"id": "X", "type": "DC",
                                                              "processing_time": -1}]})
    dash = client.get("/api/v1/dashboard/summary").json()
    assert dash["measured_pairs"] == 2
    assert dash["at_risk_count"] == 1
    assert dash["last_run"]["id"] == run_id

    # A second run supersedes the first run's stockout alerts instead of piling them up.
    client.post("/api/v1/network/run", json={"horizon": 7, "history_days": 56})
    open_alerts = client.get("/api/v1/alerts", params={"resolved": False}).json()
    assert len(open_alerts) == 1
    assert open_alerts[0]["pipeline_run_id"] != run_id


def test_network_run_without_history_fails_cleanly(client):
    run_id = client.post("/api/v1/network/run", json={}).json()["pipeline_run_id"]
    run = client.get(f"/api/v1/runs/{run_id}").json()
    assert run["status"] == "failed"
    assert "demand history" in run["error"]


def test_network_run_rejects_concurrent_run(client, db_session):
    from app.repositories.pipeline import PipelineRunRepository
    PipelineRunRepository(db_session).create("busy", "network", {})
    response = client.post("/api/v1/network/run", json={})
    assert response.status_code == 409
    assert response.json()["detail"]["pipeline_run_id"] == "busy"


def test_inventory_positions_filters(client, db_session):
    _seed_network(db_session)
    _seed_snapshot(db_session, on_hand=50)
    data = client.get("/api/v1/inventory/positions", params={"location_type": "Store"}).json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "NO_PLAN"
    assert client.get("/api/v1/inventory/positions", params={"q": "zzz"}).json()["total"] == 0
    assert client.get("/api/v1/inventory/positions",
                      params={"status": "BOGUS"}).status_code == 422


def test_classify_position_rules():
    from app.services.inventory import classify_position
    assert classify_position(5, 5, None, None, None) == "NO_PLAN"
    assert classify_position(5, 50, 10, 30, 20) == "STOCKOUT_RISK"
    assert classify_position(20, 25, 10, 30, 20) == "REORDER"
    assert classify_position(60, 60, 10, 30, 20) == "EXCESS"
    assert classify_position(40, 40, 10, 30, 20) == "HEALTHY"


def test_demand_forecast_endpoint(client, db_session):
    _seed_network(db_session, days=60)
    params = {"location_id": "ST1", "product_id": "P1", "horizon": 10, "history_days": 56}
    data = client.get("/api/v1/demand/forecast", params=params).json()
    assert len(data["history"]) == 56
    assert len(data["forecast"]) == 10
    assert data["backtest"]
    assert sum(m["selected"] for m in data["leaderboard"]) == 1
    assert data["forecast"][0]["date"] > data["history"][-1]["date"]
    missing = {**params, "location_id": "NOPE"}
    assert client.get("/api/v1/demand/forecast", params=missing).status_code == 404


def test_locations_filter_by_type(client):
    stores = client.get("/api/v1/locations", params={"type": "Store"}).json()
    assert [s["id"] for s in stores] == ["ST1"]


def test_policy_processing_time_update(client, db_session):
    _seed_network(db_session)
    updated = client.patch("/api/v1/policies/POLD", json={"processing_time": 4}).json()
    assert updated["processing_time"] == 4
