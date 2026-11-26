"""Application configuration management for LedgerGuard."""

import re
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEMO_API_TOKENS = frozenset({"ledgerguard_operator_demo_token"})
_DEMO_INTERNAL_SECRETS = frozenset({"ledgerguard_internal_secret_token_change_in_prod"})
_DEMO_DB_PASSWORDS = ("ledgerguard_app_secret", "ledgerguard_admin_secret")


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
    # Named per-caller service credentials: "name:ROLE:token,name2:ROLE:token". Several entries
    # may share a name (zero-downtime rotation: add the new token, deploy callers, drop the old).
    service_tokens_raw: str | None = Field(default=None, alias="API_SERVICE_TOKENS")

    # API rate limiting (per client, in-process token bucket; 0 disables). Bursts up to one
    # minute's worth are allowed. Multi-process deployments get the limit per process.
    rate_limit_per_minute: int = Field(default=1200, ge=0, alias="API_RATE_LIMIT_PER_MINUTE")
    write_rate_limit_per_minute: int = Field(default=600, ge=0, alias="API_WRITE_RATE_LIMIT_PER_MINUTE")

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
    def _validate_secrets(self) -> "Settings":
        """Fail closed on weak or demo secrets; validate service credentials at startup."""
        _ = self.get_service_credentials()  # raises ValueError on malformed configuration
        if self.env == "production":
            # The shared legacy token is disabled in production (see get_current_operator);
            # callers must use named service credentials.
            if self.internal_service_secret in _DEMO_INTERNAL_SECRETS:
                raise ValueError("INTERNAL_SERVICE_SECRET must be overridden in production.")
            if self.cookie_secure is False:
                raise ValueError("LEDGERGUARD_COOKIE_SECURE=false is not allowed in production.")
            if self.fault_injection_enabled:
                raise ValueError("FAULT_INJECTION_ENABLED must be false in production.")
            insecure = [o for o in self.get_trusted_origins() if not o.startswith("https://")]
            if insecure:
                raise ValueError(f"production trusted origins must use https: {insecure}")
            urls = (
                self.coordinator_db_url, self.coordinator_admin_db_url, self.ledger1_db_url,
                self.ledger1_admin_db_url, self.ledger2_db_url, self.ledger2_admin_db_url,
                self.core_db_url, self.core_admin_db_url,
            )
            if any(pw in url for url in urls for pw in _DEMO_DB_PASSWORDS):
                raise ValueError("database URLs use the demo password; override them in production.")
        return self

    def get_service_credentials(self) -> list[tuple[str, str, str]]:
        """Parse API_SERVICE_TOKENS into (name, role, token) tuples; every token >=32 chars."""
        if not self.service_tokens_raw or not self.service_tokens_raw.strip():
            return []
        roles = {"VIEWER", "OPERATOR", "APPROVER", "AUDITOR", "ADMIN"}
        out: list[tuple[str, str, str]] = []
        seen_tokens: set[str] = set()
        names_roles: dict[str, str] = {}
        for entry in (e.strip() for e in self.service_tokens_raw.split(",") if e.strip()):
            parts = entry.split(":", 2)
            if len(parts) != 3:
                raise ValueError("API_SERVICE_TOKENS entries must look like name:ROLE:token")
            name, role, token = (p.strip() for p in parts)
            if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{1,63}", name):
                raise ValueError(f"invalid service credential name {name!r}")
            if role not in roles:
                raise ValueError(f"invalid role {role!r} for service credential {name!r}")
            if len(token) < 32 or token in _DEMO_API_TOKENS:
                raise ValueError(f"service credential {name!r} needs a unique token of >=32 chars")
            if token in seen_tokens:
                raise ValueError("service credential tokens must be unique")
            if names_roles.setdefault(name, role) != role:
                raise ValueError(f"service credential {name!r} has conflicting roles")
            seen_tokens.add(token)
            out.append((name, role, token))
        return out

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
