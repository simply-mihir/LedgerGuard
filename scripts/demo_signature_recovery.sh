#!/usr/bin/env bash
set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "========================================================================"
echo " Starting LedgerGuard Signature Scenario Demo: Interrupted TCC Recovery "
echo "========================================================================"

# Check for uv binary
UV_BIN="${HOME}/.local/bin/uv"
if ! command -v "${UV_BIN}" &> /dev/null; then
    if command -v uv &> /dev/null; then
        UV_BIN="uv"
    else
        echo "Error: uv not found. Please ensure uv is installed."
        exit 1
    fi
fi

# Execute Python demo
exec "${UV_BIN}" run python scripts/demo_signature_recovery.py "$@"
