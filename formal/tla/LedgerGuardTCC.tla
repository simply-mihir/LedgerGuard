--------------------------- MODULE LedgerGuardTCC ---------------------------
EXTENDS Integers, FiniteSets

CONSTANTS
    InitSourceBal,
    InitDestBal,
    Amount,
    MaxLosses,
    MaxCrashes

VARIABLES
    txState,        \* INIT, SOURCE_PREPARED, DESTINATION_PREPARED, COMMITTING, CANCELLING, SETTLED, CANCELLED
    decision,       \* NONE, COMMIT, CANCEL
    srcState,       \* NONE, PREPARED, CONFIRMED, TOMBSTONE
    dstState,       \* NONE, PREPARED, CONFIRMED, TOMBSTONE
    srcBal,         \* Posted balance on Source Ledger (Ledger 1)
    srcHold,        \* Active hold on Source Ledger
    dstBal,         \* Posted balance on Destination Ledger (Ledger 2)
    clearingDelta,  \* Net cross-ledger clearing delta (L2 - L1)
    msgs,           \* Set of in-flight messages (out-of-order, re-deliverable)
    processedCmds,  \* Participant command inbox for deduplication
    workerUp,       \* TRUE if coordinator/recovery worker is up
    lossCount,      \* Bounded message loss counter
    crashCount      \* Bounded worker crash counter

vars == <<txState, decision, srcState, dstState, srcBal, srcHold, dstBal,
          clearingDelta, msgs, processedCmds, workerUp, lossCount, crashCount>>

TypeOK ==
    /\ txState \in {"INIT", "SOURCE_PREPARED", "DESTINATION_PREPARED",
                    "COMMITTING", "CANCELLING", "SETTLED", "CANCELLED"}
    /\ decision \in {"NONE", "COMMIT", "CANCEL"}
    /\ srcState \in {"NONE", "PREPARED", "CONFIRMED", "TOMBSTONE"}
    /\ dstState \in {"NONE", "PREPARED", "CONFIRMED", "TOMBSTONE"}
    /\ srcBal >= 0
    /\ srcHold >= 0
    /\ dstBal >= 0
    /\ workerUp \in BOOLEAN

Init ==
    /\ txState = "INIT"
    /\ decision = "NONE"
    /\ srcState = "NONE"
    /\ dstState = "NONE"
    /\ srcBal = InitSourceBal
    /\ srcHold = 0
    /\ dstBal = InitDestBal
    /\ clearingDelta = 0
    /\ msgs = {"SRC_PREPARE"}
    /\ processedCmds = {}
    /\ workerUp = TRUE
    /\ lossCount = 0
    /\ crashCount = 0

\* Phase 1a: Source participant processes SRC_PREPARE
SourcePrepare ==
    /\ "SRC_PREPARE" \in msgs
    /\ "SRC_PREPARE" \notin processedCmds
    /\ IF srcState = "TOMBSTONE" THEN
          \* Tombstone blocks delayed prepare with zero hold
          /\ processedCmds' = processedCmds \cup {"SRC_PREPARE"}
          /\ UNCHANGED <<txState, decision, srcState, dstState, srcBal, srcHold,
                       dstBal, clearingDelta, msgs, workerUp, lossCount, crashCount>>
       ELSE IF srcBal - srcHold >= Amount /\ srcState = "NONE" THEN
          /\ srcState' = "PREPARED"
          /\ srcHold' = srcHold + Amount
          /\ txState' = IF txState = "INIT" THEN "SOURCE_PREPARED" ELSE txState
          /\ processedCmds' = processedCmds \cup {"SRC_PREPARE"}
          /\ msgs' = msgs \cup {"DST_PREPARE"}
          /\ UNCHANGED <<decision, dstState, srcBal, dstBal, clearingDelta,
                       workerUp, lossCount, crashCount>>
       ELSE
          /\ processedCmds' = processedCmds \cup {"SRC_PREPARE"}
          /\ UNCHANGED <<txState, decision, srcState, dstState, srcBal, srcHold,
                       dstBal, clearingDelta, msgs, workerUp, lossCount, crashCount>>

\* Duplicate command delivery is a pure no-op due to command_inbox
DuplicateCommandIgnored ==
    \E m \in msgs :
        /\ m \in processedCmds
        /\ UNCHANGED vars

\* Phase 1b: Destination participant processes DST_PREPARE
DestinationPrepare ==
    /\ "DST_PREPARE" \in msgs
    /\ "DST_PREPARE" \notin processedCmds
    /\ IF dstState = "TOMBSTONE" THEN
          /\ processedCmds' = processedCmds \cup {"DST_PREPARE"}
          /\ UNCHANGED <<txState, decision, srcState, dstState, srcBal, srcHold,
                       dstBal, clearingDelta, msgs, workerUp, lossCount, crashCount>>
       ELSE
          /\ dstState' = "PREPARED"
          /\ txState' = IF txState = "SOURCE_PREPARED" THEN "DESTINATION_PREPARED" ELSE txState
          /\ processedCmds' = processedCmds \cup {"DST_PREPARE"}
          /\ UNCHANGED <<decision, srcState, srcBal, srcHold, dstBal, clearingDelta,
                       msgs, workerUp, lossCount, crashCount>>

\* Coordinator durable decision: COMMIT (only if both prepared and no prior CANCEL)
DecideCommit ==
    /\ workerUp
    /\ decision = "NONE"
    /\ srcState = "PREPARED"
    /\ dstState = "PREPARED"
    /\ decision' = "COMMIT"
    /\ txState' = "COMMITTING"
    /\ msgs' = msgs \cup {"SRC_CONFIRM"}
    /\ UNCHANGED <<srcState, dstState, srcBal, srcHold, dstBal, clearingDelta,
                   processedCmds, workerUp, lossCount, crashCount>>

\* Coordinator durable decision: CANCEL (only before COMMIT)
DecideCancel ==
    /\ workerUp
    /\ decision = "NONE"
    /\ txState \in {"INIT", "SOURCE_PREPARED"}
    /\ decision' = "CANCEL"
    /\ txState' = "CANCELLING"
    /\ msgs' = msgs \cup {"SRC_CANCEL", "DST_CANCEL"}
    /\ UNCHANGED <<srcState, dstState, srcBal, srcHold, dstBal, clearingDelta,
                   processedCmds, workerUp, lossCount, crashCount>>

\* Phase 2a: Source confirmation (requires durable COMMIT)
SourceConfirm ==
    /\ "SRC_CONFIRM" \in msgs
    /\ "SRC_CONFIRM" \notin processedCmds
    /\ decision = "COMMIT"
    /\ srcState = "PREPARED"
    /\ srcState' = "CONFIRMED"
    /\ srcHold' = srcHold - Amount
    /\ srcBal' = srcBal - Amount
    /\ clearingDelta' = clearingDelta - Amount
    /\ processedCmds' = processedCmds \cup {"SRC_CONFIRM"}
    /\ msgs' = msgs \cup {"DST_CONFIRM"}
    /\ UNCHANGED <<txState, decision, dstState, dstBal, workerUp, lossCount, crashCount>>

\* Phase 2b: Destination confirmation (requires durable COMMIT and source confirmed)
DestinationConfirm ==
    /\ "DST_CONFIRM" \in msgs
    /\ "DST_CONFIRM" \notin processedCmds
    /\ decision = "COMMIT"
    /\ srcState = "CONFIRMED"
    /\ dstState = "PREPARED"
    /\ dstState' = "CONFIRMED"
    /\ dstBal' = dstBal + Amount
    /\ clearingDelta' = clearingDelta + Amount
    /\ txState' = "SETTLED"
    /\ processedCmds' = processedCmds \cup {"DST_CONFIRM"}
    /\ UNCHANGED <<decision, srcState, srcBal, srcHold, msgs, workerUp, lossCount, crashCount>>

\* Cancel source (writes tombstone if not prepared, releases hold if prepared)
CancelSource ==
    /\ "SRC_CANCEL" \in msgs
    /\ "SRC_CANCEL" \notin processedCmds
    /\ decision = "CANCEL"
    /\ srcHold' = IF srcState = "PREPARED" THEN srcHold - Amount ELSE srcHold
    /\ srcState' = "TOMBSTONE"
    /\ processedCmds' = processedCmds \cup {"SRC_CANCEL"}
    /\ txState' = IF dstState = "TOMBSTONE" THEN "CANCELLED" ELSE txState
    /\ UNCHANGED <<decision, dstState, srcBal, dstBal, clearingDelta,
                   msgs, workerUp, lossCount, crashCount>>

\* Cancel destination (writes tombstone)
CancelDestination ==
    /\ "DST_CANCEL" \in msgs
    /\ "DST_CANCEL" \notin processedCmds
    /\ decision = "CANCEL"
    /\ dstState' = "TOMBSTONE"
    /\ processedCmds' = processedCmds \cup {"DST_CANCEL"}
    /\ txState' = IF srcState = "TOMBSTONE" THEN "CANCELLED" ELSE txState
    /\ UNCHANGED <<decision, srcState, srcBal, srcHold, dstBal, clearingDelta,
                   msgs, workerUp, lossCount, crashCount>>

\* Worker crash and restart
WorkerCrash ==
    /\ workerUp
    /\ crashCount < MaxCrashes
    /\ workerUp' = FALSE
    /\ crashCount' = crashCount + 1
    /\ UNCHANGED <<txState, decision, srcState, dstState, srcBal, srcHold, dstBal,
                   clearingDelta, msgs, processedCmds, lossCount>>

WorkerRecover ==
    /\ ~workerUp
    /\ workerUp' = TRUE
    /\ UNCHANGED <<txState, decision, srcState, dstState, srcBal, srcHold, dstBal,
                   clearingDelta, msgs, processedCmds, lossCount, crashCount>>

\* Bounded message loss
LoseMessage ==
    /\ lossCount < MaxLosses
    /\ \E m \in msgs :
        /\ m \notin processedCmds
        /\ msgs' = msgs \ {m}
        /\ lossCount' = lossCount + 1
        /\ UNCHANGED <<txState, decision, srcState, dstState, srcBal, srcHold, dstBal,
                       clearingDelta, processedCmds, workerUp, crashCount>>

\* Recovery worker retries pending commands based on durable state
RetryPending ==
    /\ workerUp
    /\ IF decision = "COMMIT" /\ txState = "COMMITTING" THEN
          /\ msgs' = msgs \cup (IF srcState # "CONFIRMED" THEN {"SRC_CONFIRM"} ELSE {"DST_CONFIRM"})
          /\ UNCHANGED <<txState, decision, srcState, dstState, srcBal, srcHold, dstBal,
                       clearingDelta, processedCmds, workerUp, lossCount, crashCount>>
       ELSE IF decision = "CANCEL" /\ txState = "CANCELLING" THEN
          /\ msgs' = msgs \cup {"SRC_CANCEL", "DST_CANCEL"}
          /\ UNCHANGED <<txState, decision, srcState, dstState, srcBal, srcHold, dstBal,
                       clearingDelta, processedCmds, workerUp, lossCount, crashCount>>
       ELSE IF decision = "NONE" /\ srcState = "NONE" /\ "SRC_PREPARE" \notin msgs THEN
          /\ msgs' = msgs \cup {"SRC_PREPARE"}
          /\ UNCHANGED <<txState, decision, srcState, dstState, srcBal, srcHold, dstBal,
                       clearingDelta, processedCmds, workerUp, lossCount, crashCount>>
       ELSE IF decision = "NONE" /\ srcState = "PREPARED" /\ dstState = "NONE" /\ "DST_PREPARE" \notin msgs THEN
          /\ msgs' = msgs \cup {"DST_PREPARE"}
          /\ UNCHANGED <<txState, decision, srcState, dstState, srcBal, srcHold, dstBal,
                       clearingDelta, processedCmds, workerUp, lossCount, crashCount>>
       ELSE
          UNCHANGED vars

Next ==
    \/ SourcePrepare
    \/ DestinationPrepare
    \/ DuplicateCommandIgnored
    \/ DecideCommit
    \/ DecideCancel
    \/ SourceConfirm
    \/ DestinationConfirm
    \/ CancelSource
    \/ CancelDestination
    \/ WorkerCrash
    \/ WorkerRecover
    \/ LoseMessage
    \/ RetryPending

Fairness ==
    /\ WF_vars(WorkerRecover)
    /\ WF_vars(RetryPending)
    /\ WF_vars(SourcePrepare)
    /\ WF_vars(DestinationPrepare)
    /\ WF_vars(DecideCommit)
    /\ WF_vars(SourceConfirm)
    /\ WF_vars(DestinationConfirm)
    /\ WF_vars(CancelSource)
    /\ WF_vars(CancelDestination)

Spec == Init /\ [][Next]_vars /\ Fairness

\* -------------------- SAFETY INVARIANTS --------------------

NotBothSettledAndCancelled ==
    ~(txState = "SETTLED" /\ txState = "CANCELLED")
    /\ ~(srcState = "CONFIRMED" /\ srcState = "TOMBSTONE")

NoConfirmAfterCancel ==
    (decision = "CANCEL") => (srcState # "CONFIRMED" /\ dstState # "CONFIRMED" /\ txState # "SETTLED")

NoCancelAfterCommit ==
    (decision = "COMMIT") => (srcState # "TOMBSTONE" /\ dstState # "TOMBSTONE" /\ txState # "CANCELLED")

NoOverspend ==
    (srcBal - srcHold) >= 0

ConservationOfFunds ==
    (srcBal + dstBal - clearingDelta) = (InitSourceBal + InitDestBal)

SettledClearingZero ==
    (txState = "SETTLED") => (clearingDelta = 0 /\ srcHold = 0)

CancelledNoHold ==
    (txState = "CANCELLED") => (srcHold = 0 /\ clearingDelta = 0)

\* Temporal monotonicity: terminal states & durable decisions never revert
DecisionMonotonicity ==
    [][ (decision = "COMMIT" => decision' = "COMMIT")
        /\ (decision = "CANCEL" => decision' = "CANCEL")
        /\ (txState = "SETTLED" => txState' = "SETTLED")
        /\ (txState = "CANCELLED" => txState' = "CANCELLED") ]_vars

\* -------------------- LIVENESS PROPERTIES --------------------

CommittedEventuallySettles ==
    (decision = "COMMIT") ~> (txState = "SETTLED")

CancelledEventuallyReleases ==
    (decision = "CANCEL") ~> (txState = "CANCELLED" /\ srcHold = 0)

EventuallyTerminates ==
    <>(txState \in {"SETTLED", "CANCELLED"})

=============================================================================
