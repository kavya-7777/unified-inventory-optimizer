"""Repository: Data access layer for demand history."""
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import func, select
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.orm import Session

from app.models.inventory import DemandHistory, Location, Product

BATCH_SIZE = 1000
UPSERT_BATCH_SIZE = 5000

Key = Tuple[str, str, datetime]



def _as_datetime(d) -> datetime:
    return d if isinstance(d, datetime) else datetime.combine(d, time.min)


class DemandRepository:
    def __init__(self, db: Session):
        self.db = db

    def _write_upserts(self, rows: List[dict]) -> None:
        """INSERT … that overwrites the quantity when (location, product, date) exists."""
        dialect = self.db.get_bind().dialect.name
        if dialect == "mysql":
            # MySQL 8 renders the upsert as "VALUES (…) AS new ON DUPLICATE KEY UPDATE", which
            # PyMySQL can't batch in executemany (it falls back to one round trip per row).
            # Explicit multi-row VALUES statements are about 5x faster.
            for i in range(0, len(rows), BATCH_SIZE):
                stmt = mysql.insert(DemandHistory).values(rows[i:i + BATCH_SIZE])
                self.db.execute(stmt.on_duplicate_key_update(quantity=stmt.inserted.quantity))
            return
        if dialect in ("postgresql", "sqlite"):
            module = postgresql if dialect == "postgresql" else sqlite
            pg_stmt = module.insert(DemandHistory)
            pg_stmt = pg_stmt.on_conflict_do_update(
                index_elements=["location_id", "product_id", "date"],
                set_={"quantity": pg_stmt.excluded.quantity},
            )
            # executemany lets SQLAlchemy batch the rows efficiently ("insertmanyvalues").
            for i in range(0, len(rows), UPSERT_BATCH_SIZE):
                self.db.execute(pg_stmt, rows[i:i + UPSERT_BATCH_SIZE])
            return
        raise NotImplementedError(f"Upsert not supported for dialect '{dialect}'")

    def existing_keys(self, keys: List[Key]) -> set:
        """
        Which keys already exist. Scans the bounding box (locations x products x date range)
        through the unique index rather than a row-value IN list, which databases plan
        poorly for thousands of keys; the box is then filtered down to the exact keys.
        """
        if not keys:
            return set()
        wanted = set(keys)
        cols = (DemandHistory.location_id, DemandHistory.product_id, DemandHistory.date)
        locs = sorted({k[0] for k in wanted})
        prods = sorted({k[1] for k in wanted})
        start = min(k[2] for k in wanted)
        end = max(k[2] for k in wanted)
        found: Set[Key] = set()
        for i in range(0, len(locs), 200):
            stmt = select(*cols).where(
                DemandHistory.location_id.in_(locs[i:i + 200]),
                DemandHistory.product_id.in_(prods),
                DemandHistory.date.between(start, end),
            )
            for row in self.db.execute(stmt):
                key = (row[0], row[1], row[2])
                if key in wanted:
                    found.add(key)
        return found

    def _unknown_ids(self, model, ids: set) -> set:
        known = set(self.db.scalars(select(model.id).where(model.id.in_(ids))))
        return ids - known

    def upsert_bulk(self, records: List[dict], commit: bool = True) -> dict:
        """
        Insert or update demand rows keyed on (location_id, product_id, date).
        Rows referencing unknown locations/products are ignored and reported.
        Duplicate keys within the payload resolve to the last occurrence.
        With commit=False the rows join the caller's transaction (no commit, no rollback).
        """
        if not records:
            return {"inserted_count": 0, "updated_count": 0, "ignored_count": 0, "errors": []}

        deduped: Dict[Key, dict] = {}
        for r in records:
            row = {**r, "date": _as_datetime(r["date"])}
            deduped[(row["location_id"], row["product_id"], row["date"])] = row

        bad_locs = self._unknown_ids(Location, {k[0] for k in deduped})
        bad_prods = self._unknown_ids(Product, {k[1] for k in deduped})
        errors = [f"Unknown location_id '{x}'" for x in sorted(bad_locs)]
        errors += [f"Unknown product_id '{x}'" for x in sorted(bad_prods)]

        valid = {k: v for k, v in deduped.items() if k[0] not in bad_locs and k[1] not in bad_prods}
        ignored = len(records) - len(valid)
        if not valid:
            return {"inserted_count": 0, "updated_count": 0, "ignored_count": ignored,
                    "errors": errors}

        keys = list(valid)
        existing = self.existing_keys(keys)
        rows = list(valid.values())

        try:
            self._write_upserts(rows)
            if commit:
                self.db.commit()
        except Exception:
            if commit:
                self.db.rollback()
            raise

        updated = sum(1 for k in keys if k in existing)
        return {
            "inserted_count": len(keys) - updated,
            "updated_count": updated,
            "ignored_count": ignored,
            "errors": errors,
        }

    def get_history(
        self,
        location_id: str,
        product_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[DemandHistory]:
        query = self.db.query(DemandHistory).filter(
            DemandHistory.location_id == location_id,
            DemandHistory.product_id == product_id,
        )
        if start_date:
            query = query.filter(DemandHistory.date >= _as_datetime(start_date))
        if end_date:
            query = query.filter(DemandHistory.date <= _as_datetime(end_date))
        return query.order_by(DemandHistory.date.asc()).all()

    def get_avg_demand_by_location(
        self,
        location_type: str = "Store",
        product_id: Optional[str] = None,
        days: int = 28,
    ) -> List[Tuple[str, str, float]]:
        """Average daily demand per (location_id, product_id) over the last `days` of history."""
        end = self.latest_date()
        if end is None:
            return []
        cutoff = end - timedelta(days=days - 1)
        query = (
            self.db.query(
                DemandHistory.location_id,
                DemandHistory.product_id,
                func.avg(DemandHistory.quantity),
            )
            .join(Location, DemandHistory.location_id == Location.id)
            .filter(Location.type == location_type, DemandHistory.date >= cutoff)
        )
        if product_id:
            query = query.filter(DemandHistory.product_id == product_id)
        rows = query.group_by(DemandHistory.location_id, DemandHistory.product_id).all()
        return [(loc, prod, float(avg or 0.0)) for loc, prod, avg in rows]

    def latest_date(self) -> Optional[datetime]:
        return self.db.query(func.max(DemandHistory.date)).scalar()

    def get_daily_series(
        self,
        history_days: int,
        product_ids: Optional[List[str]] = None,
        location_ids: Optional[List[str]] = None,
        end: Optional[datetime] = None,
    ) -> Tuple[List[datetime], Dict[Tuple[str, str], List[float]]]:
        """
        Dense daily demand series per (location, product) for the `history_days` days up to
        and including `end` (default: latest recorded date). Days without a record are 0.
        """
        end = end or self.latest_date()
        if end is None:
            return [], {}
        end = _as_datetime(end.date() if isinstance(end, datetime) else end)
        dates = [end - timedelta(days=offset) for offset in range(history_days - 1, -1, -1)]
        index = {d: i for i, d in enumerate(dates)}

        query = self.db.query(
            DemandHistory.location_id, DemandHistory.product_id,
            DemandHistory.date, DemandHistory.quantity,
        ).filter(DemandHistory.date >= dates[0], DemandHistory.date <= end)
        if product_ids:
            query = query.filter(DemandHistory.product_id.in_(product_ids))
        if location_ids:
            query = query.filter(DemandHistory.location_id.in_(location_ids))

        series: Dict[Tuple[str, str], List[float]] = {}
        for loc, prod, day, qty in query:
            pos = index.get(_as_datetime(day.date()))
            if pos is None:
                continue
            series.setdefault((loc, prod), [0.0] * history_days)[pos] += float(qty)
        return dates, series
