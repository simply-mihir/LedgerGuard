'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { TransferItem, WorkflowEvent } from '../../../../lib/types';
import { getTransfers, getTransferTimeline } from '../../../../lib/api';
import { formatINR } from '../../../../lib/format';

const EVENT_DESCRIPTIONS: Record<string, { label: string; stage: string; color: string; desc: string }> = {
  PHASE_PREPARE_STARTED: {
    label: 'Phase Prepare Started',
    stage: 'PHASE 1: TRY / PREPARE',
    color: '#38BDF8',
    desc: 'Coordinator initiates reservation of funds on source ledger and acceptance of intent on destination ledger.',
  },
  SOURCE_PREPARE_REJECTED: {
    label: 'Source Prepare Rejected',
    stage: 'PHASE 1: TRY / PREPARE',
    color: '#F87171',
    desc: 'Source participant rejected hold (insufficient available balance or inactive account status).',
  },
  DESTINATION_PREPARE_REJECTED: {
    label: 'Destination Prepare Rejected',
    stage: 'PHASE 1: TRY / PREPARE',
    color: '#F87171',
    desc: 'Destination participant rejected intent registration.',
  },
  DECISION_MADE: {
    label: 'Decision Computed',
    stage: 'PHASE 2: DURABLE DECISION',
    color: '#F59E0B',
    desc: 'Coordinator determines outcome: COMMIT if both participants prepared; CANCEL if either participant rejected.',
  },
  DECISION_COMMITTED: {
    label: 'Decision Committed to Database',
    stage: 'PHASE 2: DURABLE DECISION (POINT OF NO RETURN)',
    color: '#10B981',
    desc: 'Outcome written to PostgreSQL transfer_decisions table. Once COMMITTED, all participants must recover forward. Funds are never prematurely refunded.',
  },
  SOURCE_CONFIRMED: {
    label: 'Source Participant Confirmed',
    stage: 'PHASE 3: FORWARD CONFIRMATION',
    color: '#38BDF8',
    desc: 'Source ledger outbox worker transitions temporary hold into immutable double-entry journal entry.',
  },
  DESTINATION_CONFIRMED: {
    label: 'Destination Participant Confirmed',
    stage: 'PHASE 3: FORWARD CONFIRMATION',
    color: '#38BDF8',
    desc: 'Destination ledger outbox worker posts credit to recipient account and balancing clearing debit.',
  },
  TRANSFER_SETTLED: {
    label: 'Transfer Settled',
    stage: 'TERMINAL CONVERGENCE',
    color: '#10B981',
    desc: 'Both participants confirmed. Transfer marked SETTLED. Clearing conservation invariant holds: Σ ΔL = ₹0.00.',
  },
  SOURCE_CANCELLED: {
    label: 'Source Hold Released',
    stage: 'PHASE 3: CANCELLATION ROLLBACK',
    color: '#F87171',
    desc: 'Source ledger cancelled hold reservation, returning available balance to sender without journal debit.',
  },
  DESTINATION_CANCELLED: {
    label: 'Destination Intent Discarded',
    stage: 'PHASE 3: CANCELLATION ROLLBACK',
    color: '#F87171',
    desc: 'Destination ledger discarded pending incoming transfer intent.',
  },
  TRANSFER_CANCELLED: {
    label: 'Transfer Cancelled',
    stage: 'TERMINAL CONVERGENCE',
    color: '#F87171',
    desc: 'Transfer closed in CANCELLED terminal state. No funds moved across clearing boundary.',
  },
};

export default function TransferDetailPage() {
  const params = useParams();
  const transferId = params?.transferId as string;

  const [transfer, setTransfer] = useState<TransferItem | null>(null);
  const [timeline, setTimeline] = useState<WorkflowEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedPayloads, setExpandedPayloads] = useState<Record<string, boolean>>({});

  const togglePayload = (id: string) => {
    setExpandedPayloads((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  useEffect(() => {
    if (!transferId) return;

    const loadData = async () => {
      setLoading(true);
      try {
        const [txs, events] = await Promise.all([
          getTransfers(100),
          getTransferTimeline(transferId),
        ]);
        const found = txs.find((t) => t.transfer_id === transferId);
        setTransfer(found || null);
        setTimeline(events || []);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch transfer timeline');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [transferId]);

  return (
    <div className="flex flex-col gap-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center gap-2 text-xs font-mono text-[#94A3B8]">
        <Link href="/console/transfers" className="hover:text-white no-underline text-inherit flex items-center gap-1.5 transition-colors">
          <span>←</span>
          <span>Transfers Explorer</span>
        </Link>
        <span>/</span>
        <span className="text-[#38BDF8]">{transferId}</span>
      </div>

      {/* Transfer Header Card */}
      <div
        style={{
          borderRadius: 'var(--radius-primary, 28px)',
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5)',
          padding: '1.75rem',
        }}
        className="flex flex-col md:flex-row md:items-center justify-between gap-6"
      >
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] shadow-[0_0_8px_rgba(56,189,248,0.6)]" />
            TCC Distributed Lifecycle
          </div>
          <h1 className="text-2xl md:text-3xl font-mono text-white font-bold tracking-tight">
            {transferId}
          </h1>
          <div className="flex flex-wrap items-center gap-3 mt-3 text-xs font-mono text-[#94A3B8]">
            <span>Amount: <strong className="text-white font-bold">{formatINR(transfer?.amount_minor ?? 0)}</strong></span>
            <span>•</span>
            <span className="text-[#38BDF8]">{transfer?.source_ledger_id} → {transfer?.destination_ledger_id}</span>
            <span>•</span>
            <span>Source Acct: <Link href={`/console/accounts/${transfer?.source_account_id}`} className="text-inherit hover:underline">{transfer?.source_account_id.slice(0, 8)}...</Link></span>
            <span>•</span>
            <span>Dest Acct: <Link href={`/console/accounts/${transfer?.destination_account_id}`} className="text-inherit hover:underline">{transfer?.destination_account_id.slice(0, 8)}...</Link></span>
          </div>
        </div>

        {/* State Badges */}
        <div className="flex flex-col items-start md:items-end gap-2 font-mono">
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-[#94A3B8] uppercase">Decision:</span>
            <span
              style={{
                padding: '0.25rem 0.65rem',
                fontSize: '0.6875rem',
                borderRadius: 'var(--radius-pill, 9999px)',
                fontWeight: 700,
                backgroundColor:
                  transfer?.decision === 'COMMIT'
                    ? 'rgba(5, 150, 105, 0.2)'
                    : transfer?.decision === 'CANCEL'
                    ? 'rgba(220, 38, 38, 0.2)'
                    : 'rgba(255, 255, 255, 0.08)',
                color:
                  transfer?.decision === 'COMMIT'
                    ? '#34D399'
                    : transfer?.decision === 'CANCEL'
                    ? '#EF4444'
                    : '#94A3B8',
                border: transfer?.decision === 'COMMIT' ? '1px solid rgba(52, 211, 153, 0.3)' : '1px solid rgba(255, 255, 255, 0.06)',
              }}
            >
              {transfer?.decision || 'PENDING'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-[#94A3B8] uppercase">State:</span>
            <span
              style={{
                padding: '0.25rem 0.65rem',
                fontSize: '0.6875rem',
                borderRadius: 'var(--radius-pill, 9999px)',
                fontWeight: 700,
                backgroundColor:
                  transfer?.state === 'SETTLED'
                    ? 'rgba(5, 150, 105, 0.2)'
                    : transfer?.state === 'CANCELLED'
                    ? 'rgba(220, 38, 38, 0.2)'
                    : 'rgba(245, 158, 11, 0.2)',
                color:
                  transfer?.state === 'SETTLED'
                    ? '#34D399'
                    : transfer?.state === 'CANCELLED'
                    ? '#EF4444'
                    : '#F59E0B',
                border: transfer?.state === 'SETTLED' ? '1px solid rgba(52, 211, 153, 0.3)' : '1px solid rgba(245, 158, 11, 0.3)',
              }}
            >
              {transfer?.state || 'IN_FLIGHT'}
            </span>
          </div>
          {transfer?.attention_required && (
            <span
              style={{
                fontSize: '0.6875rem',
                color: '#F59E0B',
                fontWeight: 700,
                padding: '0.2rem 0.5rem',
                borderRadius: 'var(--radius-pill, 9999px)',
                backgroundColor: 'rgba(245, 158, 11, 0.15)',
              }}
            >
              ⚠ Attention: {transfer.attention_reason}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '1rem 1.25rem',
            borderRadius: 'var(--radius-control, 14px)',
            background: 'rgba(127, 29, 29, 0.3)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#FCA5A5',
            fontSize: '0.75rem',
          }}
        >
          {error}
        </div>
      )}

      {/* Vertical Narrative TCC Event Timeline Container */}
      <div
        style={{
          borderRadius: 'var(--radius-primary, 28px)',
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5)',
          padding: '1.75rem',
        }}
      >
        <div className="pb-4 mb-6 border-b border-white/[0.08] flex items-center justify-between">
          <div>
            <h2 className="text-base font-serif text-white tracking-tight">
              Authoritative Event Timeline
            </h2>
            <p className="text-xs text-[#94A3B8] mt-0.5">
              Sequential workflow events recorded in coordinator &lsquo;workflow_events&rsquo; table. Highlights the durable COMMIT decision boundary.
            </p>
          </div>
          <span
            style={{
              padding: '0.25rem 0.65rem',
              borderRadius: 'var(--radius-pill, 9999px)',
              background: 'rgba(11, 15, 23, 0.6)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6875rem',
              color: '#38BDF8',
            }}
          >
            {timeline.length} Authoritative Milestones
          </span>
        </div>

        <div className="relative pl-8 space-y-6">
          {/* Continuous vertical timeline connector path */}
          {timeline.length > 0 && (
            <div
              style={{
                position: 'absolute',
                top: '12px',
                bottom: '12px',
                left: '11px',
                width: '2px',
                background: 'linear-gradient(to bottom, #38BDF8, #10B981 60%, rgba(255, 255, 255, 0.1))',
                borderRadius: '1px',
              }}
            />
          )}

          {timeline.map((evt, idx) => {
            const meta = EVENT_DESCRIPTIONS[evt.event_type] || {
              label: evt.event_type,
              stage: 'WORKFLOW STAGE',
              color: '#38BDF8',
              desc: 'Authoritative workflow lifecycle event.',
            };
            const isDecisionBoundary = evt.event_type === 'DECISION_COMMITTED';
            const eventKey = evt.event_id || `evt-${idx}`;
            const isPayloadOpen = expandedPayloads[eventKey] ?? false;

            return (
              <div key={eventKey} className="relative group">
                {/* Circular Milestone Node with Glowing Rings */}
                <div
                  style={{
                    position: 'absolute',
                    left: '-28px',
                    top: '14px',
                    width: '16px',
                    height: '16px',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    backgroundColor: '#0F172A',
                    border: `2px solid ${meta.color}`,
                    boxShadow: `0 0 10px ${meta.color}66`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 2,
                  }}
                >
                  <div
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: 'var(--radius-pill, 9999px)',
                      backgroundColor: meta.color,
                    }}
                  />
                </div>

                <div
                  style={{
                    padding: '1.25rem',
                    borderRadius: 'var(--radius-secondary, 20px)',
                    background: isDecisionBoundary
                      ? 'linear-gradient(135deg, rgba(6, 78, 59, 0.35) 0%, rgba(11, 15, 23, 0.85) 100%)'
                      : 'rgba(11, 15, 23, 0.75)',
                    border: isDecisionBoundary
                      ? '1px solid rgba(16, 185, 129, 0.5)'
                      : '1px solid rgba(255, 255, 255, 0.08)',
                    boxShadow: isDecisionBoundary
                      ? '0 0 30px rgba(16, 185, 129, 0.15), 0 10px 25px -5px rgba(0, 0, 0, 0.5)'
                      : '0 10px 25px -5px rgba(0, 0, 0, 0.4)',
                    backdropFilter: 'blur(16px)',
                    WebkitBackdropFilter: 'blur(16px)',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 pb-2 border-b border-white/[0.08]">
                    <div>
                      <span className="text-[10px] font-mono uppercase tracking-wider block font-semibold" style={{ color: meta.color }}>
                        {meta.stage}
                      </span>
                      <h3 className="text-sm font-mono font-bold mt-0.5 text-white flex items-center gap-2">
                        <span>{evt.event_type}</span>
                        {isDecisionBoundary && (
                          <span
                            style={{
                              padding: '0.15rem 0.5rem',
                              borderRadius: 'var(--radius-pill, 9999px)',
                              backgroundColor: 'rgba(16, 185, 129, 0.2)',
                              color: '#34D399',
                              fontSize: '0.625rem',
                              fontWeight: 700,
                              border: '1px solid rgba(16, 185, 129, 0.4)',
                            }}
                          >
                            POINT OF NO RETURN
                          </span>
                        )}
                      </h3>
                    </div>
                    <span className="text-[11px] font-mono text-[#94A3B8]">
                      {new Date(evt.created_at).toLocaleTimeString()} ({new Date(evt.created_at).toISOString()})
                    </span>
                  </div>

                  <p className="text-xs mt-2.5 leading-relaxed text-[#CBD5E1]">
                    {meta.desc}
                  </p>

                  {/* Point of No Return callout */}
                  {isDecisionBoundary && (
                    <div
                      style={{
                        marginTop: '0.75rem',
                        padding: '0.75rem 1rem',
                        borderRadius: 'var(--radius-control, 14px)',
                        background: 'rgba(6, 78, 59, 0.3)',
                        border: '1px solid rgba(16, 185, 129, 0.3)',
                        color: '#A7F3D0',
                        fontSize: '0.75rem',
                        lineHeight: 1.5,
                      }}
                    >
                      <strong className="text-white">Point of No Return:</strong> The coordinator has durably committed this transfer. Even if a crash or network partition occurs immediately after this boundary, the worker orchestrator will forward-recover participants without aborting.
                    </div>
                  )}

                  {/* Optional Details Payload block */}
                  {evt.details && Object.keys(evt.details).length > 0 && (
                    <div style={{ marginTop: '0.75rem' }}>
                      <button
                        onClick={() => togglePayload(eventKey)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#38BDF8',
                          fontSize: '0.6875rem',
                          fontFamily: 'var(--font-mono)',
                          cursor: 'pointer',
                          padding: '0.2rem 0',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.35rem',
                        }}
                      >
                        <span>{isPayloadOpen ? '▼ Hide Event Payload' : '▶ Inspect Event Payload'}</span>
                        <span style={{ color: '#64748B' }}>({Object.keys(evt.details).length} fields)</span>
                      </button>

                      {isPayloadOpen && (
                        <div
                          style={{
                            marginTop: '0.5rem',
                            padding: '0.75rem',
                            borderRadius: 'var(--radius-control, 14px)',
                            border: '1px solid rgba(255, 255, 255, 0.08)',
                            background: 'rgba(15, 23, 42, 0.85)',
                            fontSize: '0.6875rem',
                            fontFamily: 'var(--font-mono)',
                            color: '#94A3B8',
                          }}
                        >
                          <div className="text-[10px] uppercase mb-1 text-[#64748B] font-semibold">Event Payload Details:</div>
                          <pre className="m-0 overflow-x-auto whitespace-pre-wrap text-[#CBD5E1]">
                            {JSON.stringify(evt.details, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {timeline.length === 0 && !loading && (
            <div className="py-8 text-center text-[#64748B] font-mono text-xs">
              No workflow events found for transfer {transferId}.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
