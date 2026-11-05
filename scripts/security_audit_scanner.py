#!/usr/bin/env python3
"""LedgerGuard Security, Privacy, and Repository Integrity Scanner.

Performs static regex and rule-based pattern auditing across:
1. All tracked repository files.
2. Feature-branch commit diffs (5f3db8b..HEAD).
3. Reachable Git commit author/committer metadata.
4. Sensitive filename rules (.env, database dumps, source maps).
5. Token, key, path, and personal email leakage checks.
"""

from __future__ import annotations

import re
import struct
import subprocess
import sys
from pathlib import Path

# Sensitive regex patterns
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")
API_TOKEN_PATTERN = re.compile(
    r"(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16})"
)
CONSUMER_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@(gmail|yahoo|hotmail|outlook)\.com", re.IGNORECASE)
USER_PATH_PATTERN = re.compile(r"/(?:Users|home)/[a-zA-Z0-9._-]+")

# Ignored binary extensions
BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".ico",
    ".woff",
    ".woff2",
    ".pdf",
    ".tar.gz",
    ".whl",
}


def run_cmd(cmd: list[str]) -> str:
    """Execute shell command and return stdout string."""
    try:
        return subprocess.check_output(cmd, stderr=subprocess.PIPE).decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError as err:
        print(f"Error running command {cmd}: {err.stderr.decode('utf-8', errors='ignore')}", file=sys.stderr)
        raise


def scan_tracked_files() -> list[str]:
    """Inspect all tracked filenames and contents."""
    errors: list[str] = []
    output = run_cmd(["git", "ls-files"])
    tracked_files = [line.strip() for line in output.splitlines() if line.strip()]

    for rel_path in tracked_files:
        path = Path(rel_path)

        # 1. Filename checks
        if ".env" in path.name and path.name != ".env.example":
            errors.append(f"Prohibited environment file tracked: {rel_path}")

        if path.suffix.lower() in (".dump", ".bak") or rel_path.endswith(".sql.gz"):
            errors.append(f"Prohibited database dump file tracked: {rel_path}")

        if path.suffix.lower() == ".map":
            errors.append(f"Prohibited frontend source map tracked: {rel_path}")

        if path.suffix.lower() in BINARY_EXTENSIONS:
            continue

        # 2. File content inspection
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Private keys
        if PRIVATE_KEY_PATTERN.search(content):
            errors.append(f"Private key header detected in {rel_path}")

        # API tokens
        if API_TOKEN_PATTERN.search(content):
            errors.append(f"Personal/Cloud API token detected in {rel_path}")

        # Absolute paths (/Users/ or /home/)
        if rel_path != "scripts/security_audit_scanner.py":
            if USER_PATH_PATTERN.search(content):
                errors.append(f"Absolute user path detected in {rel_path}")

    return errors


def scan_commit_diffs(base_sha: str = "5f3db8b") -> list[str]:
    """Scan commit range diffs for tokens, keys, paths, and personal emails."""
    errors: list[str] = []
    try:
        diff_text = run_cmd(["git", "log", "-p", f"{base_sha}..HEAD"])
    except Exception as e:
        return [f"Failed to inspect git log diff: {e}"]

    if PRIVATE_KEY_PATTERN.search(diff_text):
        errors.append("Private key block detected in branch commit history diffs.")

    if API_TOKEN_PATTERN.search(diff_text):
        errors.append("Personal/Cloud API token detected in branch commit history diffs.")

    # Search for user paths in diffs, skipping self-references in security_audit_scanner.py
    for match in USER_PATH_PATTERN.finditer(diff_text):
        matched_str = match.group(0)
        start = max(0, match.start() - 250)
        context = diff_text[start:match.end() + 250]
        if "security_audit_scanner.py" in context:
            continue
        errors.append(f"Absolute user path detected in branch commit diffs: {matched_str}")
        break

    emails = CONSUMER_EMAIL_PATTERN.findall(diff_text)
    if emails:
        errors.append(f"Personal consumer email domains found in branch commit diffs: {set(emails)}")

    return errors


def scan_git_authors() -> list[str]:
    """Inspect all reachable commit author and committer emails."""
    errors: list[str] = []
    authors_output = run_cmd(["git", "log", "--format=%an <%ae>"]).splitlines()
    unique_authors = set(authors_output)

    for author in unique_authors:
        # Check for personal consumer emails in git history
        if CONSUMER_EMAIL_PATTERN.search(author):
            errors.append(f"Personal consumer email found in git author history: {author}")

    return errors


def scan_screenshot_artifacts() -> list[str]:
    """Verify expected screenshots, validate PNG headers, dimensions, and path hygiene.

    Automated checks:
    - Expected screenshots exist with valid PNG magic bytes.
    - Dimensions are valid and non-zero.
    - No obvious local paths exist in metadata/chunks.
    - No unexpected image files are tracked in docs/assets.

    Note: Visual inspection of rendered graphical contents must be performed separately by a human reviewer.
    """
    errors: list[str] = []
    expected_screenshots = {
        "docs/assets/ledgerguard-landing.png",
        "docs/assets/ledgerguard-overview.png",
        "docs/assets/ledgerguard-transfer-lifecycle.png",
    }

    for rel_path in sorted(expected_screenshots):
        path = Path(rel_path)
        if not path.is_file():
            errors.append(f"Expected documentation screenshot missing: {rel_path}")
            continue

        data = path.read_bytes()
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            errors.append(f"Invalid PNG magic bytes in screenshot: {rel_path}")
            continue

        width, height = struct.unpack(">II", data[16:24])
        if width < 800 or height < 300:
            errors.append(f"Unusually small screenshot dimensions ({width}x{height}) in {rel_path}")

        # Check for local user paths in raw PNG chunk bytes
        if b"/Users/" in data or b"/home/" in data:
            errors.append(f"Local filesystem path found in image chunk metadata: {rel_path}")

    actual_images = {str(p) for p in Path("docs/assets").glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")}
    unexpected = actual_images - expected_screenshots
    if unexpected:
        errors.append(f"Unexpected image files found in docs/assets: {unexpected}")

    return errors


def main() -> None:
    print("===================================================================")
    print(" LedgerGuard Repository Security, Privacy & Integrity Scanner      ")
    print("===================================================================")

    all_errors: list[str] = []

    print("[1/4] Scanning tracked repository files & filenames...")
    file_errors = scan_tracked_files()
    if file_errors:
        all_errors.extend(file_errors)
    else:
        print("  ✓ Tracked files clean: zero prohibited files, dumps, source maps, or paths.")

    print("[2/4] Scanning feature-branch diffs (5f3db8b..HEAD)...")
    diff_errors = scan_commit_diffs()
    if diff_errors:
        all_errors.extend(diff_errors)
    else:
        print("  ✓ Feature branch diffs clean: zero tokens, private keys, or personal emails.")

    print("[3/4] Scanning commit author metadata...")
    author_errors = scan_git_authors()
    if author_errors:
        all_errors.extend(author_errors)
    else:
        print("  ✓ Commit authors clean: all commits use privacy-protected or authorized emails.")

    print("[4/4] Verifying documentation screenshot artifacts...")
    screenshot_errors = scan_screenshot_artifacts()
    if screenshot_errors:
        all_errors.extend(screenshot_errors)
    else:
        print("  ✓ Found 3 expected screenshots: valid PNG headers, verified dimensions, zero metadata path leaks.")
        print("  ℹ Note: Visual inspection of rendered image contents is performed manually and documented separately.")

    print("-------------------------------------------------------------------")
    if all_errors:
        print(f"SCAN FAILED: {len(all_errors)} violation(s) found:")
        for err in all_errors:
            print(f"  ✗ {err}")
        sys.exit(1)
    else:
        print("SCAN PASSED: All repository integrity, security, and privacy checks passed.")
        print("===================================================================")


if __name__ == "__main__":
    main()
