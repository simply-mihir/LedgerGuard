"""Tests validating PostgreSQL role boundary enforcement for authentication tables."""

import psycopg
import pytest

from ledgerguard.config import settings


@pytest.mark.integration
def test_reporter_role_denied_access_to_auth_tables():
    """Verify that ledgerguard_reporter role receives PostgreSQL InsufficientPrivilege on all auth tables."""
    # Connect as ledgerguard_reporter
    reporter_url = "postgresql://ledgerguard_reporter:ledgerguard_reporter_secret@localhost:5442/coordinator_db"

    prohibited_tables = [
        "operators",
        "operator_sessions",
        "operator_login_attempts",
    ]

    with psycopg.connect(reporter_url) as conn:
        for table in prohibited_tables:
            with conn.cursor() as cur:
                with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
                    cur.execute(f"SELECT * FROM {table} LIMIT 1;")
                assert "permission denied" in str(exc_info.value).lower()
            conn.rollback()


@pytest.mark.integration
def test_app_role_least_privilege_boundary():
    """Verify that runtime application role cannot delete operators or tamper with login audit history."""
    app_url = settings.coordinator_db_url

    with psycopg.connect(app_url) as conn:
        with conn.cursor() as cur:
            # 1. Prohibit table-level DELETE on operators
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
                cur.execute("DELETE FROM operators WHERE username = 'nonexistent_test_user';")
            assert "permission denied" in str(exc_info.value).lower()
        conn.rollback()

        with conn.cursor() as cur:
            # 2. Prohibit UPDATE on operator_login_attempts (audit trail is append-only)
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
                cur.execute("UPDATE operator_login_attempts SET success = TRUE WHERE identifier = 'audit_test';")
            assert "permission denied" in str(exc_info.value).lower()
        conn.rollback()

        with conn.cursor() as cur:
            # 3. Prohibit DELETE on operator_login_attempts
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
                cur.execute("DELETE FROM operator_login_attempts WHERE identifier = 'audit_test';")
            assert "permission denied" in str(exc_info.value).lower()
        conn.rollback()
