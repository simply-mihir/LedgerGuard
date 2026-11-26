"""Out-of-process transfer worker used by the real fault-injection harness.

It performs cross-ledger transfers through (possibly faulty) network paths and prints one
JSON line per milestone so the harness can kill it at a chosen moment with SIGKILL.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from uuid import UUID, uuid4

from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.domain.money import AmountPaise


def _emit(**fields: object) -> None:
    print(json.dumps(fields), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coord-url", required=True)
    parser.add_argument("--ledger1-url", required=True)
    parser.add_argument("--ledger2-url", required=True)
    parser.add_argument("--pairs", required=True, help="JSON list of [source, destination] ids")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--amount", type=int, default=1_000)
    parser.add_argument("--pause-ms", type=int, default=0)
    args = parser.parse_args()

    urls = {"ledger-1": args.ledger1_url, "ledger-2": args.ledger2_url}
    pairs = [(UUID(a), UUID(b)) for a, b in json.loads(args.pairs)]
    _emit(event="ready")
    for i in range(args.count):
        src, dst = pairs[i % len(pairs)]
        tid = uuid4()
        _emit(event="start", transfer_id=str(tid))
        try:
            res = submit_coordinator_transfer(
                args.coord_url, urls, f"fault-{tid}", src, dst,
                AmountPaise(args.amount), transfer_id=tid,
            )
            _emit(event="done", transfer_id=str(tid), status=res.get("status"))
        except Exception as exc:  # network faults surface as arbitrary driver errors
            _emit(event="error", transfer_id=str(tid), error=type(exc).__name__)
        if args.pause_ms:
            time.sleep(args.pause_ms / 1000.0)
    _emit(event="finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
