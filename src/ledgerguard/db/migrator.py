"""Explicit SQL migration runner with schema_migrations tracking table."""

import logging
from pathlib import Path

import psycopg

logger = logging.getLogger(__name__)


def init_migration_table(conn: psycopg.Connection) -> None:
    """Ensure the schema_migrations tracking table exists."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
    conn.commit()


def get_applied_versions(conn: psycopg.Connection) -> set[str]:
    """Retrieve the set of already applied migration version strings."""
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations;")
        rows = cur.fetchall()
        return {r["version"] if isinstance(r, dict) else r[0] for r in rows}


def apply_migrations(admin_db_url: str, migrations_dir: Path | str) -> list[str]:
    """Apply all pending SQL migrations in ascending filename order."""
    mig_path = Path(migrations_dir)
    if not mig_path.exists():
        logger.warning("Migrations directory %s does not exist; skipping.", mig_path)
        return []

    sql_files = sorted(mig_path.glob("*.sql"))
    applied_this_run: list[str] = []

    with psycopg.connect(admin_db_url, autocommit=False) as conn:
        init_migration_table(conn)
        applied = get_applied_versions(conn)

        for sql_file in sql_files:
            version = sql_file.name
            if version in applied:
                continue

            logger.info("Applying migration %s to %s", version, admin_db_url.split("@")[-1])
            sql_content = sql_file.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql_content)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s);",
                    (version,),
                )
            conn.commit()
            applied_this_run.append(version)

    return applied_this_run
