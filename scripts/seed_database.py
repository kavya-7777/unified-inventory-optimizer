import json
import os
import sys

if os.path.exists('/app'):
    sys.path.insert(0, '/app')
else:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.db.session import SessionLocal
from app.models.inventory import Location, Product

def seed():
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'synthetic', 'generated_data.json')
    if not os.path.exists(data_path):
        print("No synthetic data found. Run make generate-data first.")
        return

    with open(data_path, 'r') as f:
        data = json.load(f)

    db = SessionLocal()
    try:
        # Simple upsert or add
        for loc in data.get("locations", []):
            existing = db.query(Location).filter(Location.id == loc["id"]).first()
            if not existing:
                db.add(Location(**loc))
        
        for prod in data.get("products", []):
            existing = db.query(Product).filter(Product.id == prod["id"]).first()
            if not existing:
                db.add(Product(**prod))
                
        db.commit()
        print("Database seeded successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
