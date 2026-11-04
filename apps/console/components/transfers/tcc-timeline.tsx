import React from 'react';
import { TransferItem, WorkflowEvent } from '../../lib/types';
import { TCC_STAGES } from '../../lib/constants';
import { Badge } from '../ui/badge';
import { formatTime } from '../../lib/format';

interface TccTimelineProps {
  transfer: TransferItem;
  events: WorkflowEvent[];
  isLoading?: boolean;
}

export function TccTimeline({ transfer, events, isLoading = false }: TccTimelineProps) {
  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', padding: '1rem 0' }}>
        {[1, 2, 3, 4, 5, 6, 7].map((i) => (
          <div
            key={i}
            className="skeleton-shimmer"
            style={{
              height: '56px',
              borderRadius: '8px',
              backgroundColor: 'rgba(255, 255, 255, 0.04)',
            }}
          />
        ))}
      </div>
    );
  }

  // Map raw workflow events by matching event_type or ordering
  const isSettled = transfer.state === 'SETTLED';
  const isCancelled = transfer.state === 'CANCELLED';
  const hasDecision = Boolean(transfer.decision);

  // Helper to determine stage status
  const getStageState = (index: number) => {
    // Stage 1: Intent
    if (index === 0) return { status: 'complete', color: '#0df2a6', label: 'COMPLETE' };

    // Stage 2: Source prepare
    if (index === 1) {
      if (events.some((e) => e.event_type.includes('hold') || e.event_type.includes('prepare') || e.event_type.includes('source'))) {
        return { status: 'complete', color: '#0df2a6', label: 'COMPLETE' };
      }
      return transfer.state === 'ACCEPTED' ? { status: 'active', color: '#f59e0b', label: 'ACTIVE' } : { status: 'complete', color: '#0df2a6', label: 'COMPLETE' };
    }

    // Stage 3: Destination prepare
    if (index === 2) {
      if (hasDecision || isSettled || isCancelled) return { status: 'complete', color: '#0df2a6', label: 'COMPLETE' };
      if (transfer.state === 'PREPARING') return { status: 'active', color: '#f59e0b', label: 'ACTIVE' };
      return { status: 'waiting', color: '#64748b', label: 'WAITING' };
    }

    // Stage 4: Durable Decision
    if (index === 3) {
      if (hasDecision) {
        return transfer.decision === 'COMMIT'
          ? { status: 'complete', color: '#0df2a6', label: 'COMMITTED' }
          : { status: 'failed', color: '#f43f5e', label: 'CANCELLED' };
      }
      if (transfer.state === 'PREPARING') return { status: 'active', color: '#f59e0b', label: 'ACTIVE' };
      return { status: 'waiting', color: '#64748b', label: 'WAITING' };
    }

    // Stage 5: Source confirm/cancel
    if (index === 4) {
      if (isSettled || isCancelled) return { status: 'complete', color: '#0df2a6', label: 'CONFIRMED' };
      if (transfer.state === 'COMMITTING' || transfer.state === 'CANCELLING') return { status: 'active', color: '#f59e0b', label: 'ACTIVE' };
      return { status: 'waiting', color: '#64748b', label: 'WAITING' };
    }

    // Stage 6: Destination confirm/cancel
    if (index === 5) {
      if (isSettled || isCancelled) return { status: 'complete', color: '#0df2a6', label: 'CONFIRMED' };
      if (transfer.state === 'COMMITTING') return { status: 'active', color: '#f59e0b', label: 'ACTIVE' };
      return { status: 'waiting', color: '#64748b', label: 'WAITING' };
    }

    // Stage 7: Settlement resolved
    if (index === 6) {
      if (isSettled) return { status: 'complete', color: '#0df2a6', label: 'SETTLED' };
      if (isCancelled) return { status: 'failed', color: '#f43f5e', label: 'CANCELLED' };
      return { status: 'waiting', color: '#64748b', label: 'WAITING' };
    }

    return { status: 'waiting', color: '#64748b', label: 'WAITING' };
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', position: 'relative' }}>
      {TCC_STAGES.map((stage, idx) => {
        const stateInfo = getStageState(idx);
        const matchingEvent = events[idx] || null;
        const isLast = idx === TCC_STAGES.length - 1;

        return (
          <div
            key={stage.id}
            style={{
              display: 'flex',
              gap: '1rem',
              position: 'relative',
              animation: `fade-in 0.25s ease ${idx * 0.04}s both`,
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
              {/* Stage Node Icon */}
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background:
                    stateInfo.status === 'complete'
                      ? 'rgba(13, 242, 166, 0.15)'
                      : stateInfo.status === 'active'
                      ? 'rgba(245, 158, 11, 0.15)'
                      : stateInfo.status === 'failed'
                      ? 'rgba(244, 63, 94, 0.15)'
                      : 'rgba(255, 255, 255, 0.04)',
                  border: `2px solid ${stateInfo.color}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: stateInfo.color,
                  fontSize: '0.6875rem',
                  fontWeight: 700,
                  zIndex: 2,
                }}
              >
                {stateInfo.status === 'complete' ? (
                  '✓'
                ) : stateInfo.status === 'active' ? (
                  <span className="signal-pulse-ring" style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: stateInfo.color }} />
                ) : stateInfo.status === 'failed' ? (
                  '✕'
                ) : (
                  idx + 1
                )}
              </div>

              {/* Connecting Track Line */}
              {!isLast && (
                <div
                  style={{
                    width: '2px',
                    flex: 1,
                    minHeight: '34px',
                    backgroundColor: stateInfo.status === 'complete' ? 'rgba(13, 242, 166, 0.25)' : 'rgba(255, 255, 255, 0.06)',
                    margin: '3px 0',
                  }}
                />
              )}
            </div>

            {/* Stage Content Card */}
            <div
              style={{
                flex: 1,
                background: stateInfo.status === 'active' ? 'rgba(245, 158, 11, 0.05)' : 'rgba(255, 255, 255, 0.02)',
                border: `1px solid ${
                  stateInfo.status === 'active'
                    ? 'rgba(245, 158, 11, 0.25)'
                    : 'rgba(255, 255, 255, 0.06)'
                }`,
                borderRadius: '10px',
                padding: '0.75rem 1rem',
                marginBottom: isLast ? 0 : '0.5rem',
              }}
            >
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#f8fafc' }}>
                    {stage.title}
                  </span>
                  <Badge
                    size="sm"
                    variant={
                      stateInfo.status === 'complete'
                        ? 'mint'
                        : stateInfo.status === 'active'
                        ? 'amber'
                        : stateInfo.status === 'failed'
                        ? 'rose'
                        : 'neutral'
                    }
                  >
                    {stateInfo.label}
                  </Badge>
                </div>

                <span style={{ fontSize: '0.6875rem', color: '#64748b' }}>
                  {matchingEvent ? formatTime(matchingEvent.created_at) : '—'}
                </span>
              </div>

              {/* Protocol Event in Monospace */}
              <div className="font-mono" style={{ fontSize: '0.6875rem', color: '#38bdf8', marginBottom: '0.25rem' }}>
                {stage.protocolEvent}
              </div>

              {/* Description */}
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.4 }}>
                {stage.description}
              </div>

              {/* Matching Event granular details if available */}
              {matchingEvent && matchingEvent.details && Object.keys(matchingEvent.details).length > 0 && (
                <div
                  className="font-mono"
                  style={{
                    marginTop: '0.45rem',
                    padding: '0.35rem 0.55rem',
                    borderRadius: '6px',
                    background: 'rgba(0, 0, 0, 0.35)',
                    fontSize: '0.6875rem',
                    color: '#cbd5e1',
                  }}
                >
                  {Object.entries(matchingEvent.details)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join('  •  ')}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
