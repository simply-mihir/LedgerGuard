"""Application configuration management for LedgerGuard."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEMO_API_TOKENS = frozenset({"ledgerguard_operator_demo_token"})
_DEMO_INTERNAL_SECRETS = frozenset({"ledgerguard_internal_secret_token_change_in_prod"})


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

    # Transient PostgreSQL Concurrency Retry (40P01 / 40001)
    db_transient_max_retries: int = Field(default=3, ge=0, le=10, alias="DB_TRANSIENT_MAX_RETRIES")
    db_transient_base_backoff_ms: float = Field(default=10.0, ge=1.0, le=1000.0, alias="DB_TRANSIENT_BASE_BACKOFF_MS")
    db_transient_max_backoff_ms: float = Field(default=250.0, ge=10.0, le=5000.0, alias="DB_TRANSIENT_MAX_BACKOFF_MS")

    # Observability / OpenTelemetry
    otel_exporter: Literal["none", "console", "otlp", "memory"] = Field(
        default="memory", alias="LEDGERGUARD_OTEL_EXPORTER"
    )
    otel_endpoint: str = Field(
        default="http://localhost:4318/v1/traces", alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )

    @model_validator(mode="after")
    def _reject_demo_secrets_in_production(self) -> "Settings":
        """Fail closed: the documented demo secrets must never authenticate a production API."""
        if self.env == "production":
            if self.api_bearer_token in _DEMO_API_TOKENS or len(self.api_bearer_token) < 32:
                raise ValueError(
                    "API_BEARER_TOKEN must be set to a unique secret of >=32 characters in production."
                )
            if self.internal_service_secret in _DEMO_INTERNAL_SECRETS:
                raise ValueError("INTERNAL_SERVICE_SECRET must be overridden in production.")
        return self

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
