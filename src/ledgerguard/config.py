"""Application configuration management for LedgerGuard."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for LedgerGuard services and test runners."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    env: Literal["local", "test", "production"] = Field(default="local", alias="LEDGERGUARD_ENV")
    fault_injection_enabled: bool = Field(default=False, alias="FAULT_INJECTION_ENABLED")

    # Coordinator Database
    coordinator_db_url: str = Field(
        default="postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5442/coordinator_db",
        alias="COORDINATOR_DB_URL",
    )
    coordinator_admin_db_url: str = Field(
        default="postgresql://ledgerguard_admin:ledgerguard_admin_secret@localhost:5442/coordinator_db",
        alias="COORDINATOR_ADMIN_DB_URL",
    )

    # Participant Ledger 1 Database
    ledger1_db_url: str = Field(
        default="postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5443/ledger1_db",
        alias="LEDGER1_DB_URL",
    )
    ledger1_admin_db_url: str = Field(
        default="postgresql://ledgerguard_admin:ledgerguard_admin_secret@localhost:5443/ledger1_db",
        alias="LEDGER1_ADMIN_DB_URL",
    )

    # Participant Ledger 2 Database
    ledger2_db_url: str = Field(
        default="postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5444/ledger2_db",
        alias="LEDGER2_DB_URL",
    )
    ledger2_admin_db_url: str = Field(
        default="postgresql://ledgerguard_admin:ledgerguard_admin_secret@localhost:5444/ledger2_db",
        alias="LEDGER2_ADMIN_DB_URL",
    )

    # Single-database reference mode URL (core mode)
    core_db_url: str = Field(
        default="postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5442/coordinator_db",
        alias="CORE_DB_URL",
    )
    core_admin_db_url: str = Field(
        default="postgresql://ledgerguard_admin:ledgerguard_admin_secret@localhost:5442/coordinator_db",
        alias="CORE_ADMIN_DB_URL",
    )

    # Service Ports & URLs
    coordinator_port: int = Field(default=8010, alias="COORDINATOR_PORT")
    coordinator_url: str = Field(default="http://localhost:8010", alias="COORDINATOR_URL")
    ledger1_port: int = Field(default=8011, alias="LEDGER1_PORT")
    ledger1_url: str = Field(default="http://localhost:8011", alias="LEDGER1_URL")
    ledger2_port: int = Field(default=8012, alias="LEDGER2_PORT")
    ledger2_url: str = Field(default="http://localhost:8012", alias="LEDGER2_URL")
    console_port: int = Field(default=3300, alias="CONSOLE_PORT")

    # Security & Origins
    trusted_origins_raw: str | None = Field(default=None, alias="LEDGERGUARD_TRUSTED_ORIGINS")
    cookie_secure: bool | None = Field(default=None, alias="LEDGERGUARD_COOKIE_SECURE")
    trusted_proxies_raw: str = Field(default="127.0.0.1,::1,testclient", alias="LEDGERGUARD_TRUSTED_PROXIES")
    internal_service_secret: str = Field(
        default="ledgerguard_internal_secret_token_change_in_prod",
        alias="INTERNAL_SERVICE_SECRET",
    )
    api_bearer_token: str = Field(
        default="ledgerguard_operator_demo_token",
        alias="API_BEARER_TOKEN",
    )

    # Workers
    worker_poll_interval_ms: int = Field(default=200, alias="WORKER_POLL_INTERVAL_MS")
    worker_batch_size: int = Field(default=20, alias="WORKER_BATCH_SIZE")
    worker_lock_timeout_seconds: int = Field(default=10, alias="WORKER_LOCK_TIMEOUT_SECONDS")

    def get_trusted_origins(self) -> list[str]:
        """Return validated list of complete trusted origins.

        In production, LEDGERGUARD_TRUSTED_ORIGINS must be explicitly configured.
        In local/test environments, defaults to local dev servers if not specified.
        """
        if self.trusted_origins_raw is not None and self.trusted_origins_raw.strip():
            raw_list = [o.strip() for o in self.trusted_origins_raw.split(",") if o.strip()]
            from ledgerguard.auth.origins import normalize_origin

            return [normalize_origin(o) for o in raw_list]

        if self.env in ("local", "test"):
            return [
                "http://localhost:3300",
                "http://127.0.0.1:3300",
                "http://localhost:8010",
                "http://127.0.0.1:8010",
            ]

        raise ValueError(
            "LEDGERGUARD_TRUSTED_ORIGINS must be configured outside local/test environment."
        )

    def get_trusted_proxies(self) -> set[str]:
        """Return set of IP addresses permitted to set reverse-proxy headers."""
        return {p.strip() for p in self.trusted_proxies_raw.split(",") if p.strip()}


settings = Settings()
