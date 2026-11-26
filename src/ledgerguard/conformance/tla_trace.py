"""Trace validation with the TLC model checker.

A recorded trace is turned into a TLA+ module that extends ``LedgerGuardTCC``. Each
observed event must be matched, in order, by the corresponding specification action;
unobserved actions may interleave. TLC then searches for a behaviour that consumes the
whole trace: an *invariant violation* of ``NotAccepted`` means the trace is accepted.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

TLA_VERSION = "1.8.0"
SPEC_DIR = Path(__file__).resolve().parents[3] / "formal" / "tla"

_OBS = """\
Obs(e) ==
    CASE e = "PHASE_PREPARE_STARTED" -> UNCHANGED vars
      [] e = "DECISION_MADE:COMMIT" -> DecideCommit
      [] e = "DECISION_MADE:CANCEL" -> DecideCancel
      [] e = "DECISION_COMMITTED" -> decision = "COMMIT" /\\ UNCHANGED vars
      [] e = "SOURCE_CONFIRMED" -> SourceConfirm
      [] e = "DESTINATION_CONFIRMED" -> DestinationConfirm
      [] e = "SOURCE_CANCELLED" -> CancelSource
      [] e = "DESTINATION_CANCELLED" -> CancelDestination
      [] e = "TRANSFER_SETTLED" -> txState = "SETTLED" /\\ UNCHANGED vars
      [] e = "TRANSFER_CANCELLED" -> txState = "CANCELLED" /\\ UNCHANGED vars
      [] e = "SOURCE_PREPARE_REJECTED" ->
            decision = "CANCEL" /\\ srcState \\in {"NONE", "TOMBSTONE"} /\\ UNCHANGED vars
      [] e = "DESTINATION_PREPARE_REJECTED" ->
            decision = "CANCEL" /\\ srcState # "CONFIRMED" /\\ dstState # "CONFIRMED"
            /\\ UNCHANGED vars
      [] OTHER -> FALSE
"""


def find_jar() -> Path | None:
    env = os.environ.get("LEDGERGUARD_TLA_JAR")
    candidates = [Path(env)] if env else []
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    candidates.append(cache / "ledgerguard-tla" / f"tla2tools-{TLA_VERSION}.jar")
    return next((p for p in candidates if p.is_file()), None)


def tlc_available() -> bool:
    return shutil.which("java") is not None and find_jar() is not None


def render_module(tokens: list[str]) -> str:
    seq = ", ".join(f'"{t}"' for t in tokens)
    obs = _OBS.replace("[] OTHER -> FALSE", "[] OTHER -> FALSE")
    # TLA+ CASE has no default without OTHER; keep OTHER as the final arm.
    return f"""---------------------------- MODULE LedgerGuardTCCTrace ----------------------------
EXTENDS LedgerGuardTCC, Sequences

VARIABLE pos

Trace == <<{seq}>>

{obs}
Silent ==
    \\/ SourcePrepare \\/ DestinationPrepare \\/ DuplicateCommandIgnored
    \\/ WorkerCrash \\/ WorkerRecover \\/ LoseMessage \\/ RetryPending
    \\/ CancelSource \\/ CancelDestination

TInit == Init /\\ pos = 0

TNext ==
    \\/ /\\ pos < Len(Trace)
       /\\ Obs(Trace[pos + 1])
       /\\ pos' = pos + 1
    \\/ /\\ Silent
       /\\ UNCHANGED pos

NotAccepted == pos # Len(Trace)
=============================================================================
"""


_CFG = """INIT TInit
NEXT TNext
CONSTANTS
    InitSourceBal = 10
    InitDestBal = 0
    Amount = 4
    MaxLosses = 1
    MaxCrashes = 1
INVARIANT NotAccepted
"""


def tlc_accepts(tokens: list[str], timeout_s: int = 120) -> bool:
    """Run TLC trace validation; True iff the specification can produce the trace."""
    jar = find_jar()
    if shutil.which("java") is None or jar is None:
        raise RuntimeError("java and tla2tools.jar are required for TLC trace validation")
    unknown = [t for t in tokens if '"' in t]
    if unknown:
        raise ValueError(f"invalid tokens: {unknown}")
    with tempfile.TemporaryDirectory(prefix="lg-trace-") as tmp:
        d = Path(tmp)
        shutil.copy(SPEC_DIR / "LedgerGuardTCC.tla", d / "LedgerGuardTCC.tla")
        (d / "LedgerGuardTCCTrace.tla").write_text(render_module(tokens), encoding="utf-8")
        (d / "LedgerGuardTCCTrace.cfg").write_text(_CFG, encoding="utf-8")
        proc = subprocess.run(
            ["java", "-XX:+UseSerialGC", "-cp", str(jar), "tlc2.TLC", "-workers", "1",
             "-deadlock", "-metadir", str(d / "states"), "-config",
             str(d / "LedgerGuardTCCTrace.cfg"), str(d / "LedgerGuardTCCTrace.tla")],
            capture_output=True, text=True, timeout=timeout_s, cwd=d,
        )
    out = proc.stdout + proc.stderr
    if proc.returncode == 12 and "NotAccepted is violated" in out:
        return True
    if proc.returncode == 0 and "No error has been found" in out:
        return False
    raise RuntimeError(f"unexpected TLC result (exit {proc.returncode}):\n{out[-1500:]}")
