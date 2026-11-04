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
        <Link href="/console/transfers" className="hover:text-white no-underline text-inherit">
          &larr; Transfers Explorer
        </Link>
        <span>/</span>
        <span className="text-[#38BDF8]">{transferId}</span>
      </div>

      {/* Transfer Header Card */}
      <div className="p-6 bg-[#0F172A] border border-[#1E293B] flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 bg-[#38BDF8]" />
            TCC Distributed Lifecycle
          </div>
          <h1 className="text-2xl md:text-3xl font-mono text-white font-bold tracking-tight">
            {transferId}
          </h1>
          <div className="flex flex-wrap items-center gap-3 mt-3 text-xs font-mono text-[#94A3B8]">
            <span>Amount: <strong className="text-white font-bold">{formatINR(transfer?.amount_minor ?? 0)}</strong></span>
            <span>&bull;</span>
            <span className="text-[#38BDF8]">{transfer?.source_ledger_id} &rarr; {transfer?.destination_ledger_id}</span>
            <span>&bull;</span>
            <span>Source Acct: <Link href={`/console/accounts/${transfer?.source_account_id}`} className="text-inherit hover:underline">{transfer?.source_account_id.slice(0, 8)}...</Link></span>
            <span>&bull;</span>
            <span>Dest Acct: <Link href={`/console/accounts/${transfer?.destination_account_id}`} className="text-inherit hover:underline">{transfer?.destination_account_id.slice(0, 8)}...</Link></span>
          </div>
        </div>

        {/* State Badges */}
        <div className="flex flex-col items-end gap-2 font-mono">
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-[#64748B] uppercase">Decision:</span>
            <span
              className={`px-2.5 py-1 text-xs font-bold ${
                transfer?.decision === 'COMMIT'
                  ? 'bg-[#064E3B] text-[#10B981]'
                  : transfer?.decision === 'CANCEL'
                  ? 'bg-[#7F1D1D] text-[#EF4444]'
                  : 'bg-[#1E293B] text-[#94A3B8]'
              }`}
            >
              {transfer?.decision || 'PENDING'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-[#64748B] uppercase">State:</span>
            <span
              className={`px-2.5 py-1 text-xs font-bold ${
                transfer?.state === 'SETTLED'
                  ? 'bg-[#064E3B]/60 text-[#10B981]'
                  : transfer?.state === 'CANCELLED'
                  ? 'bg-[#7F1D1D]/60 text-[#EF4444]'
                  : 'bg-[#78350F]/60 text-[#F59E0B]'
              }`}
            >
              {transfer?.state || 'IN_FLIGHT'}
            </span>
          </div>
          {transfer?.attention_required && (
            <span className="text-[11px] text-[#F59E0B] font-bold">
              ⚠ Attention: {transfer.attention_reason}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-[#7F1D1D]/30 border-l-2 border-[#DC2626] text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      {/* Vertical Narrative TCC Event Timeline */}
      <div className="p-6 bg-[#0F172A] border border-[#1E293B]">
        <div className="pb-4 mb-6 border-b border-[#1E293B]">
          <h2 className="text-base font-serif text-white tracking-tight">
            Authoritative Event Timeline
          </h2>
          <p className="text-xs text-[#94A3B8]">
            Sequential workflow events recorded in coordinator &lsquo;workflow_events&rsquo; table. Highlights the durable COMMIT decision boundary.
          </p>
        </div>

        <div className="relative pl-6 border-l-2 border-[#1E293B] space-y-8">
          {timeline.map((evt, idx) => {
            const meta = EVENT_DESCRIPTIONS[evt.event_type] || {
              label: evt.event_type,
              stage: 'WORKFLOW STAGE',
              color: '#38BDF8',
              desc: 'Authoritative workflow lifecycle event.',
            };
            const isDecisionBoundary = evt.event_type === 'DECISION_COMMITTED';

            return (
              <div key={evt.event_id || idx} className="relative group">
                {/* Milestone Node */}
                <div
                  className="absolute -left-[31px] top-1 w-3.5 h-3.5 rounded-none border-2 border-[#0F172A]"
                  style={{ backgroundColor: meta.color }}
                />

                <div
                  className={`p-4 bg-[#0B0F17] border ${isDecisionBoundary ? 'border-[#10B981] shadow-[0_0_20px_rgba(16,185,129,0.15)]' : 'border-[#1E293B]'}`}
                  style={{ backgroundColor: '#0B0F17' }}
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 pb-2 border-b border-[#1E293B]/60">
                    <div>
                      <span className="text-[10px] font-mono uppercase tracking-wider block" style={{ color: meta.color }}>
                        {meta.stage}
                      </span>
                      <h3 className="text-sm font-mono font-bold mt-0.5" style={{ color: '#FFFFFF' }}>
                        {evt.event_type}
                      </h3>
                    </div>
                    <span className="text-[11px] font-mono" style={{ color: '#94A3B8' }}>
                      {new Date(evt.created_at).toLocaleTimeString()} ({new Date(evt.created_at).toISOString()})
                    </span>
                  </div>

                  <p className="text-xs mt-2 leading-relaxed" style={{ color: '#E2E8F0' }}>
                    {meta.desc}
                  </p>

                  {/* Optional Details Payload */}
                  {evt.details && Object.keys(evt.details).length > 0 && (
                    <div
                      className="mt-3 p-2.5 border border-[#1E293B] text-[11px] font-mono"
                      style={{ backgroundColor: '#0F172A', color: '#94A3B8' }}
                    >
                      <div className="text-[10px] uppercase mb-1" style={{ color: '#94A3B8' }}>Event Payload Details:</div>
                      <pre className="m-0 overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(evt.details, null, 2)}
                      </pre>
                    </div>
                  )}

                  {isDecisionBoundary && (
                    <div
                      className="mt-3 p-2 border-l-2 border-[#10B981] text-[11px]"
                      style={{ backgroundColor: 'rgba(6, 78, 59, 0.4)', color: '#A7F3D0' }}
                    >
                      <strong>Point of No Return:</strong> The coordinator has durably committed this transfer. Even if a crash or network partition occurs immediately after this boundary, the worker orchestrator will forward-recover participants without aborting.
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
