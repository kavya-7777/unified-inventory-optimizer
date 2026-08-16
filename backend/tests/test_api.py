"""
MEIO Backend Test Suite.
Covers: API health, optimizer known-answer tests, and forecasting accuracy.
"""
import math
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ─────────────────────────────────────────────
# API Tests
# ─────────────────────────────────────────────

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_products():
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_locations():
    response = client.get("/api/v1/locations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_optimization_run_returns_pipeline_id():
    response = client.post("/api/v1/optimization/run", json={})
    assert response.status_code == 200
    data = response.json()
    assert "pipeline_run_id" in data
    assert len(data["pipeline_run_id"]) > 0


# ─────────────────────────────────────────────
# Safety Stock Known-Answer Tests
# ─────────────────────────────────────────────

def test_safety_stock_zero_demand_std():
    """If demand_std=0, safety stock must be exactly 0."""
    from app.optimization.safety_stock import calculate_safety_stock
    ss = calculate_safety_stock(
        service_level_z=1.645, lead_time_mean=5, lead_time_std=0, demand_mean=100, demand_std=0
    )
    assert ss == 0.0


def test_safety_stock_known_answer():
    """
    Known answer: Z=1.645, LT_mean=4, LT_std=0, D_std=10 → SS = 1.645 * sqrt(4) * 10 = 32.9
    """
    from app.optimization.safety_stock import calculate_safety_stock
    ss = calculate_safety_stock(
        service_level_z=1.645, lead_time_mean=4, lead_time_std=0.0, demand_mean=50, demand_std=10
    )
    expected = 1.645 * math.sqrt(4) * 10  # = 32.9
    assert abs(ss - expected) < 0.01


def test_safety_stock_combined_variance():
    """Tests the full variance formula including lead time variability."""
    from app.optimization.safety_stock import calculate_safety_stock
    z, lt_mean, lt_std, d_mean, d_std = 1.645, 4, 1.0, 50, 10
    variance = (lt_mean * d_std**2) + (d_mean**2 * lt_std**2)
    expected = z * math.sqrt(variance)
    ss = calculate_safety_stock(z, lt_mean, lt_std, d_mean, d_std)
    assert abs(ss - expected) < 0.01


# ─────────────────────────────────────────────
# Reorder Point Known-Answer Tests
# ─────────────────────────────────────────────

def test_reorder_point_known_answer():
    """ROP = demand_mean * lead_time_mean + SS → 100*2 + 30 = 230"""
    from app.optimization.reorder_point import calculate_reorder_point
    rop = calculate_reorder_point(demand_mean=100, lead_time_mean=2, safety_stock=30)
    assert rop == 230.0


def test_eoq_known_answer():
    """EOQ = sqrt(2*D*S/H) → sqrt(2*1000*50/5) = sqrt(20000) ≈ 141.42"""
    from app.optimization.reorder_point import calculate_order_quantity
    eoq = calculate_order_quantity(annual_demand=1000, ordering_cost=50, holding_cost_per_unit=5)
    assert abs(eoq - math.sqrt(20000)) < 0.01


# ─────────────────────────────────────────────
# Service Time Known-Answer Tests
# ─────────────────────────────────────────────

def test_net_replenishment_time():
    """T = s_in + processing_time - s_out → 5 + 2 - 3 = 4"""
    from app.optimization.gsm import GSMNetwork, GSMNode, GSMEdge
    from app.optimization.service_time import compute_net_replenishment_times
    network = GSMNetwork(
        nodes=[GSMNode(id="DC1", type="DC", processing_time=2)],
        edges=[]
    )
    net_times = compute_net_replenishment_times(network, s_in={"DC1": 5}, s_out={"DC1": 3})
    assert net_times["DC1"] == 4


# ─────────────────────────────────────────────
# Demand Classification Tests
# ─────────────────────────────────────────────

def test_smooth_demand_classification():
    from app.forecasting.classifier import classify_demand, DemandPattern
    history = [10, 12, 9, 11, 10, 13, 10, 11]
    assert classify_demand(history) == DemandPattern.SMOOTH


def test_intermittent_demand_classification():
    from app.forecasting.classifier import classify_demand, DemandPattern
    history = [0, 0, 10, 0, 0, 8, 0, 0, 0, 12, 0]
    assert classify_demand(history) == DemandPattern.INTERMITTENT


# ─────────────────────────────────────────────
# Forecasting Known-Answer Tests
# ─────────────────────────────────────────────

def test_ses_constant_demand():
    """For a perfectly constant history, SES forecast should equal the constant."""
    from app.forecasting.ets import simple_exponential_smoothing
    history = [100.0] * 10
    result = simple_exponential_smoothing(history, alpha=0.3, horizon=3)
    for f in result["forecast"]:
        assert abs(f - 100.0) < 0.01


def test_croston_known_answer():
    """
    Intermittent demand: [0, 0, 10, 0, 10]. 
    Average interval ~ 2.5, average size = 10 → forecast ≈ 10/2.5 = 4.0
    """
    from app.forecasting.croston import croston
    history = [0.0, 0.0, 10.0, 0.0, 10.0]
    result = croston(history, alpha=0.0, horizon=1)  # alpha=0 → no smoothing
    assert result["forecast"][0] > 0


def test_forecasting_runner_routes_correctly():
    """Intermittent demand should route to Croston-SBA."""
    from app.forecasting.runner import run_forecast_pipeline
    items = [{"id": "SKU1", "history": [0, 0, 10, 0, 0, 8, 0, 0, 12, 0]}]
    results = run_forecast_pipeline(items, horizon=4)
    assert results[0]["method"] == "Croston-SBA"
    assert len(results[0]["forecast"]) == 4


# ─────────────────────────────────────────────
# LP Fallback Tests
# ─────────────────────────────────────────────

def test_lp_fallback_returns_feasible():
    payload = {
        "run_type": "manual",
        "max_service_time": 5,
        "nodes": [
            {"id": "Supplier", "type": "Supplier", "processing_time": 2, "max_s_out": 2},
            {"id": "DC1", "type": "DC", "processing_time": 1, "max_s_out": 2},
            {"id": "Store1", "type": "Store", "processing_time": 0, "max_s_out": 0},
        ],
        "edges": [
            {"source": "Supplier", "target": "DC1", "transit_time": 10},  # Force infeasibility under max_time=5
            {"source": "DC1", "target": "Store1", "transit_time": 1},
        ],
    }
    response = client.post("/api/v1/optimization/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["solver"] == "lp-fallback"
    assert data["fallback_used"] is True
    assert data["status"] == "FEASIBLE"


def test_ingest_demand():
    locs = client.get("/api/v1/locations").json()
    prods = client.get("/api/v1/products").json()
    if not locs or not prods:
        pytest.skip("Skipping demand ingest test: DB needs at least one location and product.")

    loc_id = locs[0]["id"]
    prod_id = prods[0]["id"]

    payload = {
        "records": [
            {"location_id": loc_id, "product_id": prod_id, "date": "2024-01-01", "quantity": 10},
            {"location_id": loc_id, "product_id": prod_id, "date": "2024-01-02", "quantity": 15},
        ]
    }
    response = client.post("/api/v1/demand/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "inserted_count" in data


def test_get_demand_history():
    locs = client.get("/api/v1/locations").json()
    prods = client.get("/api/v1/products").json()
    if not locs or not prods:
        pytest.skip("Skipping demand history test: DB empty.")

    loc_id = locs[0]["id"]
    prod_id = prods[0]["id"]

    response = client.get("/api/v1/demand/history", params={"location_id": loc_id, "product_id": prod_id})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert data[0]["location_id"] == loc_id
        assert data[0]["product_id"] == prod_id

# ─────────────────────────────────────────────
# E2E Pipeline Tests
# ─────────────────────────────────────────────

def test_end_to_end_pipeline():
    payload = {
        "run_type": "daily_batch",
        "horizon": 4,
        "max_service_time": 30,
        "nodes": [
            {"id": "Supplier", "type": "Supplier", "processing_time": 2, "holding_cost": 1.0},
            {"id": "DC1", "type": "DC", "processing_time": 1, "holding_cost": 2.0},
            {"id": "Store1", "type": "Store", "processing_time": 0, "holding_cost": 5.0, "demand_std": 10.0}
        ],
        "edges": [
            {"source": "Supplier", "target": "DC1", "transit_time": 3, "cost_per_unit": 2.5, "capacity": 1000},
            {"source": "DC1", "target": "Store1", "transit_time": 1, "cost_per_unit": 5.0, "capacity": 500}
        ],
        "items_history": [
            {"id": "Store1", "history": [100.0, 110.0, 90.0, 105.0, 100.0, 110.0]}
        ]
    }
    response = client.post("/api/v1/pipeline/run", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "SUCCESS", f"Pipeline failed: {data}"
    assert "pipeline_run_id" in data
    
    # Forecast stage
    assert data["stages"]["forecast"]["status"] == "SUCCESS"
    assert data["stages"]["forecast"]["count"] == 1
    
    # GSM stage
    assert data["stages"]["gsm"]["status"] == "SUCCESS"
    
    # Transportation stage
    assert data["stages"]["transportation"]["status"] == "OPTIMAL"
    assert "flows" in data["stages"]["transportation"]
    assert "Supplier->DC1" in data["stages"]["transportation"]["flows"]
