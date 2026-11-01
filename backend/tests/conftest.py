import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import create_access_token, hash_password, login_limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.deps import get_db, get_session_factory  # noqa: E402
from app.db.session import engine_options  # noqa: E402
from app.main import app  # noqa: E402
from app.models.inventory import Location, Product  # noqa: E402
from app.models.users import User  # noqa: E402

PASSWORD = "correct-horse-battery"
USERS = {
    "admin": User(id="U-ADMIN", email="admin@test.io", name="Ada Admin", role="admin"),
    "planner": User(id="U-PLANNER", email="planner@test.io", name="Pat Planner", role="planner"),
    "viewer": User(id="U-VIEWER", email="viewer@test.io", name="Vic Viewer", role="viewer"),
}
_PASSWORD_HASH = hash_password(PASSWORD)  # bcrypt is slow; hash once per session

# Fast in-memory SQLite by default. Set TEST_DATABASE_URL to run the same suite against a real
# (throwaway!) MySQL database, e.g. mysql+pymysql://uio:uio_password@mysql:3306/uio_test —
# every table in it is dropped and recreated.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

if TEST_DATABASE_URL:
    engine = create_engine(TEST_DATABASE_URL, **engine_options(TEST_DATABASE_URL))
else:
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
app.dependency_overrides[get_session_factory] = lambda: TestingSession


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _db(_schema):
    with TestingSession() as db:
        db.add_all([
            Location(id="SUP1", name="Supplier 1", type="Supplier"),
            Location(id="DC1", name="Distribution Center 1", type="DC"),
            Location(id="ST1", name="Store 1", type="Store"),
            Product(id="P1", name="Product 1", sku="SKU-1"),
        ])
        db.add_all(User(id=u.id, email=u.email, name=u.name, role=u.role,
                        password_hash=_PASSWORD_HASH, is_active=True) for u in USERS.values())
        db.commit()
    login_limiter.reset()
    yield
    # Empty every table, children first, so the next test starts clean.
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


def _client_for(role: str) -> TestClient:
    token = create_access_token(USERS[role])
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def client():
    """Signed in as an admin, so tests of the planning features aren't about permissions."""
    return _client_for("admin")


@pytest.fixture
def planner_client():
    return _client_for("planner")


@pytest.fixture
def viewer_client():
    return _client_for("viewer")


@pytest.fixture
def anon_client():
    return TestClient(app)


@pytest.fixture
def db_session():
    with TestingSession() as db:
        yield db
