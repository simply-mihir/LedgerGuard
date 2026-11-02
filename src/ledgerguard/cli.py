"""Command line interface for LedgerGuard management tasks."""

import argparse
from pathlib import Path

from ledgerguard.config import settings
from ledgerguard.db.migrator import apply_migrations


def cmd_migrate(args: argparse.Namespace) -> None:
    """Run database migrations for coordinator or ledger databases."""
    root_dir = Path(__file__).parent.parent.parent
    target = args.target

    if target in ("coordinator", "all"):
        print(f"Migrating Coordinator DB at {settings.coordinator_admin_db_url.split('@')[-1]}...")
        applied = apply_migrations(
            settings.coordinator_admin_db_url,
            root_dir / "migrations" / "coordinator",
        )
        print(f"Coordinator migrations applied: {applied or 'None (up to date)'}")

    if target in ("ledger1", "all"):
        print(f"Migrating Ledger 1 DB at {settings.ledger1_admin_db_url.split('@')[-1]}...")
        applied = apply_migrations(
            settings.ledger1_admin_db_url,
            root_dir / "migrations" / "ledger",
        )
        print(f"Ledger 1 migrations applied: {applied or 'None (up to date)'}")

    if target in ("ledger2", "all"):
        print(f"Migrating Ledger 2 DB at {settings.ledger2_admin_db_url.split('@')[-1]}...")
        applied = apply_migrations(
            settings.ledger2_admin_db_url,
            root_dir / "migrations" / "ledger",
        )
        print(f"Ledger 2 migrations applied: {applied or 'None (up to date)'}")

    if target == "core":
        print(f"Migrating Core Reference DB at {settings.core_admin_db_url.split('@')[-1]}...")
        applied_coord = apply_migrations(
            settings.core_admin_db_url,
            root_dir / "migrations" / "coordinator",
        )
        applied_ledger = apply_migrations(
            settings.core_admin_db_url,
            root_dir / "migrations" / "ledger",
        )
        print(f"Core migrations applied: coordinator={applied_coord}, ledger={applied_ledger}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LedgerGuard management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate_parser = subparsers.add_parser("migrate", help="Run database migrations")
    migrate_parser.add_argument(
        "--target",
        choices=["all", "coordinator", "ledger1", "ledger2", "core"],
        default="all",
        help="Target database to migrate (default: all)",
    )
    migrate_parser.set_defaults(func=cmd_migrate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
