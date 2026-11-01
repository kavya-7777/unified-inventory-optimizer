"""Login, sessions, role-based access, user management and the activity log."""
import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import DEV_JWT_SECRET, Settings, settings
from app.core.security import JWT_ALGORITHM
from app.models.inventory import PipelineRun
from app.models.users import AuditEvent, User
from tests.conftest import PASSWORD


def login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# ── Login & sessions ─────────────────────────────────────────────────────────

def test_login_returns_token_and_user(anon_client):
    res = login(anon_client, "  Planner@Test.io ")
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == "planner@test.io"
    assert body["user"]["role"] == "planner"
    assert "password_hash" not in body["user"]
    me = anon_client.get("/api/v1/auth/me",
                         headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["id"] == "U-PLANNER"


def test_login_wrong_password_or_unknown_email_is_401(anon_client):
    assert login(anon_client, "planner@test.io", "nope").status_code == 401
    res = login(anon_client, "ghost@test.io")
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password"


def test_login_rate_limited_after_repeated_failures(anon_client):
    for _ in range(5):
        assert login(anon_client, "viewer@test.io", "wrong").status_code == 401
    res = login(anon_client, "viewer@test.io")  # even the right password is refused for now
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_deactivated_user_cannot_log_in_or_use_old_token(anon_client, viewer_client, db_session):
    db_session.get(User, "U-VIEWER").is_active = False
    db_session.commit()
    assert login(anon_client, "viewer@test.io").status_code == 403
    assert viewer_client.get("/api/v1/products").status_code == 401


def test_data_routes_require_login(anon_client):
    for path in ("/api/v1/products", "/api/v1/dashboard/summary", "/api/v1/runs",
                 "/api/v1/policies", "/api/v1/transportation/plan", "/api/v1/setup/status"):
        assert anon_client.get(path).status_code == 401, path
    assert anon_client.get("/health").status_code == 200


def test_expired_and_forged_tokens_rejected(anon_client):
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    expired = jwt.encode({"sub": "U-ADMIN", "exp": past}, settings.JWT_SECRET,
                         algorithm=JWT_ALGORITHM)
    res = anon_client.get("/api/v1/products", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()

    forged = jwt.encode({"sub": "U-ADMIN"}, "not-the-secret", algorithm=JWT_ALGORITHM)
    res = anon_client.get("/api/v1/products", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401


def test_change_password(planner_client, anon_client):
    res = planner_client.post("/api/v1/auth/change-password",
                              json={"current_password": "wrong", "new_password": "brand-new-pass"})
    assert res.status_code == 400
    res = planner_client.post("/api/v1/auth/change-password",
                              json={"current_password": PASSWORD, "new_password": "short"})
    assert res.status_code == 422
    res = planner_client.post("/api/v1/auth/change-password",
                              json={"current_password": PASSWORD, "new_password": "brand-new-pass"})
    assert res.status_code == 204
    assert login(anon_client, "planner@test.io").status_code == 401
    assert login(anon_client, "planner@test.io", "brand-new-pass").status_code == 200


# ── Roles ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/v1/optimization/run", {}),
    ("post", "/api/v1/network/run", {}),
    ("post", "/api/v1/pipeline/run", {}),
    ("post", "/api/v1/forecast/run", {"items": []}),
    ("post", "/api/v1/demand/ingest", {"records": []}),
    ("post", "/api/v1/alerts/1/resolve", None),
    ("patch", "/api/v1/policies/x", {"service_level": 0.9}),
])
def test_viewer_cannot_change_data(viewer_client, method, path, body):
    res = getattr(viewer_client, method)(path, json=body) if body is not None \
        else getattr(viewer_client, method)(path)
    assert res.status_code == 403


def test_viewer_can_read(viewer_client):
    for path in ("/api/v1/products", "/api/v1/dashboard/summary", "/api/v1/runs",
                 "/api/v1/alerts", "/api/v1/policies", "/api/v1/setup/status"):
        assert viewer_client.get(path).status_code == 200, path


def test_planner_runs_are_attributed_and_logged(planner_client, db_session):
    res = planner_client.post("/api/v1/optimization/run", json={})
    assert res.status_code == 200
    run_id = res.json()["pipeline_run_id"]
    assert db_session.get(PipelineRun, run_id).triggered_by == "planner@test.io"
    listed = planner_client.get("/api/v1/runs").json()
    assert listed[0]["triggered_by"] == "planner@test.io"
    event = db_session.query(AuditEvent).filter_by(action="pipeline.run").one()
    assert (event.user_email, event.entity_id) == ("planner@test.io", run_id)


def test_admin_only_routes(planner_client, client):
    for path in ("/api/v1/users", "/api/v1/audit"):
        assert planner_client.get(path).status_code == 403
        assert client.get(path).status_code == 200
    assert planner_client.post("/api/v1/admin/demo-data", json={}).status_code == 403


# ── User management ──────────────────────────────────────────────────────────

def test_admin_creates_user_who_can_then_log_in(client, anon_client):
    res = client.post("/api/v1/users", json={"email": "New.Person@Test.io", "name": " New Person ",
                                             "role": "planner", "password": "temporary-pass"})
    assert res.status_code == 201
    assert res.json()["email"] == "new.person@test.io"
    assert res.json()["name"] == "New Person"
    assert login(anon_client, "new.person@test.io", "temporary-pass").status_code == 200
    dup = client.post("/api/v1/users", json={"email": "new.person@test.io", "name": "X",
                                             "role": "viewer", "password": "temporary-pass"})
    assert dup.status_code == 409


@pytest.mark.parametrize("payload", [
    {"email": "not-an-email", "name": "X", "role": "viewer", "password": "long-enough"},
    {"email": "a@b.io", "name": "X", "role": "superuser", "password": "long-enough"},
    {"email": "a@b.io", "name": "X", "role": "viewer", "password": "short"},
    {"email": "a@b.io", "name": "   ", "role": "viewer", "password": "long-enough"},
])
def test_create_user_validation(client, payload):
    assert client.post("/api/v1/users", json=payload).status_code == 422


def test_admin_cannot_lock_themselves_out(client):
    res = client.patch("/api/v1/users/U-ADMIN", json={"role": "viewer"})
    assert res.status_code == 400
    res = client.patch("/api/v1/users/U-ADMIN", json={"is_active": False})
    assert res.status_code == 400


def test_admin_can_demote_another_admin(client, db_session):
    db_session.add(User(id="U-ADMIN2", email="admin2@test.io", name="Second", role="admin",
                        password_hash="x", is_active=True))
    db_session.commit()
    # Demoting the other admin is fine while one admin (the caller) remains.
    assert client.patch("/api/v1/users/U-ADMIN2", json={"role": "planner"}).status_code == 200


def test_admin_changes_role_and_resets_password(client, anon_client, db_session):
    res = client.patch("/api/v1/users/U-VIEWER", json={"role": "planner"})
    assert res.status_code == 200 and res.json()["role"] == "planner"
    assert client.post("/api/v1/users/U-VIEWER/reset-password",
                       json={"new_password": "reset-by-admin"}).status_code == 204
    assert login(anon_client, "viewer@test.io", "reset-by-admin").status_code == 200
    actions = [e.action for e in db_session.query(AuditEvent).order_by(AuditEvent.id)]
    assert actions == ["user.update", "user.reset_password"]


def test_audit_log_filters_by_action(client):
    client.post("/api/v1/optimization/run", json={})
    client.patch("/api/v1/users/U-VIEWER", json={"name": "Victoria"})
    events = client.get("/api/v1/audit", params={"action": "user."}).json()
    assert [e["action"] for e in events] == ["user.update"]
    assert len(client.get("/api/v1/audit").json()) == 2


# ── Config ───────────────────────────────────────────────────────────────────

def test_database_url_normalised_for_hosted_mysql():
    s = Settings(DATABASE_URL="mysql://u:p@host:3306/db", _env_file=None)
    assert s.DATABASE_URL == "mysql+pymysql://u:p@host:3306/db"
    assert s.DATABASE_SSL is False
    # Aiven-style URI: ssl-mode is stripped from the URL and turns TLS on.
    s = Settings(DATABASE_URL="mysql://u:p@host:12345/defaultdb?ssl-mode=REQUIRED", _env_file=None)
    assert s.DATABASE_URL == "mysql+pymysql://u:p@host:12345/defaultdb"
    assert s.DATABASE_SSL is True
    s = Settings(DATABASE_URL="mysql+pymysql://u:p@h/db?charset=utf8mb4&ssl_mode=DISABLED",
                 _env_file=None)
    assert s.DATABASE_URL == "mysql+pymysql://u:p@h/db?charset=utf8mb4"
    assert s.DATABASE_SSL is False


def test_mysql_engine_uses_tls_when_required():
    import ssl

    from app.db.session import ssl_context
    assert ssl_context(False, "") is None
    unverified = ssl_context(True, "")
    assert unverified.verify_mode == ssl.CERT_NONE
    # The provider's CA certificate, as a path or as pasted PEM text, enables verification.
    bundle = ssl.get_default_verify_paths().cafile or "/etc/ssl/certs/ca-certificates.crt"
    if not os.path.exists(bundle):
        pytest.skip("no system CA bundle to test with")
    with open(bundle) as f:
        pem = f.read()
    for ca in (bundle, pem):
        verified = ssl_context(False, ca)
        assert verified.verify_mode == ssl.CERT_REQUIRED and verified.check_hostname


def test_production_requires_real_jwt_secret():
    with pytest.raises(ValueError):
        Settings(APP_ENV="production", JWT_SECRET="", _env_file=None)
    with pytest.raises(ValueError):
        Settings(APP_ENV="production", JWT_SECRET=DEV_JWT_SECRET, _env_file=None)
    ok = Settings(APP_ENV="production", JWT_SECRET="x" * 40, _env_file=None)
    assert ok.JWT_SECRET == "x" * 40
    assert Settings(JWT_SECRET="", _env_file=None).JWT_SECRET == DEV_JWT_SECRET


def test_bootstrap_admin_created_only_when_no_users(db_session, monkeypatch):
    from app.services.users import ensure_bootstrap_admin
    monkeypatch.setattr(settings, "ADMIN_EMAIL", "first@test.io")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "first-admin-pass")
    assert ensure_bootstrap_admin(db_session) is None  # users already exist
    db_session.query(User).delete()
    db_session.commit()
    created = ensure_bootstrap_admin(db_session)
    assert created is not None and created.role == "admin"
