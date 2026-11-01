import ssl
import tempfile
from typing import Any, Dict, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _ca_file(value: str) -> str:
    """DATABASE_SSL_CA may hold the certificate itself (handy on Render) or a path to it."""
    if "-----BEGIN" not in value:
        return value
    handle = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
    handle.write(value.replace("\\n", "\n"))
    handle.close()
    return handle.name


def ssl_context(enabled: bool, ca: str) -> Optional[ssl.SSLContext]:
    if not enabled and not ca:
        return None
    if ca:
        # Verify the server against the provider's CA certificate.
        return ssl.create_default_context(cafile=_ca_file(ca))
    # Encrypted but unverified, matching MySQL's ssl-mode=REQUIRED.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def engine_options(url: str) -> Dict[str, Any]:
    """Connection settings shared by the app and Alembic."""
    options: Dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("mysql"):
        # Hosted MySQL closes idle connections (wait_timeout), and free plans cap the number
        # of connections, so recycle connections early and keep the pool small.
        options.update(pool_recycle=280, pool_size=5, max_overflow=5)
        ctx = ssl_context(settings.DATABASE_SSL, settings.DATABASE_SSL_CA)
        if ctx is not None:
            options["connect_args"] = {"ssl": ctx}
    return options


engine = create_engine(str(settings.DATABASE_URL), **engine_options(str(settings.DATABASE_URL)))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
