"""
Excel / CSV data import.

One workbook can carry any of six sheets — Locations, Products, Lanes, Policies, Inventory,
Demand — each with a fixed set of columns. Rows are matched on business keys (location code,
SKU), never internal IDs. Every row is validated before anything is written; a commit applies
the whole file in one transaction, so either all of it lands or none of it does.
"""
import csv
import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.orm import Session

from app.core.security import CurrentUser
from app.models.base import utcnow
from app.models.inventory import (
    InventorySnapshot,
    Lane,
    Location,
    LocationProductPolicy,
    Product,
)
from app.models.users import DataImport
from app.repositories.demand import DemandRepository
from app.services.users import record_event

LOCATION_TYPES = {"supplier": "Supplier", "dc": "DC", "store": "Store"}
MAX_ROWS = 250_000
MAX_ERRORS = 200


class ImportFileError(ValueError):
    """The upload can't be read at all (wrong format, corrupt, too large)."""


# ── Column specs ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Column:
    name: str
    kind: str              # text | number | integer | date | location_type | fraction
    required: bool = False
    help: str = ""
    min: Optional[float] = None
    max: Optional[float] = None
    strict_min: bool = False


@dataclass(frozen=True)
class SheetSpec:
    name: str
    description: str
    columns: Tuple[Column, ...]
    example: Tuple[Tuple[Any, ...], ...]

    @property
    def required(self) -> Set[str]:
        return {c.name for c in self.columns if c.required}


SHEETS: Tuple[SheetSpec, ...] = (
    SheetSpec(
        "Locations", "Suppliers, distribution centres (DC) and stores.",
        (
            Column("code", "text", True, "Your unique code for the location, e.g. ST-CHN-01."),
            Column("name", "text", True, "Display name."),
            Column("type", "location_type", True, "Supplier, DC or Store."),
            Column("region", "text", help="State or region (optional)."),
        ),
        (("SUP-EX1", "Example Supplier", "Supplier", "Tamil Nadu"),
         ("DC-EX1", "Example DC", "DC", "Tamil Nadu"),
         ("ST-EX1", "Example Store", "Store", "Tamil Nadu")),
    ),
    SheetSpec(
        "Products", "The SKU catalogue.",
        (
            Column("sku", "text", True, "Unique SKU code."),
            Column("name", "text", True, "Product name."),
            Column("category", "text", help="Category (optional)."),
            Column("unit_cost", "number", help="Cost per unit in rupees; used for inventory value.",
                   min=0),
        ),
        (("EX-001", "Example Product", "Grocery", 120),),
    ),
    SheetSpec(
        "Lanes", "Transport links: goods flow from_code → to_code.",
        (
            Column("from_code", "text", True, "Location code the goods leave from."),
            Column("to_code", "text", True, "Location code the goods arrive at."),
            Column("transit_days", "integer", True, "Days in transit.", min=0, max=365),
            Column("cost_per_unit", "number", help="Freight cost per unit.", min=0),
            Column("capacity", "number", help="Max units per day; blank = unlimited.", min=0,
                   strict_min=True),
        ),
        (("SUP-EX1", "DC-EX1", 2, 3.5, 5000), ("DC-EX1", "ST-EX1", 1, 2.0, 800)),
    ),
    SheetSpec(
        "Policies", "Which locations stock which SKUs, and their inventory settings. "
                    "A location only carries a SKU if it has a policy row for it.",
        (
            Column("location_code", "text", True, "Location code."),
            Column("sku", "text", True, "SKU."),
            Column("service_level", "fraction",
                   help="Target service level, e.g. 0.95 or 95%. Default 0.95.", min=0.5,
                   max=0.999),
            Column("min_service_time", "integer", help="Min days promised downstream. Default 0.",
                   min=0),
            Column("max_service_time", "integer", help="Max days promised downstream. Default 30.",
                   min=0),
            Column("holding_cost", "number", help="Cost to hold one unit for a day.", min=0),
            Column("ordering_cost", "number", help="Fixed cost per replenishment order.", min=0),
            Column("review_period", "integer", help="Days between stock reviews. Default 1.",
                   min=1),
            Column("processing_time", "integer", help="Days to process an order. Default 1.",
                   min=0, max=90),
        ),
        (("SUP-EX1", "EX-001", 0.9, 0, 14, 0.08, 2500, 7, 3),
         ("DC-EX1", "EX-001", 0.95, 0, 7, 0.08, 1200, 3, 1),
         ("ST-EX1", "EX-001", 0.97, 0, 0, 0.08, 400, 1, 0)),
    ),
    SheetSpec(
        "Inventory", "Current stock per location and SKU.",
        (
            Column("location_code", "text", True, "Location code."),
            Column("sku", "text", True, "SKU."),
            Column("on_hand", "number", True, "Units physically in stock.", min=0),
            Column("on_order", "number", help="Units ordered, not yet shipped.", min=0),
            Column("in_transit", "number", help="Units on the way.", min=0),
            Column("snapshot_date", "date", help="Stock-count date. Default today."),
        ),
        (("DC-EX1", "EX-001", 900, 200, 0, None), ("ST-EX1", "EX-001", 60, 0, 40, None)),
    ),
    SheetSpec(
        "Demand", "Daily sales history per store and SKU (one row per day). "
                  "Forecasts need at least 4 weeks of history.",
        (
            Column("location_code", "text", True, "Store code."),
            Column("sku", "text", True, "SKU."),
            Column("date", "date", True, "Sales date (YYYY-MM-DD or DD/MM/YYYY)."),
            Column("quantity", "number", True, "Units sold that day.", min=0),
        ),
        (("ST-EX1", "EX-001", date(2026, 1, 1), 12), ("ST-EX1", "EX-001", date(2026, 1, 2), 9)),
    ),
)
SPEC_BY_KEY = {s.name.lower(): s for s in SHEETS}


def _norm_header(value: Any) -> str:
    text = re.sub(r"\(.*?\)", "", str(value or "")).replace("*", "")
    return re.sub(r"[\s\-]+", "_", text.strip().lower())


# ── Reading the file ─────────────────────────────────────────────────────────

RawSheet = Tuple[str, List[str], Iterator[Tuple[int, Tuple[Any, ...]]]]


def _xlsx_sheets(content: bytes) -> List[RawSheet]:
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as e:
        raise ImportFileError("This file isn't a readable .xlsx workbook.") from e
    sheets: List[RawSheet] = []
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None)
        if header is None:
            continue
        sheets.append((ws.title, [_norm_header(h) for h in header],
                       ((i, r) for i, r in enumerate(rows, start=2))))
    return sheets


def _csv_sheet(content: bytes, filename: str) -> List[RawSheet]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if header is None:
        return []
    headers = [_norm_header(h) for h in header]
    # A CSV holds one sheet: pick it from the file name, else from the columns present.
    stem = _norm_header(re.sub(r"\.csv$", "", filename, flags=re.I))
    spec = next((s for s in SHEETS if s.name.lower() in stem), None)
    if spec is None:
        matches = [s for s in SHEETS if s.required <= set(headers)]
        spec = max(matches, key=lambda s: len(s.required)) if matches else None
    if spec is None:
        raise ImportFileError("Couldn't tell which sheet this CSV is. Name the file after the "
                              "sheet (e.g. demand.csv) and use the template's column headers.")
    return [(spec.name, headers, ((i, tuple(r)) for i, r in enumerate(reader, start=2)))]


# ── Validation ───────────────────────────────────────────────────────────────

@dataclass
class ImportReport:
    errors: List[Dict[str, Any]] = field(default_factory=list)
    error_count: int = 0
    warnings: List[str] = field(default_factory=list)
    rows: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def error(self, sheet: str, row: Optional[int], column: Optional[str], message: str) -> None:
        self.error_count += 1
        if len(self.errors) < MAX_ERRORS:
            self.errors.append({"sheet": sheet, "row": row, "column": column,
                                "message": message})


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _coerce(col: Column, v: Any) -> Any:
    """Returns the typed value or raises ValueError with a user-facing message."""
    if col.kind == "text":
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        out = str(v).strip()
        if len(out) > 255:
            raise ValueError("is longer than 255 characters")
        return out
    if col.kind == "location_type":
        key = str(v).strip().lower()
        if key not in LOCATION_TYPES:
            raise ValueError(f"must be Supplier, DC or Store (got '{v}')")
        return LOCATION_TYPES[key]
    if col.kind == "date":
        if isinstance(v, datetime):
            return datetime.combine(v.date(), time.min)
        if isinstance(v, date):
            return datetime.combine(v, time.min)
        text = str(v).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        raise ValueError(f"'{v}' isn't a date (use YYYY-MM-DD or DD/MM/YYYY)")

    # numeric kinds
    if isinstance(v, bool):
        raise ValueError(f"must be a number (got '{v}')")
    text = str(v).strip().replace(",", "") if isinstance(v, str) else v
    is_percent = isinstance(text, str) and text.endswith("%")
    if is_percent:
        text = text[:-1]
    try:
        num = float(text)
    except (TypeError, ValueError):
        raise ValueError(f"must be a number (got '{v}')") from None
    if num != num or num in (float("inf"), float("-inf")):
        raise ValueError("must be a finite number")
    if col.kind == "fraction" and (is_percent or 1 < num <= 100):
        num = num / 100
    if col.kind == "integer":
        if not num.is_integer():
            raise ValueError(f"must be a whole number (got '{v}')")
        num = int(num)
    if col.min is not None and (num <= col.min if col.strict_min else num < col.min):
        raise ValueError(f"must be {'greater than' if col.strict_min else 'at least'} "
                         f"{col.min:g}")
    if col.max is not None and num > col.max:
        raise ValueError(f"must be at most {col.max:g}")
    return num


def _read_sheet(spec: SheetSpec, title: str, headers: List[str],
                rows: Iterator[Tuple[int, Tuple[Any, ...]]], report: ImportReport) -> None:
    known = {c.name for c in spec.columns}
    missing = spec.required - set(headers)
    if missing:
        report.error(spec.name, 1, None,
                     f"Missing required column(s): {', '.join(sorted(missing))}")
        return
    extra = [h for h in headers if h and h not in known]
    if extra:
        report.warnings.append(f"{spec.name}: ignored unknown column(s) {', '.join(extra)}")

    index = {h: i for i, h in enumerate(headers) if h in known}
    out = report.rows.setdefault(spec.name, [])
    for row_no, raw in rows:
        values = {name: raw[i] if i < len(raw) else None for name, i in index.items()}
        if all(_blank(v) for v in values.values()):
            continue
        if sum(len(r) for r in report.rows.values()) >= MAX_ROWS:
            raise ImportFileError(f"The file has more than {MAX_ROWS:,} rows. Split it into "
                                  "smaller files.")
        record: Dict[str, Any] = {"_row": row_no}
        ok = True
        for col in spec.columns:
            v = values.get(col.name)
            if _blank(v):
                if col.required:
                    report.error(spec.name, row_no, col.name, "is required")
                    ok = False
                record[col.name] = None
                continue
            try:
                record[col.name] = _coerce(col, v)
            except ValueError as e:
                report.error(spec.name, row_no, col.name, str(e))
                ok = False
        if ok:
            out.append(record)


def parse_upload(content: bytes, filename: str) -> ImportReport:
    name = (filename or "").lower()
    if name.endswith(".xlsx"):
        raw_sheets = _xlsx_sheets(content)
    elif name.endswith(".csv"):
        raw_sheets = _csv_sheet(content, filename)
    else:
        raise ImportFileError("Upload an .xlsx workbook (or a .csv for a single sheet).")

    report = ImportReport()
    seen = set()
    for title, headers, rows in raw_sheets:
        key = _norm_header(title).replace("_", "")
        spec = SPEC_BY_KEY.get(key)
        if spec is None:
            if key != "instructions":
                report.warnings.append(f"Ignored sheet '{title}' (not one of "
                                       f"{', '.join(s.name for s in SHEETS)}).")
            continue
        if spec.name in seen:
            report.warnings.append(f"Ignored a second '{spec.name}' sheet.")
            continue
        seen.add(spec.name)
        _read_sheet(spec, title, headers, rows, report)

    if not seen:
        raise ImportFileError("No recognised sheets. Use the template: sheets named "
                              + ", ".join(s.name for s in SHEETS) + ".")
    if not any(report.rows.values()) and not report.error_count:
        raise ImportFileError("The file has no data rows.")
    return report


# ── Cross-row checks and writing ─────────────────────────────────────────────

def _dupes(report: ImportReport, sheet: str, key: Callable[[Dict[str, Any]], Any],
           label: Callable[[Dict[str, Any]], str]) -> List[Dict[str, Any]]:
    """Reports duplicate keys within a sheet; returns the rows to keep (first occurrences)."""
    first: Dict[Any, int] = {}
    keep = []
    for r in report.rows.get(sheet, []):
        k = key(r)
        if k in first:
            report.error(sheet, r["_row"], None,
                         f"Duplicate {label(r)} (already on row {first[k]})")
            continue
        first[k] = r["_row"]
        keep.append(r)
    return keep


def _check_and_plan(db: Session, report: ImportReport) -> Dict[str, Any]:
    """Validates references and works out what each row would create or update."""
    locs = _dupes(report, "Locations", lambda r: r["code"].lower(), lambda r: f"code {r['code']}")
    prods = _dupes(report, "Products", lambda r: r["sku"].lower(), lambda r: f"SKU {r['sku']}")
    lanes = _dupes(report, "Lanes", lambda r: (r["from_code"].lower(), r["to_code"].lower()),
                   lambda r: f"lane {r['from_code']} → {r['to_code']}")
    pols = _dupes(report, "Policies", lambda r: (r["location_code"].lower(), r["sku"].lower()),
                  lambda r: f"policy {r['location_code']} / {r['sku']}")
    invs = _dupes(report, "Inventory",
                  lambda r: (r["location_code"].lower(), r["sku"].lower(), r["snapshot_date"]),
                  lambda r: f"stock row {r['location_code']} / {r['sku']}")
    dems = _dupes(report, "Demand",
                  lambda r: (r["location_code"].lower(), r["sku"].lower(), r["date"]),
                  lambda r: f"demand {r['location_code']} / {r['sku']} on {r['date']:%Y-%m-%d}")

    # Known locations by code (case-insensitive) and products by SKU.
    db_locs = {loc.id.lower(): loc for loc in db.query(Location)}
    db_prods = {p.sku.lower(): p for p in db.query(Product) if p.sku}
    loc_types = {k: v.type for k, v in db_locs.items()}
    loc_types.update({r["code"].lower(): r["type"] for r in locs})
    loc_ids = {k: v.id for k, v in db_locs.items()}
    loc_ids.update({r["code"].lower(): db_locs[r["code"].lower()].id
                    if r["code"].lower() in db_locs else r["code"] for r in locs})
    known_skus = set(db_prods) | {r["sku"].lower() for r in prods}

    def check_refs(sheet: str, rows: List[Dict[str, Any]], loc_cols: Tuple[str, ...],
                   need_type: Optional[str] = None) -> List[Dict[str, Any]]:
        good = []
        for r in rows:
            ok = True
            for col in loc_cols:
                code = r[col].lower()
                if code not in loc_types:
                    report.error(sheet, r["_row"], col,
                                 f"Unknown location code '{r[col]}' (add it to Locations)")
                    ok = False
                elif need_type and loc_types[code] != need_type:
                    report.error(sheet, r["_row"], col,
                                 f"'{r[col]}' is a {loc_types[code]}; demand is recorded "
                                 f"at stores")
                    ok = False
            if "sku" in r and r["sku"].lower() not in known_skus:
                report.error(sheet, r["_row"], "sku",
                             f"Unknown SKU '{r['sku']}' (add it to Products)")
                ok = False
            if ok:
                good.append(r)
        return good

    lanes = check_refs("Lanes", lanes, ("from_code", "to_code"))
    good_lanes = []
    for r in lanes:
        if r["from_code"].lower() == r["to_code"].lower():
            report.error("Lanes", r["_row"], "to_code", "A lane can't start and end at the "
                                                         "same location")
        elif loc_types[r["to_code"].lower()] == "Supplier":
            report.error("Lanes", r["_row"], "to_code", "Suppliers can't receive goods")
        else:
            good_lanes.append(r)
    pols = check_refs("Policies", pols, ("location_code",))
    good_pols = []
    for r in pols:
        lo, hi = r["min_service_time"], r["max_service_time"]
        if lo is not None and hi is not None and lo > hi:
            report.error("Policies", r["_row"], "min_service_time",
                         "min_service_time can't exceed max_service_time")
        else:
            good_pols.append(r)
    invs = check_refs("Inventory", invs, ("location_code",))
    dems = check_refs("Demand", dems, ("location_code",), need_type="Store")

    return {"locs": locs, "prods": prods, "lanes": good_lanes, "pols": good_pols,
            "invs": invs, "dems": dems, "db_locs": db_locs, "db_prods": db_prods,
            "loc_ids": loc_ids}


def _set_fields(obj: Any, values: Dict[str, Any]) -> None:
    """Blank cells leave existing values alone."""
    for attr, v in values.items():
        if v is not None:
            setattr(obj, attr, v)


def _apply(db: Session, plan: Dict[str, Any], today: datetime) -> Dict[str, Dict[str, int]]:
    """Stages every change in the session (no commit). Returns created/updated per sheet."""
    counts: Dict[str, Dict[str, int]] = {}

    def tally(sheet: str, created: bool) -> None:
        c = counts.setdefault(sheet, {"rows": 0, "created": 0, "updated": 0})
        c["rows"] += 1
        c["created" if created else "updated"] += 1

    db_locs, db_prods, loc_ids = plan["db_locs"], plan["db_prods"], plan["loc_ids"]
    for r in plan["locs"]:
        loc = db_locs.get(r["code"].lower())
        if loc is None:
            loc = Location(id=r["code"], name=r["name"], type=r["type"], region=r["region"])
            db.add(loc)
            db_locs[r["code"].lower()] = loc
            tally("Locations", True)
        else:
            _set_fields(loc, {"name": r["name"], "type": r["type"], "region": r["region"]})
            tally("Locations", False)

    for r in plan["prods"]:
        prod = db_prods.get(r["sku"].lower())
        if prod is None:
            new_id = r["sku"] if db.get(Product, r["sku"]) is None else str(uuid.uuid4())
            prod = Product(id=new_id, sku=r["sku"], name=r["name"], category=r["category"],
                           unit_cost=r["unit_cost"] or 0.0)
            db.add(prod)
            db_prods[r["sku"].lower()] = prod
            tally("Products", True)
        else:
            _set_fields(prod, {"name": r["name"], "category": r["category"],
                               "unit_cost": r["unit_cost"]})
            tally("Products", False)
    db.flush()

    def lid(code: str) -> str:
        return loc_ids[code.lower()]

    def pid(sku: str) -> str:
        return db_prods[sku.lower()].id

    existing_lanes = {(lane.source_id, lane.target_id): lane for lane in db.query(Lane)}
    for r in plan["lanes"]:
        key = (lid(r["from_code"]), lid(r["to_code"]))
        lane = existing_lanes.get(key)
        if lane is None:
            lane = Lane(source_id=key[0], target_id=key[1], transit_time=r["transit_days"],
                        cost_per_unit=r["cost_per_unit"] or 0.0, capacity=r["capacity"])
            db.add(lane)
            existing_lanes[key] = lane
            tally("Lanes", True)
        else:
            _set_fields(lane, {"transit_time": r["transit_days"],
                               "cost_per_unit": r["cost_per_unit"], "capacity": r["capacity"]})
            tally("Lanes", False)

    existing_pols = {(p.location_id, p.product_id): p for p in db.query(LocationProductPolicy)}
    for r in plan["pols"]:
        key = (lid(r["location_code"]), pid(r["sku"]))
        values = {"service_level": r["service_level"], "min_s_out": r["min_service_time"],
                  "max_s_out": r["max_service_time"], "holding_cost": r["holding_cost"],
                  "ordering_cost": r["ordering_cost"], "review_period": r["review_period"],
                  "processing_time": r["processing_time"]}
        pol = existing_pols.get(key)
        if pol is None:
            pol = LocationProductPolicy(location_id=key[0], product_id=key[1])
            pol.service_level, pol.min_s_out, pol.max_s_out = 0.95, 0, 30
            pol.holding_cost, pol.ordering_cost = 1.0, 50.0
            pol.review_period, pol.processing_time = 1, 1
            _set_fields(pol, values)
            if pol.min_s_out > pol.max_s_out:
                pol.max_s_out = pol.min_s_out
            db.add(pol)
            existing_pols[key] = pol
            tally("Policies", True)
        else:
            _set_fields(pol, values)
            tally("Policies", False)

    if plan["invs"]:
        snaps = {(s.location_id, s.product_id, s.snapshot_date): s
                 for s in db.query(InventorySnapshot).filter(
                     InventorySnapshot.snapshot_date.in_(
                         list({r["snapshot_date"] or today for r in plan["invs"]})))}
        for r in plan["invs"]:
            snap_key: Tuple[str, str, datetime] = (
                lid(r["location_code"]), pid(r["sku"]), r["snapshot_date"] or today)
            values = {"on_hand": r["on_hand"], "on_order": r["on_order"] or 0.0,
                      "in_transit": r["in_transit"] or 0.0}
            snap = snaps.get(snap_key)
            if snap is None:
                snap = InventorySnapshot(location_id=snap_key[0], product_id=snap_key[1],
                                         snapshot_date=snap_key[2], **values)
                db.add(snap)
                snaps[snap_key] = snap
                tally("Inventory", True)
            else:
                _set_fields(snap, values)
                tally("Inventory", False)
        db.flush()

    if plan["dems"]:
        records = [{"location_id": lid(r["location_code"]), "product_id": pid(r["sku"]),
                    "date": r["date"], "quantity": r["quantity"]} for r in plan["dems"]]
        result = DemandRepository(db).upsert_bulk(records, commit=False)
        counts["Demand"] = {"rows": len(records), "created": result["inserted_count"],
                            "updated": result["updated_count"]}
    return counts


def _preview_counts(
    db: Session, plan: Dict[str, Any], today: datetime
) -> Dict[str, Dict[str, int]]:
    """Same numbers as _apply, computed by staging the changes and rolling them back."""
    try:
        return _apply(db, plan, today)
    finally:
        db.rollback()


SHEET_ORDER = [s.name for s in SHEETS]


def run_import(db: Session, content: bytes, filename: str, user: CurrentUser,
               dry_run: bool) -> Dict[str, Any]:
    report = parse_upload(content, filename)
    plan = _check_and_plan(db, report)
    today = datetime.combine(date.today(), time.min)

    result: Dict[str, Any] = {
        "filename": filename,
        "dry_run": dry_run,
        "committed": False,
        "import_id": None,
        "sheets": [],
        "errors": report.errors,
        "error_count": report.error_count,
        "warnings": report.warnings,
    }
    if report.error_count:
        return result

    if dry_run:
        counts = _preview_counts(db, plan, today)
    else:
        try:
            counts = _apply(db, plan, today)
            entry = DataImport(filename=filename[:255], user_email=user.email,
                               summary=counts, created_at=utcnow())
            db.add(entry)
            db.flush()
            record_event(db, user, "data.import", "data_import", entry.id,
                         {"filename": filename, "sheets": counts}, commit=False)
            db.commit()
        except Exception:
            db.rollback()
            raise
        result["committed"] = True
        result["import_id"] = entry.id

    result["sheets"] = [{"sheet": name, **counts[name]} for name in SHEET_ORDER if name in counts]
    return result


# ── Template / current-data workbook ─────────────────────────────────────────

HEADER_FILL = PatternFill("solid", fgColor="4F46E5")
EXAMPLE_FONT = Font(italic=True, color="808080")


def _current_rows(db: Session, sheet: str) -> List[Tuple[Any, ...]]:
    locs = {loc.id: loc for loc in db.query(Location)}
    prods = {p.id: p for p in db.query(Product)}
    if sheet == "Locations":
        return [(loc.id, loc.name, loc.type, loc.region)
                for loc in sorted(locs.values(), key=lambda x: (x.type, x.id))]
    if sheet == "Products":
        return [(p.sku or p.id, p.name, p.category, p.unit_cost)
                for p in sorted(prods.values(), key=lambda x: x.sku or x.id)]
    if sheet == "Lanes":
        return [(lane.source_id, lane.target_id, lane.transit_time, lane.cost_per_unit,
                 lane.capacity) for lane in db.query(Lane).order_by(Lane.source_id,
                                                                    Lane.target_id)]
    if sheet == "Policies":
        rows = db.query(LocationProductPolicy).order_by(LocationProductPolicy.location_id,
                                                       LocationProductPolicy.product_id)
        return [(p.location_id, prods[p.product_id].sku or p.product_id, p.service_level,
                 p.min_s_out, p.max_s_out, p.holding_cost, p.ordering_cost, p.review_period,
                 p.processing_time) for p in rows if p.product_id in prods]
    if sheet == "Inventory":
        from app.repositories.inventory import InventoryRepository
        snaps = InventoryRepository(db).get_all_latest_snapshots()
        return [(s.location_id, prods[s.product_id].sku or s.product_id, s.on_hand, s.on_order,
                 s.in_transit, s.snapshot_date.date() if s.snapshot_date else None)
                for s in sorted(snaps, key=lambda s: (s.location_id, s.product_id))
                if s.product_id in prods]
    return []  # Demand history is too large to round-trip through a workbook


def build_template(db: Optional[Session] = None) -> bytes:
    """
    The import template. With a session, the sheets are pre-filled with the current data
    (except demand history) so it can be edited and uploaded again.
    """
    wb = Workbook()
    guide = wb.active
    guide.title = "Instructions"
    lines: List[Tuple[Any, ...]] = [
        ("Unified Inventory Optimizer — data import template",),
        (),
        ("How it works",),
        ("1. Fill in only the sheets you need; delete or leave out the others.",),
        ("2. Keep the header row as it is. Columns marked * are required.",),
        ("3. Rows are matched by location code and SKU: existing rows are updated, "
         "new ones are added. Blank optional cells keep the current value.",),
        ("4. Upload the file on the Data Import page. You'll see every problem before "
         "anything is saved, and nothing is saved unless the whole file is valid.",),
        ("5. After importing, run the network pipeline to refresh forecasts and targets.",),
    ]
    if db is None:
        lines.append(("Grey rows are examples: replace or delete them before uploading.",))
    lines.append(())
    for spec in SHEETS:
        lines.append((spec.name, spec.description))
        for col in spec.columns:
            lines.append(("", col.name + (" *" if col.required else ""), col.help))
        lines.append(())
    for line in lines:
        guide.append(line)
    guide["A1"].font = Font(bold=True, size=14)
    guide["A3"].font = Font(bold=True)
    for row in guide.iter_rows(min_row=10):
        if row[0].value:
            row[0].font = Font(bold=True)
    guide.column_dimensions["A"].width = 18
    guide.column_dimensions["B"].width = 22
    guide.column_dimensions["C"].width = 90

    for spec in SHEETS:
        ws = wb.create_sheet(spec.name)
        ws.append([c.name + ("*" if c.required else "") for c in spec.columns])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center")
        rows = _current_rows(db, spec.name) if db is not None else []
        if rows:
            for row in rows:
                ws.append(list(row))
        elif db is None:
            for example in spec.example:
                ws.append(list(example))
                for cell in ws[ws.max_row]:
                    cell.font = EXAMPLE_FONT
        for i, col in enumerate(spec.columns, start=1):
            ws.column_dimensions[get_column_letter(i)].width = max(14, len(col.name) + 4)
            letter = get_column_letter(i)
            if col.kind == "date":
                for cell in ws[letter][1:]:
                    cell.number_format = "yyyy-mm-dd"
            if col.kind == "location_type":
                dv = DataValidation(type="list", formula1='"Supplier,DC,Store"',
                                    allow_blank=False)
                dv.add(f"{letter}2:{letter}5000")
                ws.add_data_validation(dv)
        ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
