------------------------- MODULE LedgerGuardTCCMulti -------------------------
\* Several concurrent TCC transfers that share ONE source account and ONE
\* destination account. Complements LedgerGuardTCC.tla (single transfer, with
\* message loss and crashes): this model abstracts the message layer and instead
\* checks the cross-transfer property that matters for money safety - holds taken
\* by concurrent transfers never over-commit the shared source balance.
\*
\* IgnoreHolds = TRUE models a defective Try phase that checks only the posted
\* balance. TLC must find an overspend counterexample for it.
EXTENDS Integers, FiniteSets

CONSTANTS
    Transfers,      \* set of concurrent transfer identifiers
    InitSourceBal,
    InitDestBal,
    Amount,         \* each transfer moves this amount from the shared source
    IgnoreHolds     \* BOOLEAN: defective funds check when TRUE

VARIABLES
    dec,        \* [Transfers -> {"NONE", "COMMIT", "CANCEL"}]   durable decision
    srcSt,      \* [Transfers -> {"NONE", "PREPARED", "CONFIRMED", "RELEASED"}]
    dstSt,      \* [Transfers -> {"NONE", "PREPARED", "CONFIRMED", "RELEASED"}]
    srcBal,     \* posted balance of the shared source account
    dstBal,     \* posted balance of the shared destination account
    clearing    \* net cross-ledger clearing delta (L2 - L1)

vars == <<dec, srcSt, dstSt, srcBal, dstBal, clearing>>

PartState == {"NONE", "PREPARED", "CONFIRMED", "RELEASED"}

Holds == Amount * Cardinality({t \in Transfers : srcSt[t] = "PREPARED"})

Funded == IF IgnoreHolds THEN srcBal >= Amount ELSE srcBal - Holds >= Amount

Settled(t)   == dstSt[t] = "CONFIRMED"
Cancelled(t) == dec[t] = "CANCEL" /\ srcSt[t] = "RELEASED" /\ dstSt[t] = "RELEASED"
Done(t)      == Settled(t) \/ Cancelled(t)

TypeOK ==
    /\ dec \in [Transfers -> {"NONE", "COMMIT", "CANCEL"}]
    /\ srcSt \in [Transfers -> PartState]
    /\ dstSt \in [Transfers -> PartState]
    /\ srcBal \in Int /\ dstBal \in Int /\ clearing \in Int

Init ==
    /\ dec = [t \in Transfers |-> "NONE"]
    /\ srcSt = [t \in Transfers |-> "NONE"]
    /\ dstSt = [t \in Transfers |-> "NONE"]
    /\ srcBal = InitSourceBal
    /\ dstBal = InitDestBal
    /\ clearing = 0

\* Try: place a hold on the shared source if the AVAILABLE balance covers it.
SrcPrepare(t) ==
    /\ dec[t] = "NONE" /\ srcSt[t] = "NONE"
    /\ Funded
    /\ srcSt' = [srcSt EXCEPT ![t] = "PREPARED"]
    /\ UNCHANGED <<dec, dstSt, srcBal, dstBal, clearing>>

\* Insufficient available funds: the coordinator durably decides CANCEL.
SrcReject(t) ==
    /\ dec[t] = "NONE" /\ srcSt[t] = "NONE"
    /\ ~Funded
    /\ dec' = [dec EXCEPT ![t] = "CANCEL"]
    /\ UNCHANGED <<srcSt, dstSt, srcBal, dstBal, clearing>>

DstPrepare(t) ==
    /\ dec[t] = "NONE" /\ srcSt[t] = "PREPARED" /\ dstSt[t] = "NONE"
    /\ dstSt' = [dstSt EXCEPT ![t] = "PREPARED"]
    /\ UNCHANGED <<dec, srcSt, srcBal, dstBal, clearing>>

DecideCommit(t) ==
    /\ dec[t] = "NONE" /\ srcSt[t] = "PREPARED" /\ dstSt[t] = "PREPARED"
    /\ dec' = [dec EXCEPT ![t] = "COMMIT"]
    /\ UNCHANGED <<srcSt, dstSt, srcBal, dstBal, clearing>>

\* A CANCEL decision is only possible while no COMMIT decision exists.
DecideCancel(t) ==
    /\ dec[t] = "NONE"
    /\ dec' = [dec EXCEPT ![t] = "CANCEL"]
    /\ UNCHANGED <<srcSt, dstSt, srcBal, dstBal, clearing>>

SrcConfirm(t) ==
    /\ dec[t] = "COMMIT" /\ srcSt[t] = "PREPARED"
    /\ srcSt' = [srcSt EXCEPT ![t] = "CONFIRMED"]
    /\ srcBal' = srcBal - Amount
    /\ clearing' = clearing - Amount
    /\ UNCHANGED <<dec, dstSt, dstBal>>

DstConfirm(t) ==
    /\ dec[t] = "COMMIT" /\ srcSt[t] = "CONFIRMED" /\ dstSt[t] = "PREPARED"
    /\ dstSt' = [dstSt EXCEPT ![t] = "CONFIRMED"]
    /\ dstBal' = dstBal + Amount
    /\ clearing' = clearing + Amount
    /\ UNCHANGED <<dec, srcSt, srcBal>>

\* Cancel handling releases the hold (PREPARED -> RELEASED) or tombstones (NONE -> RELEASED).
SrcRelease(t) ==
    /\ dec[t] = "CANCEL" /\ srcSt[t] \in {"NONE", "PREPARED"}
    /\ srcSt' = [srcSt EXCEPT ![t] = "RELEASED"]
    /\ UNCHANGED <<dec, dstSt, srcBal, dstBal, clearing>>

DstRelease(t) ==
    /\ dec[t] = "CANCEL" /\ dstSt[t] \in {"NONE", "PREPARED"}
    /\ dstSt' = [dstSt EXCEPT ![t] = "RELEASED"]
    /\ UNCHANGED <<dec, srcSt, srcBal, dstBal, clearing>>

AllDone == \A t \in Transfers : Done(t)

Next ==
    \/ \E t \in Transfers :
          \/ SrcPrepare(t) \/ SrcReject(t) \/ DstPrepare(t)
          \/ DecideCommit(t) \/ DecideCancel(t)
          \/ SrcConfirm(t) \/ DstConfirm(t)
          \/ SrcRelease(t) \/ DstRelease(t)
    \/ (AllDone /\ UNCHANGED vars)

Fairness ==
    /\ WF_vars(\E t \in Transfers : SrcPrepare(t) \/ SrcReject(t))
    /\ WF_vars(\E t \in Transfers : DstPrepare(t))
    /\ WF_vars(\E t \in Transfers : DecideCommit(t))
    /\ WF_vars(\E t \in Transfers : SrcConfirm(t))
    /\ WF_vars(\E t \in Transfers : DstConfirm(t))
    /\ WF_vars(\E t \in Transfers : SrcRelease(t))
    /\ WF_vars(\E t \in Transfers : DstRelease(t))

Spec == Init /\ [][Next]_vars /\ Fairness

\* -------------------- SAFETY --------------------

\* Holds placed by concurrent transfers never exceed the posted balance.
NoOverspend == srcBal - Holds >= 0

ConservationOfFunds ==
    srcBal + dstBal - clearing = InitSourceBal + InitDestBal

\* A transfer is never both committed and cancelled.
CommitCancelExclusive ==
    \A t \in Transfers :
        /\ dec[t] = "CANCEL" => (srcSt[t] # "CONFIRMED" /\ dstSt[t] # "CONFIRMED")
        /\ dec[t] = "COMMIT" => (srcSt[t] # "RELEASED" /\ dstSt[t] # "RELEASED")

\* Once every transfer finished, cross-ledger clearing nets to zero and no hold remains.
FinishedClearingZero == AllDone => (clearing = 0 /\ Holds = 0)

\* Money cannot be created: settled transfers never exceed the source funds.
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
