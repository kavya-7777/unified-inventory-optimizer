from sqlalchemy import Column, String, Float, Integer, ForeignKey
from app.models.base import Base

class Location(Base):
    __tablename__ = "locations"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False) # e.g., 'DC', 'Store'

class Product(Base):
    __tablename__ = "products"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String)

class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(String, ForeignKey("locations.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    on_hand = Column(Float, default=0.0)
    version = Column(Integer, default=1) # Optimistic locking
