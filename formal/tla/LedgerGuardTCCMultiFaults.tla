---------------------- MODULE LedgerGuardTCCMultiFaults ----------------------
\* Closes the gap between the two other models: LedgerGuardTCC.tla has message loss and
\* worker crashes but ONE transfer; LedgerGuardTCCMulti.tla has concurrent transfers on
\* shared accounts but NO message layer. This model has both: several concurrent transfers
\* sharing one source and one destination account, per-transfer re-deliverable messages that
\* can be lost, a worker that can crash and restart, and a recovery action that re-derives
\* the missing message from DURABLE state only (decision + participant states), exactly as
\* the production recovery loop does.
\*
\* Two defects must be caught by TLC (see the *_broken configs):
\*   IgnoreHolds    = TRUE  : Try phase checks the posted balance only (overspend).
\*   UnsafeRecovery = TRUE  : recovery may flip a durable COMMIT into CANCEL after the
\*                            source already confirmed (decision reversal).
EXTENDS Integers, FiniteSets

CONSTANTS
    Transfers,
    InitSourceBal,
    InitDestBal,
    Amount,
    MaxLosses,        \* bounded total message losses
    MaxCrashes,       \* bounded total worker crashes
    IgnoreHolds,
    UnsafeRecovery

VARIABLES
    dec, srcSt, dstSt, srcBal, dstBal, clearing,
    msgs,             \* [Transfers -> SUBSET MsgTypes]  in-flight, re-deliverable
    workerUp, lossCount, crashCount

vars == <<dec, srcSt, dstSt, srcBal, dstBal, clearing, msgs, workerUp, lossCount, crashCount>>

PartState == {"NONE", "PREPARED", "CONFIRMED", "RELEASED"}
MsgTypes == {"SRC_PREPARE", "DST_PREPARE", "SRC_CONFIRM", "DST_CONFIRM", "SRC_CANCEL", "DST_CANCEL"}

Holds == Amount * Cardinality({t \in Transfers : srcSt[t] = "PREPARED"})
Funded == IF IgnoreHolds THEN srcBal >= Amount ELSE srcBal - Holds >= Amount

Settled(t)   == dstSt[t] = "CONFIRMED"
Cancelled(t) == dec[t] = "CANCEL" /\ srcSt[t] = "RELEASED" /\ dstSt[t] = "RELEASED"
Done(t)      == Settled(t) \/ Cancelled(t)
AllDone == \A t \in Transfers : Done(t)

TypeOK ==
    /\ dec \in [Transfers -> {"NONE", "COMMIT", "CANCEL"}]
    /\ srcSt \in [Transfers -> PartState]
    /\ dstSt \in [Transfers -> PartState]
    /\ srcBal \in Int /\ dstBal \in Int /\ clearing \in Int
    /\ msgs \in [Transfers -> SUBSET MsgTypes]
    /\ workerUp \in BOOLEAN
    /\ lossCount \in 0..MaxLosses /\ crashCount \in 0..MaxCrashes

Init ==
    /\ dec = [t \in Transfers |-> "NONE"]
    /\ srcSt = [t \in Transfers |-> "NONE"]
    /\ dstSt = [t \in Transfers |-> "NONE"]
    /\ srcBal = InitSourceBal
    /\ dstBal = InitDestBal
    /\ clearing = 0
    /\ msgs = [t \in Transfers |-> {"SRC_PREPARE"}]
    /\ workerUp = TRUE
    /\ lossCount = 0
    /\ crashCount = 0

Send(t, S) == msgs' = [msgs EXCEPT ![t] = @ \cup S]
Quiet == UNCHANGED <<workerUp, lossCount, crashCount>>

SrcPrepare(t) ==
    /\ workerUp /\ "SRC_PREPARE" \in msgs[t]
    /\ dec[t] = "NONE" /\ srcSt[t] = "NONE" /\ Funded
    /\ srcSt' = [srcSt EXCEPT ![t] = "PREPARED"]
    /\ Send(t, {"DST_PREPARE"})
    /\ UNCHANGED <<dec, dstSt, srcBal, dstBal, clearing>> /\ Quiet

SrcReject(t) ==
    /\ workerUp /\ "SRC_PREPARE" \in msgs[t]
    /\ dec[t] = "NONE" /\ srcSt[t] = "NONE" /\ ~Funded
    /\ dec' = [dec EXCEPT ![t] = "CANCEL"]
    /\ Send(t, {"SRC_CANCEL", "DST_CANCEL"})
    /\ UNCHANGED <<srcSt, dstSt, srcBal, dstBal, clearing>> /\ Quiet

DstPrepare(t) ==
    /\ workerUp /\ "DST_PREPARE" \in msgs[t]
    /\ dec[t] = "NONE" /\ srcSt[t] = "PREPARED" /\ dstSt[t] = "NONE"
    /\ dstSt' = [dstSt EXCEPT ![t] = "PREPARED"]
    /\ UNCHANGED <<dec, srcSt, srcBal, dstBal, clearing, msgs>> /\ Quiet

DecideCommit(t) ==
    /\ workerUp
    /\ dec[t] = "NONE" /\ srcSt[t] = "PREPARED" /\ dstSt[t] = "PREPARED"
    /\ dec' = [dec EXCEPT ![t] = "COMMIT"]
    /\ Send(t, {"SRC_CONFIRM"})
    /\ UNCHANGED <<srcSt, dstSt, srcBal, dstBal, clearing>> /\ Quiet

DecideCancel(t) ==
    /\ workerUp /\ dec[t] = "NONE"
    /\ dec' = [dec EXCEPT ![t] = "CANCEL"]
    /\ Send(t, {"SRC_CANCEL", "DST_CANCEL"})
    /\ UNCHANGED <<srcSt, dstSt, srcBal, dstBal, clearing>> /\ Quiet

SrcConfirm(t) ==
    /\ workerUp /\ "SRC_CONFIRM" \in msgs[t]
    /\ dec[t] = "COMMIT" /\ srcSt[t] = "PREPARED"
    /\ srcSt' = [srcSt EXCEPT ![t] = "CONFIRMED"]
    /\ srcBal' = srcBal - Amount
    /\ clearing' = clearing - Amount
    /\ Send(t, {"DST_CONFIRM"})
    /\ UNCHANGED <<dec, dstSt, dstBal>> /\ Quiet

DstConfirm(t) ==
    /\ workerUp /\ "DST_CONFIRM" \in msgs[t]
    /\ dec[t] = "COMMIT" /\ srcSt[t] = "CONFIRMED" /\ dstSt[t] = "PREPARED"
    /\ dstSt' = [dstSt EXCEPT ![t] = "CONFIRMED"]
    /\ dstBal' = dstBal + Amount
    /\ clearing' = clearing + Amount
    /\ UNCHANGED <<dec, srcSt, srcBal, msgs>> /\ Quiet

SrcRelease(t) ==
    /\ workerUp /\ "SRC_CANCEL" \in msgs[t]
    /\ dec[t] = "CANCEL" /\ srcSt[t] \in {"NONE", "PREPARED"}
    /\ srcSt' = [srcSt EXCEPT ![t] = "RELEASED"]
    /\ UNCHANGED <<dec, dstSt, srcBal, dstBal, clearing, msgs>> /\ Quiet

DstRelease(t) ==
    /\ workerUp /\ "DST_CANCEL" \in msgs[t]
    /\ dec[t] = "CANCEL" /\ dstSt[t] \in {"NONE", "PREPARED"}
    /\ dstSt' = [dstSt EXCEPT ![t] = "RELEASED"]
    /\ UNCHANGED <<dec, srcSt, srcBal, dstBal, clearing, msgs>> /\ Quiet

\* ---- faults ----

WorkerCrash ==
    /\ workerUp /\ crashCount < MaxCrashes
    /\ workerUp' = FALSE /\ crashCount' = crashCount + 1
    /\ UNCHANGED <<dec, srcSt, dstSt, srcBal, dstBal, clearing, msgs, lossCount>>

WorkerRestart ==
    /\ ~workerUp
    /\ workerUp' = TRUE
    /\ UNCHANGED <<dec, srcSt, dstSt, srcBal, dstBal, clearing, msgs, lossCount, crashCount>>

LoseMessage ==
    /\ lossCount < MaxLosses
    /\ \E t \in Transfers : \E m \in msgs[t] :
          msgs' = [msgs EXCEPT ![t] = @ \ {m}]
    /\ lossCount' = lossCount + 1
    /\ UNCHANGED <<dec, srcSt, dstSt, srcBal, dstBal, clearing, workerUp, crashCount>>

\* Recovery: re-send the message the durable state says is missing. Reads only
\* dec / srcSt / dstSt, never the (volatile) message set, except to avoid no-op sends.
NeededMsg(t) ==
    IF dec[t] = "COMMIT" THEN
        IF srcSt[t] # "CONFIRMED" THEN {"SRC_CONFIRM"}
        ELSE IF dstSt[t] # "CONFIRMED" THEN {"DST_CONFIRM"} ELSE {}
    ELSE IF dec[t] = "CANCEL" THEN
        (IF srcSt[t] \in {"NONE", "PREPARED"} THEN {"SRC_CANCEL"} ELSE {})
        \cup (IF dstSt[t] \in {"NONE", "PREPARED"} THEN {"DST_CANCEL"} ELSE {})
    ELSE IF srcSt[t] = "NONE" THEN {"SRC_PREPARE"}
    ELSE IF dstSt[t] = "NONE" THEN {"DST_PREPARE"}
    ELSE {}

Recover(t) ==
    /\ workerUp
    /\ NeededMsg(t) \ msgs[t] # {}
    /\ Send(t, NeededMsg(t))
    /\ UNCHANGED <<dec, srcSt, dstSt, srcBal, dstBal, clearing>> /\ Quiet

\* DEFECT (only when UnsafeRecovery): recovery "gives up" on a committed transfer.
UnsafeRecover(t) ==
    /\ UnsafeRecovery /\ workerUp
    /\ dec[t] = "COMMIT" /\ srcSt[t] = "CONFIRMED"
    /\ dec' = [dec EXCEPT ![t] = "CANCEL"]
    /\ Send(t, {"SRC_CANCEL", "DST_CANCEL"})
    /\ UNCHANGED <<srcSt, dstSt, srcBal, dstBal, clearing>> /\ Quiet

Next ==
    \/ \E t \in Transfers :
          \/ SrcPrepare(t) \/ SrcReject(t) \/ DstPrepare(t)
          \/ DecideCommit(t) \/ DecideCancel(t)
          \/ SrcConfirm(t) \/ DstConfirm(t)
          \/ SrcRelease(t) \/ DstRelease(t)
          \/ Recover(t) \/ UnsafeRecover(t)
    \/ WorkerCrash \/ WorkerRestart \/ LoseMessage
    \/ (AllDone /\ UNCHANGED vars)

Fairness ==
    /\ WF_vars(WorkerRestart)
    /\ WF_vars(\E t \in Transfers : SrcPrepare(t) \/ SrcReject(t))
    /\ WF_vars(\E t \in Transfers : DstPrepare(t))
    /\ WF_vars(\E t \in Transfers : DecideCommit(t))
    /\ WF_vars(\E t \in Transfers : SrcConfirm(t))
    /\ WF_vars(\E t \in Transfers : DstConfirm(t))
    /\ WF_vars(\E t \in Transfers : SrcRelease(t))
    /\ WF_vars(\E t \in Transfers : DstRelease(t))
    /\ WF_vars(\E t \in Transfers : Recover(t))

Spec == Init /\ [][Next]_vars /\ Fairness

\* -------------------- SAFETY --------------------
NoOverspend == srcBal - Holds >= 0
ConservationOfFunds == srcBal + dstBal - clearing = InitSourceBal + InitDestBal
CommitCancelExclusive ==
    \A t \in Transfers :
        /\ dec[t] = "CANCEL" => (srcSt[t] # "CONFIRMED" /\ dstSt[t] # "CONFIRMED")
        /\ dec[t] = "COMMIT" => (srcSt[t] # "RELEASED" /\ dstSt[t] # "RELEASED")
FinishedClearingZero == AllDone => (clearing = 0 /\ Holds = 0)
SettledWithinFunds ==
    Amount * Cardinality({t \in Transfers : Settled(t)}) <= InitSourceBal

DecisionMonotonicity ==
    [][\A t \in Transfers :
          /\ dec[t] = "COMMIT" => dec'[t] = "COMMIT"
          /\ dec[t] = "CANCEL" => dec'[t] = "CANCEL"
          /\ Settled(t) => Settled(t)'
          /\ Cancelled(t) => Cancelled(t)']_vars

\* -------------------- LIVENESS --------------------
EveryTransferTerminates == \A t \in Transfers : <>Done(t)

=============================================================================
