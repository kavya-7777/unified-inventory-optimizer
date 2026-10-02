import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base  # noqa: E402
from app.db.deps import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.inventory import Location, Product  # noqa: E402

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _db():
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        db.add_all([
            Location(id="SUP1", name="Supplier 1", type="Supplier"),
            Location(id="DC1", name="Distribution Center 1", type="DC"),
            Location(id="ST1", name="Store 1", type="Store"),
            Product(id="P1", name="Product 1", sku="SKU-1"),
        ])
        db.commit()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    with TestingSession() as db:
        yield db
