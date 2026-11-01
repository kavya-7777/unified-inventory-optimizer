"""Excel/CSV import, the results export, setup status and the demo-data loader."""
import io
from datetime import date

from openpyxl import Workbook, load_workbook

from app.models.inventory import (
    DemandHistory,
    InventorySnapshot,
    Lane,
    Location,
    LocationProductPolicy,
    Product,
)
from app.models.users import AuditEvent, DataImport

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def workbook(**sheets) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def upload(client, content: bytes, dry_run: bool, filename: str = "data.xlsx"):
    return client.post("/api/v1/imports", params={"dry_run": dry_run},
                       files={"file": (filename, content, XLSX)})


GOOD = dict(
    Locations=[("code*", "name*", "type*", "region"),
               ("ST2", "Store 2", "store", "Kerala")],
    Products=[("sku*", "name*", "category", "unit_cost"),
              ("SKU-1", "Renamed product", None, 99),
              ("SKU-2", "Second product", "Grocery", "1,250")],
    Lanes=[("from_code", "to_code", "transit_days", "cost_per_unit", "capacity"),
           ("DC1", "ST2", 1, 2.5, None)],
    Policies=[("location_code", "sku", "service_level", "min_service_time", "max_service_time"),
              ("ST2", "SKU-2", "97%", 0, 0),
              ("DC1", "SKU-2", 0.95, None, None)],
    Inventory=[("location_code", "sku", "on_hand", "on_order", "in_transit", "snapshot_date"),
               ("ST2", "SKU-2", 40, None, 5, "15/01/2026")],
    Demand=[("location_code", "sku", "date", "quantity"),
            ("ST2", "SKU-2", date(2026, 1, 1), 12),
            ("ST2", "SKU-2", "2026-01-02", 9)],
)


def test_dry_run_previews_without_saving(planner_client, db_session):
    res = upload(planner_client, workbook(**GOOD), dry_run=True)
    assert res.status_code == 200
    body = res.json()
    assert body["error_count"] == 0 and body["committed"] is False
    counts = {s["sheet"]: (s["created"], s["updated"]) for s in body["sheets"]}
    assert counts == {"Locations": (1, 0), "Products": (1, 1), "Lanes": (1, 0),
                      "Policies": (2, 0), "Inventory": (1, 0), "Demand": (2, 0)}
    assert db_session.get(Location, "ST2") is None
    assert db_session.query(DataImport).count() == 0


def test_commit_writes_everything_and_records_history(planner_client, db_session):
    res = upload(planner_client, workbook(**GOOD), dry_run=False)
    body = res.json()
    assert body["committed"] is True and body["import_id"]

    assert db_session.get(Location, "ST2").type == "Store"
    assert db_session.get(Product, "P1").name == "Renamed product"
    sku2 = db_session.query(Product).filter_by(sku="SKU-2").one()
    assert sku2.unit_cost == 1250
    assert db_session.query(Lane).filter_by(source_id="DC1", target_id="ST2").one().capacity is None
    pol = db_session.query(LocationProductPolicy).filter_by(location_id="ST2").one()
    assert pol.service_level == 0.97 and pol.max_s_out == 0
    dc_pol = db_session.query(LocationProductPolicy).filter_by(location_id="DC1").one()
    assert (dc_pol.min_s_out, dc_pol.max_s_out) == (0, 30)  # defaults for blank cells
    snap = db_session.query(InventorySnapshot).one()
    assert (snap.on_hand, snap.on_order, snap.in_transit) == (40, 0, 5)
    assert snap.snapshot_date.date() == date(2026, 1, 15)
    assert db_session.query(DemandHistory).count() == 2

    history = planner_client.get("/api/v1/imports").json()
    assert history[0]["user_email"] == "planner@test.io"
    assert db_session.query(AuditEvent).filter_by(action="data.import").count() == 1


def test_reimport_updates_instead_of_duplicating(planner_client, db_session):
    upload(planner_client, workbook(**GOOD), dry_run=False)
    body = upload(planner_client, workbook(**GOOD), dry_run=False).json()
    assert all(s["created"] == 0 for s in body["sheets"])
    assert db_session.query(DemandHistory).count() == 2
    assert db_session.query(InventorySnapshot).count() == 1


def test_invalid_rows_are_reported_and_nothing_is_saved(planner_client, db_session):
    bad = dict(
        Locations=[("code", "name", "type"),
                   ("ST2", "Store 2", "Warehouse"),
                   ("ST3", None, "Store"),
                   ("ST4", "Store 4", "Store"),
                   ("st4", "Duplicate", "Store")],
        Policies=[("location_code", "sku", "service_level", "min_service_time",
                   "max_service_time"),
                  ("ST4", "NOPE", 0.9, 0, 0),
                  ("ST4", "SKU-1", 0.2, 5, 1)],
        Demand=[("location_code", "sku", "date", "quantity"),
                ("DC1", "SKU-1", "2026-01-01", 5),
                ("ST4", "SKU-1", "yesterday", -1)],
        Notes=[("anything",)],
    )
    body = upload(planner_client, workbook(**bad), dry_run=False).json()
    assert body["committed"] is False
    found = {(e["sheet"], e["row"], e["column"]) for e in body["errors"]}
    assert ("Locations", 2, "type") in found          # not Supplier/DC/Store
    assert ("Locations", 3, "name") in found          # required
    assert ("Locations", 5, None) in found            # duplicate code (case-insensitive)
    assert ("Policies", 2, "sku") in found            # unknown SKU
    assert ("Policies", 3, "service_level") in found  # below 0.5
    assert ("Demand", 2, "location_code") in found    # demand only at stores
    assert ("Demand", 3, "date") in found
    assert ("Demand", 3, "quantity") in found
    assert any("Notes" in w for w in body["warnings"])
    assert db_session.get(Location, "ST4") is None
    assert db_session.query(DataImport).count() == 0


def test_missing_required_column(planner_client):
    content = workbook(Products=[("sku", "category"), ("X", "Y")])
    body = upload(planner_client, content, dry_run=True).json()
    assert body["errors"][0]["message"] == "Missing required column(s): name"


def test_unreadable_files_get_clear_errors(planner_client):
    res = upload(planner_client, b"not a zip", dry_run=True)
    assert res.status_code == 422 and "readable" in res.json()["detail"]
    res = upload(planner_client, b"x", dry_run=True, filename="data.pdf")
    assert res.status_code == 422
    res = upload(planner_client, workbook(Sheet1=[("a",)]), dry_run=True)
    assert res.status_code == 422 and "No recognised sheets" in res.json()["detail"]
    res = upload(planner_client, workbook(Products=[("sku", "name")]), dry_run=True)
    assert res.status_code == 422 and "no data rows" in res.json()["detail"]


def test_file_size_limit(planner_client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "IMPORT_MAX_BYTES", 100)
    assert upload(planner_client, workbook(**GOOD), dry_run=True).status_code == 413


def test_csv_import_picks_sheet_from_file_name(planner_client, db_session):
    csv = "location_code,sku,date,quantity\nST1,SKU-1,02/01/2026,7\n".encode()
    res = planner_client.post("/api/v1/imports", params={"dry_run": False},
                              files={"file": ("demand.csv", csv, "text/csv")})
    assert res.json()["committed"] is True
    row = db_session.query(DemandHistory).one()
    assert (row.location_id, row.quantity, row.date.date()) == ("ST1", 7, date(2026, 1, 2))


def test_viewer_cannot_import(viewer_client):
    assert upload(viewer_client, workbook(**GOOD), dry_run=True).status_code == 403
    assert viewer_client.get("/api/v1/imports").status_code == 403


def test_template_round_trips(planner_client):
    res = planner_client.get("/api/v1/imports/template")
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(res.content))
    assert wb.sheetnames == ["Instructions", "Locations", "Products", "Lanes", "Policies",
                             "Inventory", "Demand"]
    # The blank template's example rows form a valid little network.
    body = upload(planner_client, res.content, dry_run=True).json()
    assert body["error_count"] == 0, body["errors"]

    current = planner_client.get("/api/v1/imports/template", params={"include_data": True})
    rows = list(load_workbook(io.BytesIO(current.content))["Locations"].values)
    assert ("DC1", "Distribution Center 1", "DC", None) in rows
    body = upload(planner_client, current.content, dry_run=True).json()
    assert body["error_count"] == 0
    assert {s["sheet"]: s["created"] for s in body["sheets"]} == {"Locations": 0, "Products": 0}


def test_results_export(client, viewer_client):
    client.post("/api/v1/optimization/run", json={})
    res = viewer_client.get("/api/v1/exports/results")
    assert res.status_code == 200
    assert res.headers["content-type"] == XLSX
    wb = load_workbook(io.BytesIO(res.content))
    assert wb.sheetnames == ["Summary", "Targets", "Inventory positions", "Transport plan",
                             "Open alerts"]
    assert wb["Summary"]["B4"].value == "viewer@test.io"


def test_setup_status_and_demo_data(client, db_session):
    status = client.get("/api/v1/setup/status").json()
    assert status["has_data"] is False and status["locations"] == 3

    res = client.post("/api/v1/admin/demo-data", json={"reset": True})
    assert res.status_code == 200
    assert res.json()["locations"] == 28
    status = client.get("/api/v1/setup/status").json()
    assert status["has_data"] is True
    assert status["locations"] == 28  # the reset removed the fixture locations
    assert status["demand_rows"] > 0
    # Users survive a reset.
    assert len(client.get("/api/v1/users").json()) == 3
    assert db_session.query(AuditEvent).filter_by(action="data.demo_load").count() == 1
