import React from 'react';
import { TransferItem, WorkflowEvent } from '../../lib/types';
import { getWorkflowEventDefinition } from '../../lib/constants';
import { Badge } from '../ui/badge';
import { formatDateTime } from '../../lib/format';

interface TccTimelineProps {
  transfer: TransferItem;
  events: WorkflowEvent[];
  isLoading?: boolean;
}

export function TccTimeline({ transfer, events, isLoading = false }: TccTimelineProps) {
  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '0.5rem 0' }}>
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div
            key={i}
            className="skeleton-shimmer"
            style={{
              height: '72px',
              borderRadius: '10px',
              backgroundColor: 'rgba(255, 255, 255, 0.04)',
            }}
          />
        ))}
      </div>
    );
  }

  // Ensure chronological ordering by recorded timestamp
  const sortedEvents = [...events].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  const isTerminal = transfer.state === 'SETTLED' || transfer.state === 'CANCELLED';
  const isSettled = transfer.state === 'SETTLED';
  const isCancelled = transfer.state === 'CANCELLED';
  const hasDecision = Boolean(transfer.decision);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* High-Level TCC Business Lifecycle Progression Bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '0.5rem',
          padding: '0.75rem',
          borderRadius: '10px',
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
        }}
      >
        {/* Phase 1: Try */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.625rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            1. Try (Prepare)
          </div>
          <div style={{ marginTop: '0.25rem' }}>
            <Badge
              size="sm"
              variant={
                hasDecision || isTerminal
                  ? 'mint'
                  : transfer.state === 'PREPARING'
                  ? 'amber'
                  : 'neutral'
              }
            >
              {hasDecision || isTerminal ? 'COMPLETED' : transfer.state === 'PREPARING' ? 'ACTIVE' : 'WAITING'}
            </Badge>
          </div>
        </div>

        {/* Phase 2: Decision */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.625rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            2. Decision
          </div>
          <div style={{ marginTop: '0.25rem' }}>
            <Badge
              size="sm"
              variant={
                transfer.decision === 'COMMIT'
                  ? 'mint'
                  : transfer.decision === 'CANCEL'
                  ? 'rose'
                  : transfer.state === 'PREPARING'
                  ? 'amber'
                  : 'neutral'
              }
            >
              {transfer.decision ? transfer.decision : 'PENDING'}
            </Badge>
          </div>
        </div>

        {/* Phase 3: Confirm / Cancel */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.625rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            3. {transfer.decision === 'CANCEL' ? 'Cancel' : 'Confirm'}
          </div>
          <div style={{ marginTop: '0.25rem' }}>
            <Badge
              size="sm"
              variant={
                isTerminal
                  ? isSettled
                    ? 'mint'
                    : 'rose'
                  : transfer.state === 'COMMITTING' || transfer.state === 'CANCELLING'
                  ? 'amber'
                  : 'neutral'
              }
            >
              {isTerminal
                ? 'APPLIED'
                : transfer.state === 'COMMITTING' || transfer.state === 'CANCELLING'
                ? 'DISPATCHING'
                : 'WAITING'}
            </Badge>
          </div>
        </div>

        {/* Phase 4: Resolution */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.625rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            4. Resolution
          </div>
          <div style={{ marginTop: '0.25rem' }}>
            <Badge
              size="sm"
              variant={isSettled ? 'mint' : isCancelled ? 'rose' : 'neutral'}
            >
              {transfer.state}
            </Badge>
          </div>
        </div>
      </div>

      {/* Recorded Workflow Events Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#f8fafc' }}>
          Recorded Workflow Audit Events
        </span>
        <span className="font-mono" style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>
          {sortedEvents.length} Recorded in DB
        </span>
      </div>

      {/* Empty State */}
      {sortedEvents.length === 0 && (
        <div
          style={{
            padding: '2rem 1rem',
            textAlign: 'center',
            borderRadius: '10px',
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            color: '#94a3b8',
            fontSize: '0.8125rem',
          }}
        >
          No workflow events recorded in coordinator database yet.
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
            Transfer is in {transfer.state} state awaiting orchestrator worker pickup.
          </div>
        </div>
      )}

      {/* Chronological Event Timeline */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', position: 'relative' }}>
        {sortedEvents.map((event, idx) => {
          const meta = getWorkflowEventDefinition(event.event_type);
          const isLast = idx === sortedEvents.length - 1 && isTerminal;
          const isError =
            event.event_type.includes('REJECTED') ||
            event.event_type.includes('CANCEL') ||
            (event.details && (event.details.decision === 'CANCEL' || event.details.status === 'CANCELLED'));

          return (
            <div
              key={event.event_id || `${event.event_type}-${idx}`}
              style={{
                display: 'flex',
                gap: '1rem',
                position: 'relative',
                animation: `fade-in 0.25s ease ${idx * 0.03}s both`,
              }}
            >
              {/* Left track line & indicator */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  width: '28px',
                  flexShrink: 0,
                }}
              >
                {/* Node icon */}
                <div
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    background: isError
                      ? 'rgba(244, 63, 94, 0.15)'
                      : 'rgba(13, 242, 166, 0.15)',
                    border: `2px solid ${isError ? '#f43f5e' : '#0df2a6'}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: isError ? '#f43f5e' : '#0df2a6',
                    fontSize: '0.6875rem',
                    fontWeight: 700,
                    zIndex: 2,
                  }}
                >
                  {isError ? '✕' : '✓'}
                </div>

                {/* Connecting Line */}
                {(!isLast || !isTerminal) && (
                  <div
                    style={{
                      width: '2px',
                      flex: 1,
                      minHeight: '28px',
                      backgroundColor: 'rgba(13, 242, 166, 0.25)',
                      margin: '3px 0',
                    }}
                  />
                )}
              </div>

              {/* Event Content Card */}
              <div
                style={{
                  flex: 1,
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  borderRadius: '10px',
                  padding: '0.75rem 1rem',
                  marginBottom: isLast ? 0 : '0.5rem',
                }}
              >
                {/* Header: Stage title + Recorded badge + Timestamp */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#f8fafc' }}>
                      {meta.stageTitle}
                    </span>
                    <Badge
                      size="sm"
                      variant={isError ? 'rose' : 'mint'}
                    >
                      RECORDED
                    </Badge>
                  </div>

                  <span style={{ fontSize: '0.6875rem', color: '#64748b' }}>
                    {formatDateTime(event.created_at)}
                  </span>
                </div>

                {/* Exact Backend Event Name in Monospace */}
                <div
                  className="font-mono"
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: isError ? '#fb7185' : '#38bdf8',
                    marginBottom: '0.25rem',
                    letterSpacing: '0.02em',
                  }}
                >
                  {event.event_type}
                </div>

                {/* Conceptual Description */}
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.4 }}>
                  {meta.description}
                </div>

                {/* Granular Recorded Event Details */}
                {event.details && Object.keys(event.details).length > 0 && (
                  <div
                    className="font-mono"
                    style={{
                      marginTop: '0.5rem',
                      padding: '0.4rem 0.6rem',
                      borderRadius: '6px',
                      background: 'rgba(0, 0, 0, 0.4)',
                      border: '1px solid rgba(255, 255, 255, 0.04)',
                      fontSize: '0.6875rem',
                      color: '#cbd5e1',
                    }}
                  >
                    {Object.entries(event.details)
                      .map(([k, v]) => `${k}: ${String(v)}`)
                      .join('  •  ')}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Active In-Flight Waiting Stage Indicator */}
        {!isTerminal && (
          <div
            style={{
              display: 'flex',
              gap: '1rem',
              position: 'relative',
              animation: 'fade-in 0.3s ease both',
            }}
          >
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                width: '28px',
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: 'rgba(245, 158, 11, 0.15)',
                  border: '2px solid #f59e0b',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: 2,
                }}
              >
                <span
                  className="signal-pulse-ring"
                  style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#f59e0b' }}
                />
              </div>
            </div>

            <div
              style={{
                flex: 1,
                background: 'rgba(245, 158, 11, 0.04)',
                border: '1px dashed rgba(245, 158, 11, 0.3)',
                borderRadius: '10px',
                padding: '0.75rem 1rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#f8fafc' }}>
                  Next Stage Pending
                </span>
                <Badge size="sm" variant="amber">
                  IN FLIGHT
                </Badge>
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                Transfer state: <span className="font-mono" style={{ color: '#f59e0b' }}>{transfer.state}</span>. Awaiting participant response or autonomous worker completion.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
