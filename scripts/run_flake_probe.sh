#!/usr/bin/env bash
# Repeat the timing-sensitive test files, quietly and under CPU load, and report failures.
# Usage: scripts/run_flake_probe.sh [REPEATS=3]   (needs the compose databases running)
set -uo pipefail
cd "$(dirname "$0")/.."
REPEATS="${1:-3}"
FILES="tests/test_resilience_backpressure.py tests/test_opposite_direction_concurrency.py \
tests/test_durable_workflow.py tests/test_distributed_failures.py tests/test_operator_auth.py \
tests/test_perf_study.py tests/test_protocol_comparison.py tests/test_chaos_campaign.py \
tests/test_real_fault_injection.py tests/test_rate_limit.py"
FAILED=0
run() {
  echo "== $1 run $2"
  # shellcheck disable=SC2086
  if ! uv run pytest $FILES -q -W error -p no:cacheprovider; then FAILED=1; fi
}
for i in $(seq 1 "$REPEATS"); do run quiet "$i"; done
CORES="$(getconf _NPROCESSORS_ONLN)"
PIDS=()
for _ in $(seq 1 "$CORES"); do yes > /dev/null & PIDS+=("$!"); done
trap 'kill "${PIDS[@]}" 2>/dev/null || true' EXIT
for i in $(seq 1 "$REPEATS"); do run loaded "$i"; done
exit "$FAILED"
