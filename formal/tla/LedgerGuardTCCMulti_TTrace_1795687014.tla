---- MODULE LedgerGuardTCCMulti_TTrace_1795687014 ----
EXTENDS Sequences, TLCExt, Toolbox, Naturals, TLC, LedgerGuardTCCMulti_TEConstants, LedgerGuardTCCMulti

_expression ==
    LET LedgerGuardTCCMulti_TEExpression == INSTANCE LedgerGuardTCCMulti_TEExpression
    IN LedgerGuardTCCMulti_TEExpression!expression
----

_trace ==
    LET LedgerGuardTCCMulti_TETrace == INSTANCE LedgerGuardTCCMulti_TETrace
    IN LedgerGuardTCCMulti_TETrace!trace
----

_inv ==
    ~(
        TLCGet("level") = Len(_TETrace)
        /\
        dstSt = ((t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"))
        /\
        dec = ((t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"))
        /\
        dstBal = (0)
        /\
        srcBal = (10)
        /\
        srcSt = ((t1 :> "PREPARED" @@ t2 :> "PREPARED" @@ t3 :> "PREPARED"))
        /\
        clearing = (0)
    )
----

_init ==
    /\ dec = _TETrace[1].dec
    /\ clearing = _TETrace[1].clearing
    /\ srcBal = _TETrace[1].srcBal
    /\ dstBal = _TETrace[1].dstBal
    /\ dstSt = _TETrace[1].dstSt
    /\ srcSt = _TETrace[1].srcSt
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
        /\ dec  = _TETrace[i].dec
        /\ dec' = _TETrace[j].dec
        /\ clearing  = _TETrace[i].clearing
        /\ clearing' = _TETrace[j].clearing
        /\ srcBal  = _TETrace[i].srcBal
        /\ srcBal' = _TETrace[j].srcBal
        /\ dstBal  = _TETrace[i].dstBal
        /\ dstBal' = _TETrace[j].dstBal
        /\ dstSt  = _TETrace[i].dstSt
        /\ dstSt' = _TETrace[j].dstSt
        /\ srcSt  = _TETrace[i].srcSt
        /\ srcSt' = _TETrace[j].srcSt

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("LedgerGuardTCCMulti_TTrace_1795687014.json", _TETrace)

=============================================================================

 Note that you can extract this module `LedgerGuardTCCMulti_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `LedgerGuardTCCMulti_TEExpression.tla` file takes precedence 
  over the module `LedgerGuardTCCMulti_TEExpression` below).

---- MODULE LedgerGuardTCCMulti_TEExpression ----
EXTENDS Sequences, TLCExt, Toolbox, Naturals, TLC, LedgerGuardTCCMulti_TEConstants, LedgerGuardTCCMulti

expression == 
    [
        \* To hide variables of the `LedgerGuardTCCMulti` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        dec |-> dec
        ,clearing |-> clearing
        ,srcBal |-> srcBal
        ,dstBal |-> dstBal
        ,dstSt |-> dstSt
        ,srcSt |-> srcSt
        
        \* Put additional constant-, state-, and action-level expressions here:
        \* ,_stateNumber |-> _TEPosition
        \* ,_decUnchanged |-> dec = dec'
        
        \* Format the `dec` variable as Json value.
        \* ,_decJson |->
        \*     LET J == INSTANCE Json
        \*     IN J!ToJson(dec)
        
        \* Lastly, you may build expressions over arbitrary sets of states by
        \* leveraging the _TETrace operator.  For example, this is how to
        \* count the number of times a spec variable changed up to the current
        \* state in the trace.
        \* ,_decModCount |->
        \*     LET F[s \in DOMAIN _TETrace] ==
        \*         IF s = 1 THEN 0
        \*         ELSE IF _TETrace[s].dec # _TETrace[s-1].dec
        \*             THEN 1 + F[s-1] ELSE F[s-1]
        \*     IN F[_TEPosition - 1]
    ]

=============================================================================



Parsing and semantic processing can take forever if the trace below is long.
 In this case, it is advised to uncomment the module below to deserialize the
 trace from a generated binary file.

\*
\*---- MODULE LedgerGuardTCCMulti_TETrace ----
\*EXTENDS IOUtils, TLC, LedgerGuardTCCMulti_TEConstants, LedgerGuardTCCMulti
\*
\*trace == IODeserialize("LedgerGuardTCCMulti_TTrace_1795687014.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE LedgerGuardTCCMulti_TETrace ----
EXTENDS TLC, LedgerGuardTCCMulti_TEConstants, LedgerGuardTCCMulti

trace == 
    <<
    ([dstSt |-> (t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"),dec |-> (t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"),dstBal |-> 0,srcBal |-> 10,srcSt |-> (t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"),clearing |-> 0]),
    ([dstSt |-> (t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"),dec |-> (t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"),dstBal |-> 0,srcBal |-> 10,srcSt |-> (t1 :> "PREPARED" @@ t2 :> "NONE" @@ t3 :> "NONE"),clearing |-> 0]),
    ([dstSt |-> (t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"),dec |-> (t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"),dstBal |-> 0,srcBal |-> 10,srcSt |-> (t1 :> "PREPARED" @@ t2 :> "PREPARED" @@ t3 :> "NONE"),clearing |-> 0]),
    ([dstSt |-> (t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"),dec |-> (t1 :> "NONE" @@ t2 :> "NONE" @@ t3 :> "NONE"),dstBal |-> 0,srcBal |-> 10,srcSt |-> (t1 :> "PREPARED" @@ t2 :> "PREPARED" @@ t3 :> "PREPARED"),clearing |-> 0])
    >>
----


=============================================================================

---- MODULE LedgerGuardTCCMulti_TEConstants ----
EXTENDS LedgerGuardTCCMulti

CONSTANTS t1, t2, t3

=============================================================================

---- CONFIG LedgerGuardTCCMulti_TTrace_1795687014 ----
CONSTANTS
    t1 = t1
    t2 = t2
    t3 = t3
    Transfers = { t1 , t2 , t3 }
    InitSourceBal = 10
    InitDestBal = 0
    Amount = 4
    IgnoreHolds = TRUE
    t1 = t1
    t3 = t3
    t2 = t2

INVARIANT
    _inv

CHECK_DEADLOCK
    \* CHECK_DEADLOCK off because of PROPERTY or INVARIANT above.
    FALSE

INIT
    _init

NEXT
    _next

CONSTANT
    _TETrace <- _trace

ALIAS
    _expression
=============================================================================
\* Generated on Thu Nov 26 15:26:54 IST 2026