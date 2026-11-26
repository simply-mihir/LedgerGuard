"""TLC checks of the concurrent multi-transfer TLA+ model (skipped without Java + TLC)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from ledgerguard.conformance.tla_trace import SPEC_DIR, find_jar, tlc_available

pytestmark = pytest.mark.skipif(not tlc_available(), reason="java + tla2tools.jar not available")


def _tlc(cfg: str) -> tuple[int, str]:
    jar = find_jar()
    with tempfile.TemporaryDirectory(prefix="lg-multi-") as tmp:
        work = Path(tmp)
        # Run on a copy: TLC writes counterexample (*_TTrace_*) files next to the spec.
        for name in ("LedgerGuardTCCMulti.tla", cfg):
            shutil.copy(SPEC_DIR / name, work / name)
        proc = subprocess.run(
            ["java", "-XX:+UseSerialGC", "-cp", str(jar), "tlc2.TLC", "-workers", "2",
             "-metadir", str(work / "states"), "-config", str(work / cfg),
             str(work / "LedgerGuardTCCMulti.tla")],
            capture_output=True, text=True, timeout=240, cwd=tmp,
        )
    return proc.returncode, proc.stdout + proc.stderr


def test_three_concurrent_transfers_preserve_all_invariants_and_terminate() -> None:
    code, out = _tlc("LedgerGuardTCCMulti.cfg")
    assert code == 0, out[-1500:]
    assert "No error has been found" in out
    assert "violated" not in out


def test_defective_funds_check_yields_overspend_counterexample() -> None:
    code, out = _tlc("LedgerGuardTCCMulti_broken.cfg")
    assert code != 0
    assert "Invariant NoOverspend is violated" in out
    assert '"PREPARED"' in out  # counterexample shows concurrent holds
