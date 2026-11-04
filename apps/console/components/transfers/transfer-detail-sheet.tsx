import React from 'react';
import { TransferItem, WorkflowEvent } from '../../lib/types';
import { Sheet } from '../ui/sheet';
import { Badge } from '../ui/badge';
import { CopyButton } from '../ui/copy-button';
import { formatDateTime, formatINR, truncateId } from '../../lib/format';
import { TccTimeline } from './tcc-timeline';

interface TransferDetailSheetProps {
  transfer: TransferItem | null;
  onClose: () => void;
  timelineEvents: WorkflowEvent[];
  isLoadingTimeline?: boolean;
}

export function TransferDetailSheet({
  transfer,
  onClose,
  timelineEvents,
  isLoadingTimeline = false,
}: TransferDetailSheetProps) {
  if (!transfer) return null;

  const isSettled = transfer.state === 'SETTLED';
  const isCancelled = transfer.state === 'CANCELLED';

  return (
    <Sheet
      isOpen={Boolean(transfer)}
      onClose={onClose}
      width="640px"
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span>TCC Transfer Lifecycle</span>
          <Badge
            variant={isSettled ? 'mint' : isCancelled ? 'rose' : 'amber'}
            size="sm"
          >
            {transfer.state}
          </Badge>
        </div>
      }
      subtitle={
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <span className="font-mono" style={{ color: '#0df2a6' }}>
            {transfer.transfer_id}
          </span>
          <CopyButton text={transfer.transfer_id} />
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Transfer Header Card */}
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(22, 26, 33, 0.9) 0%, rgba(14, 17, 22, 0.95) 100%)',
            border: '1px solid rgba(255, 255, 255, 0.10)',
            borderRadius: '14px',
            padding: '1.25rem 1.5rem',
            display: 'flex',
            alignItems: 'baseline',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Transfer Amount ({transfer.currency})
            </div>
            <div style={{ fontSize: '2rem', fontWeight: 800, color: '#f8fafc', marginTop: '0.2rem', letterSpacing: '-0.03em' }}>
              {formatINR(transfer.amount_minor)}
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Durable Decision
            </div>
            <div style={{ marginTop: '0.35rem' }}>
              {transfer.decision ? (
                <Badge
                  variant={transfer.decision === 'COMMIT' ? 'mint' : 'rose'}
                  size="md"
                  dot={true}
                >
                  {transfer.decision}
                </Badge>
              ) : (
                <Badge variant="amber" size="md">
                  PENDING DECISION
                </Badge>
              )}
            </div>
          </div>
        </div>

        {/* Route Details Matrix */}
        <div
          style={{
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            borderRadius: '12px',
            padding: '1rem 1.25rem',
            display: 'grid',
            gridTemplateColumns: '1fr auto 1fr',
            alignItems: 'center',
            gap: '1rem',
          }}
        >
          {/* Source Account */}
          <div>
            <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
              Source Origin
            </div>
            <div style={{ marginTop: '0.25rem' }}>
              <Badge variant="blue" size="sm">
                {transfer.source_ledger_id.toUpperCase()}
              </Badge>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.35rem' }}>
              <span className="font-mono" style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                {truncateId(transfer.source_account_id, 8, 4)}
              </span>
              <CopyButton text={transfer.source_account_id} />
            </div>
          </div>

          {/* Arrow */}
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              background: 'rgba(255, 255, 255, 0.05)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#0df2a6',
              fontSize: '1rem',
            }}
          >
            →
          </div>

          {/* Destination Account */}
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
              Destination
            </div>
            <div style={{ marginTop: '0.25rem' }}>
              <Badge variant="neutral" size="sm">
                {transfer.destination_ledger_id.toUpperCase()}
              </Badge>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.4rem', marginTop: '0.35rem' }}>
              <span className="font-mono" style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                {truncateId(transfer.destination_account_id, 8, 4)}
              </span>
              <CopyButton text={transfer.destination_account_id} />
            </div>
          </div>
        </div>

        {/* Attention Callout if flagged */}
        {transfer.attention_required && (
          <div
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              color: '#fbbf24',
              fontSize: '0.8125rem',
            }}
          >
            <strong>Operator Attention Required:</strong>{' '}
            {transfer.attention_reason || 'In-flight reservation exceeded normal forward SLA.'}
          </div>
        )}

        {/* Timestamps strip */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '0.75rem',
            color: '#64748b',
            padding: '0.5rem 0.25rem',
          }}
        >
          <span>Created: {formatDateTime(transfer.created_at)}</span>
          {transfer.decided_at && <span>Decided: {formatDateTime(transfer.decided_at)}</span>}
        </div>

        {/* 7-Stage TCC Vertical Timeline */}
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1rem',
            }}
          >
            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#f8fafc' }}>
              TCC Business Reservation Lifecycle Trace
            </span>
            <span className="font-mono" style={{ fontSize: '0.6875rem', color: '#38bdf8' }}>
              Workflow Audit Trail
            </span>
          </div>

          <TccTimeline
            transfer={transfer}
            events={timelineEvents}
            isLoading={isLoadingTimeline}
          />
        </div>
      </div>
    </Sheet>
  );
}
