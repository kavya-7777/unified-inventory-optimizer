import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me"


class Settings(BaseSettings):
    APP_ENV: str = "local"
    DEBUG: bool = False
    DATABASE_URL: str = "mysql+pymysql://uio:uio_password@localhost:3306/uio"
    # TLS to the database. Hosted MySQL (e.g. Aiven) requires it: their connection URIs carry
    # ?ssl-mode=REQUIRED, which turns it on automatically. DATABASE_SSL_CA (the provider's CA
    # certificate, as PEM text or a file path) additionally verifies the server's identity.
    DATABASE_SSL: bool = False
    DATABASE_SSL_CA: str = ""
    CORS_ORIGINS: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"
    OPTIMIZATION_TIMEOUT_SECONDS: float = 60.0

    # Machine token for scheduled jobs (the nightly GitHub Action). People log in instead.
    API_KEY: str = ""

    # Login
    JWT_SECRET: str = DEV_JWT_SECRET
    JWT_EXPIRE_MINUTES: int = 8 * 60
    # First admin, created at startup when the users table is empty.
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_NAME: str = "Administrator"

    # Excel import
    IMPORT_MAX_BYTES: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def use_pymysql_driver(cls, url: str) -> str:
        """Hosts hand out mysql:// URLs; SQLAlchemy needs the driver named."""
        if url.startswith("mysql://"):
            return "mysql+pymysql://" + url[len("mysql://"):]
        return url

    @model_validator(mode="after")
    def extract_ssl_mode(self) -> "Settings":
        """
        Aiven-style URIs end in ?ssl-mode=REQUIRED, a MySQL client option PyMySQL doesn't
        understand. Strip it from the URL and turn on DATABASE_SSL instead.
        """
        parts = urlsplit(self.DATABASE_URL)
        query = parse_qsl(parts.query, keep_blank_values=True)
        kept = []
        for key, value in query:
            if key.lower().replace("_", "-") == "ssl-mode":
                if value.upper() not in ("DISABLED", "PREFERRED"):
                    self.DATABASE_SSL = True
            else:
                kept.append((key, value))
        if len(kept) != len(query):
            self.DATABASE_URL = urlunsplit(parts._replace(query=urlencode(kept)))
        return self

    @model_validator(mode="after")
    def require_real_secret_in_production(self) -> "Settings":
        if self.APP_ENV == "production":
            if self.JWT_SECRET in ("", DEV_JWT_SECRET) or len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET (32+ characters) must be set when APP_ENV=production")
        elif not self.JWT_SECRET:
            self.JWT_SECRET = DEV_JWT_SECRET
        return self


settings = Settings()
