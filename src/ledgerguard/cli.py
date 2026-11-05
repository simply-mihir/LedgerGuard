"""Command line interface for LedgerGuard management tasks."""

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from ledgerguard.auth.models import CreateOperatorRequest
from ledgerguard.auth.service import create_operator_account, enroll_totp
from ledgerguard.config import settings
from ledgerguard.db.migrator import apply_migrations
from ledgerguard.db.pool import get_db_connection


def _resolve_password(
    stdin_password: bool,
    env_var_name: str,
    prompt_label: str,
    require_confirmation: bool = True,
    default_test_password: str | None = None,
) -> str:
    """Resolve password securely via stdin, test env var, or hidden getpass prompt."""
    # 1. Protected stdin mode for CI/automation
    if stdin_password:
        line = sys.stdin.readline().strip()
        if not line:
            print("Error: Stdin was empty; password required.", file=sys.stderr)
            sys.exit(1)
        return line

    # 2. Clearly named test-only environment mechanism
    if settings.env in ("local", "test"):
        test_pwd = os.environ.get("LEDGERGUARD_TEST_ADMIN_PASSWORD") or os.environ.get(env_var_name)
        if test_pwd:
            return test_pwd
        if default_test_password:
            return default_test_password

    # 3. Hidden interactive prompt with confirmation
    if sys.stdin.isatty():
        pwd = getpass.getpass(f"Enter {prompt_label} password: ")
        if not pwd:
            print("Error: Password cannot be empty.", file=sys.stderr)
            sys.exit(1)
        if require_confirmation:
            confirm = getpass.getpass("Confirm password: ")
            if pwd != confirm:
                print("Error: Passwords do not match.", file=sys.stderr)
                sys.exit(1)
        return pwd

    print(
        "Error: Non-interactive environment. Provide password via stdin (--stdin-password) "
        "or set LEDGERGUARD_TEST_ADMIN_PASSWORD in development/test.",
        file=sys.stderr,
    )
    sys.exit(1)


def cmd_create_operator(args: argparse.Namespace) -> None:
    """Create a new operator with Argon2id password hash and optional TOTP."""
    password = _resolve_password(
        stdin_password=args.stdin_password,
        env_var_name="LEDGERGUARD_OPERATOR_PASSWORD",
        prompt_label="operator",
        require_confirmation=True,
    )

    req = CreateOperatorRequest(
        username=args.username,
        email=args.email,
        password=password,
        role=args.role,
        enable_totp=args.enable_totp,
    )
    op = create_operator_account(req)
    print(f"Operator created successfully: ID={op.operator_id}, username={op.username}, role={op.role}")
    if op.totp_enabled:
        secret, uri, key = enroll_totp(op.operator_id)
        print(f"TOTP Authenticator Key: {key}")
        print(f"Provisioning URI: {uri}")


def cmd_seed_demo_operator(args: argparse.Namespace) -> None:
    """Seed demo operator account for development/CI if not already present."""
    username = args.username
    email = args.email

    with get_db_connection(settings.coordinator_db_url) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT operator_id, username FROM operators WHERE username = %s OR email = %s",
                (username, email),
            )
            existing = cur.fetchone()
            if existing:
                print(f"Demo operator already exists: {existing['username']} ({existing['operator_id']})")
                return

    password = _resolve_password(
        stdin_password=args.stdin_password,
        env_var_name="LEDGERGUARD_DEMO_PASSWORD",
        prompt_label="demo operator",
        require_confirmation=False,
    )

    req = CreateOperatorRequest(
        username=username,
        email=email,
        password=password,
        role="ADMIN",
        enable_totp=args.enable_totp,
    )
    op = create_operator_account(req)
    print(f"Demo operator seeded successfully: ID={op.operator_id}, username={op.username}")
    if op.totp_enabled:
        secret, uri, key = enroll_totp(op.operator_id)
        print(f"Demo TOTP Key: {key}")
        print(f"Demo Provisioning URI: {uri}")


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

    operator_parser = subparsers.add_parser("create-operator", help="Provision a new operator account")
    operator_parser.add_argument("--username", required=True, help="Operator username")
    operator_parser.add_argument("--email", required=True, help="Operator email address")
    operator_parser.add_argument(
        "--stdin-password",
        action="store_true",
        help="Read operator password securely from standard input (recommended for non-interactive CI)",
    )
    operator_parser.add_argument(
        "--role",
        choices=["OPERATOR", "ADMIN", "AUDITOR"],
        default="ADMIN",
        help="Operator role (default: ADMIN)",
    )
    operator_parser.add_argument(
        "--enable-totp",
        action="store_true",
        help="Enable TOTP two-factor authentication upon creation",
    )
    operator_parser.set_defaults(func=cmd_create_operator)

    seed_parser = subparsers.add_parser(
        "seed-demo-operator",
        help="Provision local demo operator if not already present (reads LEDGERGUARD_TEST_ADMIN_PASSWORD in dev/test)",
    )
    seed_parser.add_argument("--username", default="operator", help="Demo username (default: operator)")
    seed_parser.add_argument(
        "--email", default="operator@ledgerguard.internal", help="Demo email (default: operator@ledgerguard.internal)"
    )
    seed_parser.add_argument(
        "--stdin-password",
        action="store_true",
        help="Read demo operator password securely from standard input (recommended for CI)",
    )
    seed_parser.add_argument(
        "--enable-totp",
        action="store_true",
        help="Provision demo operator with pre-configured TOTP",
    )
    seed_parser.set_defaults(func=cmd_seed_demo_operator)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
