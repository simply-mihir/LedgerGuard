"""Smoke test verifying environment, database connections, and PostgreSQL version."""

import psycopg
import pytest

from ledgerguard.config import settings
from ledgerguard.db.migrator import get_applied_versions, init_migration_table


def test_settings_loaded():
    """Verify application configuration loads without errors."""
    assert settings.env in ("local", "test", "production")
    assert "coordinator_db" in settings.coordinator_db_url
    assert "ledger1_db" in settings.ledger1_db_url
    assert "ledger2_db" in settings.ledger2_db_url


@pytest.mark.integration
def test_real_postgres_connection():
    """Verify connection to real PostgreSQL 17 instances."""
    for name, url in [
        ("coordinator", settings.coordinator_admin_db_url),
        ("ledger1", settings.ledger1_admin_db_url),
        ("ledger2", settings.ledger2_admin_db_url),
    ]:
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version_str = cur.fetchone()[0]
                assert "PostgreSQL 17" in version_str, (
                    f"{name} DB should be PostgreSQL 17, got {version_str}"
                )


@pytest.mark.integration
def test_migration_table_initialization():
    """Verify schema_migrations table can be initialized on real PostgreSQL."""
    with psycopg.connect(settings.coordinator_admin_db_url) as conn:
        init_migration_table(conn)
        applied = get_applied_versions(conn)
        assert isinstance(applied, set)
