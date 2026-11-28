----------------------- MODULE LedgerGuardTCC_broken -----------------------
\* Intentionally broken variant where DecideCancel is allowed even after COMMIT
\* to demonstrate that TLC detects the NoCancelAfterCommit safety violation.
EXTENDS LedgerGuardTCC

BrokenDecideCancel ==
    /\ workerUp
    /\ decision' = "CANCEL"
    /\ txState' = "CANCELLING"
    /\ msgs' = msgs \cup {"SRC_CANCEL", "DST_CANCEL"}
    /\ UNCHANGED <<srcState, dstState, srcBal, srcHold, dstBal, clearingDelta,
                   processedCmds, workerUp, lossCount, crashCount>>

BrokenNext ==
    \/ Next
    \/ BrokenDecideCancel

BrokenSpec == Init /\ [][BrokenNext]_vars
=============================================================================
