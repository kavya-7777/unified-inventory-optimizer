"""Repository: Data access layer for demand history."""
from datetime import date
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.models.inventory import DemandHistory


class DemandRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_bulk(self, records: List[dict]) -> dict:
        """
        Upsert demand history records using PostgreSQL ON CONFLICT DO UPDATE.
        Expects a list of dicts: {"location_id": "...", "product_id": "...", "date": "...", "quantity": ...}
        """
        if not records:
            return {"inserted_count": 0, "updated_count": 0, "ignored_count": 0, "errors": []}

        total_processed = 0
        batch_size = 1000
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            # PostgreSQL upsert (insert or update on conflict)
            stmt = insert(DemandHistory).values(batch)
            
            # On conflict (location_id, product_id, date), update the quantity
            update_stmt = stmt.on_conflict_do_update(
                index_elements=['location_id', 'product_id', 'date'],
                set_=dict(quantity=stmt.excluded.quantity)
            )
            
            result = self.db.execute(update_stmt)
            total_processed += result.rowcount

        self.db.commit()
        
        return {
            "inserted_count": result.rowcount,
            "updated_count": 0,  # Rowcount handles both for this driver mostly
            "ignored_count": 0,
            "errors": []
        }

    def get_history(self, location_id: str, product_id: str, start_date: date = None, end_date: date = None) -> List[DemandHistory]:
        query = self.db.query(DemandHistory).filter(
            DemandHistory.location_id == location_id,
            DemandHistory.product_id == product_id
        )
        if start_date:
            query = query.filter(DemandHistory.date >= start_date)
        if end_date:
            query = query.filter(DemandHistory.date <= end_date)
            
        return query.order_by(DemandHistory.date.asc()).all()
