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


def cmd_check_history(args: argparse.Namespace) -> None:
    """Check an execution history JSON file against the independent reference model."""
    from ledgerguard.reference import ExecutionHistory, check_history, format_report_text

    history = ExecutionHistory.from_json_file(args.history_file)
    report = check_history(history)
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(format_report_text(report))
    if report.status != "PASS":
        sys.exit(1)


def _ledger_url_for(ledger_id: str) -> str:
    return settings.ledger1_db_url if ledger_id == "ledger-1" else settings.ledger2_db_url


def cmd_verify_journal_chain(args: argparse.Namespace) -> None:
    """Verify hash chain integrity for a participant ledger."""
    from ledgerguard.audit import verify_journal_chain

    report = verify_journal_chain(_ledger_url_for(args.ledger), args.ledger)
    print(report.model_dump_json(indent=2))
    if report.status != "PASS":
        sys.exit(1)


def cmd_create_journal_checkpoint(args: argparse.Namespace) -> None:
    """Create a Merkle checkpoint on a ledger and attest it in Coordinator DB."""
    from ledgerguard.audit import create_journal_checkpoint

    res = create_journal_checkpoint(
        _ledger_url_for(args.ledger),
        settings.coordinator_db_url,
        args.ledger,
        first_sequence=args.first_sequence,
    )
    print(res.model_dump_json(indent=2))


def cmd_verify_journal_checkpoint(args: argparse.Namespace) -> None:
    """Verify a Merkle checkpoint against ledger entries and coordinator attestation."""
    from ledgerguard.audit import verify_journal_checkpoint

    res = verify_journal_checkpoint(
        _ledger_url_for(args.ledger),
        settings.coordinator_db_url,
        args.ledger,
        checkpoint_id=args.checkpoint_id,
    )
    print(res.model_dump_json(indent=2))
    if res.status != "PASS":
        sys.exit(1)


def cmd_run_worker(args: argparse.Namespace) -> None:
    import signal
    import threading

    from ledgerguard.worker.daemon import run_worker

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    sweeps = run_worker(
        settings.coordinator_db_url,
        {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url},
        stop,
        poll_interval_s=max(settings.worker_poll_interval_ms / 1000.0, 1.0),
    )
    print(f"worker stopped after {sweeps} sweeps")


def cmd_verify_all_ledgers(args: argparse.Namespace) -> None:
    """Verify hash chains across all participant ledgers."""
    import json

    from ledgerguard.audit import verify_all_ledgers

    res = verify_all_ledgers()
    print(json.dumps(res, indent=2))
    if res["status"] != "PASS":
        sys.exit(1)


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
        choices=["VIEWER", "OPERATOR", "APPROVER", "AUDITOR", "ADMIN"],
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

    history_parser = subparsers.add_parser(
        "check-history",
        help="Verify a canonical execution history JSON file against the independent reference model",
    )
    history_parser.add_argument("history_file", help="Path to execution history JSON file")
    history_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    history_parser.set_defaults(func=cmd_check_history)

    vjc_parser = subparsers.add_parser("verify-journal-chain", help="Verify sequential SHA-256 journal chain")
    vjc_parser.add_argument("--ledger", choices=["ledger-1", "ledger-2"], default="ledger-1")
    vjc_parser.set_defaults(func=cmd_verify_journal_chain)

    cjc_parser = subparsers.add_parser("create-journal-checkpoint", help="Create and attest Merkle checkpoint")
    cjc_parser.add_argument("--ledger", choices=["ledger-1", "ledger-2"], default="ledger-1")
    cjc_parser.add_argument("--first-sequence", type=int, default=1)
    cjc_parser.set_defaults(func=cmd_create_journal_checkpoint)

    vcp_parser = subparsers.add_parser("verify-journal-checkpoint", help="Verify Merkle checkpoint and attestation")
    vcp_parser.add_argument("--ledger", choices=["ledger-1", "ledger-2"], default="ledger-1")
    vcp_parser.add_argument("--checkpoint-id", default=None)
    vcp_parser.set_defaults(func=cmd_verify_journal_checkpoint)

    val_parser = subparsers.add_parser("verify-all-ledgers", help="Verify hash chains across all ledgers")
    val_parser.set_defaults(func=cmd_verify_all_ledgers)

    worker_parser = subparsers.add_parser(
        "run-worker", help="Run the always-on recovery worker (wakes on outbox NOTIFY, polls as fallback)"
    )
    worker_parser.set_defaults(func=cmd_run_worker)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
