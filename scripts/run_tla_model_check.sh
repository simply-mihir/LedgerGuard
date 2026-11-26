#!/usr/bin/env bash
set -euo pipefail

# Pinned TLA+ tools release
TLA_VERSION="1.8.0"
TLA_URL="https://github.com/tlaplus/tlaplus/releases/download/v${TLA_VERSION}/tla2tools.jar"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/ledgerguard-tla"
JAR_PATH="${CACHE_DIR}/tla2tools-${TLA_VERSION}.jar"

mkdir -p "$CACHE_DIR"
if [ ! -f "$JAR_PATH" ]; then
  echo "Downloading pinned tla2tools.jar v${TLA_VERSION}..."
  curl -fsSL "$TLA_URL" -o "$JAR_PATH"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TLA_DIR="${ROOT_DIR}/formal/tla"
OUT_DIR="${TLA_DIR}/states_tmp"
mkdir -p "$OUT_DIR"
trap 'rm -rf "$OUT_DIR" "${TLA_DIR}"/*_TTrace_*.tla' EXIT

echo "=== Running TLC Model Checker on LedgerGuardTCC.tla ==="
java -XX:+UseParallelGC -cp "$JAR_PATH" tlc2.TLC \
  -workers auto \
  -metadir "$OUT_DIR" \
  -config "${TLA_DIR}/LedgerGuardTCC.cfg" \
  "${TLA_DIR}/LedgerGuardTCC.tla"

if [ "${VERIFY_BROKEN:-0}" = "1" ]; then
  echo "=== Verifying intentionally broken model detects violation ==="
  set +e
  java -XX:+UseParallelGC -cp "$JAR_PATH" tlc2.TLC \
    -workers auto \
    -metadir "$OUT_DIR" \
    -config "${TLA_DIR}/LedgerGuardTCC_broken.cfg" \
    "${TLA_DIR}/LedgerGuardTCC_broken.tla"
  STATUS=$?
  set -e
  if [ "$STATUS" -eq 0 ]; then
    echo "ERROR: Broken model unexpectedly passed!"
    exit 1
  fi
  echo "Broken model correctly detected invariant violation (exit $STATUS)."
fi
