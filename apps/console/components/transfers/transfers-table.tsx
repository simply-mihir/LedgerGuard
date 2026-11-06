import React from 'react';
import { TransferItem } from '../../lib/types';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { CopyButton } from '../ui/copy-button';
import { formatDateTime, formatINR, formatRelativeAge, truncateId } from '../../lib/format';

interface TransfersTableProps {
  transfers: TransferItem[];
  onOpenTimeline: (transfer: TransferItem) => void;
  isLoading?: boolean;
}

export function TransfersTable({
  transfers,
  onOpenTimeline,
  isLoading = false,
}: TransfersTableProps) {
  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1rem' }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="skeleton-shimmer"
            style={{
              height: '52px',
              borderRadius: '10px',
              backgroundColor: 'rgba(255, 255, 255, 0.04)',
            }}
          />
        ))}
      </div>
    );
  }

  if (transfers.length === 0) {
    return (
      <div
        style={{
          padding: '3.5rem 1rem',
          textAlign: 'center',
          color: '#64748b',
          fontSize: '0.875rem',
        }}
      >
        No transfers found matching the current search and filter criteria.
      </div>
    );
  }

  return (
    <>
      {/* Desktop Table View */}
      <div className="signal-table-container hidden md:block">
        <table className="signal-table">
          <thead>
            <tr>
              <th>Transfer ID</th>
              <th>Route</th>
              <th style={{ textAlign: 'right' }}>Amount</th>
              <th>State</th>
              <th>Durable Decision</th>
              <th>Attention</th>
              <th>Age</th>
              <th style={{ textAlign: 'center', width: '110px' }}>Lifecycle</th>
            </tr>
          </thead>
          <tbody>
            {transfers.map((t) => {
              const isSettled = t.state === 'SETTLED';
              const isCancelled = t.state === 'CANCELLED';

              return (
                <tr key={t.transfer_id}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      <span className="font-mono" style={{ color: '#0df2a6', fontWeight: 600, fontSize: '0.75rem' }}>
                        {truncateId(t.transfer_id, 8, 4)}
                      </span>
                      <CopyButton text={t.transfer_id} />
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem' }}>
                      <span className="font-mono" style={{ color: '#94a3b8' }}>{t.source_ledger_id}</span>
                      <span style={{ color: '#0df2a6' }}>→</span>
                      <span className="font-mono" style={{ color: '#94a3b8' }}>{t.destination_ledger_id}</span>
                    </div>
                  </td>
                  <td style={{ textAlign: 'right', fontWeight: 700, fontSize: '0.875rem' }}>
                    {formatINR(t.amount_minor)}
                  </td>
                  <td>
                    <Badge
                      variant={isSettled ? 'mint' : isCancelled ? 'rose' : 'amber'}
                      size="sm"
                      dot={true}
                    >
                      {t.state}
                    </Badge>
                  </td>
                  <td>
                    {t.decision ? (
                      <Badge
                        variant={t.decision === 'COMMIT' ? 'mint' : 'rose'}
                        size="sm"
                      >
                        {t.decision}
                      </Badge>
                    ) : (
                      <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Pending</span>
                    )}
                  </td>
                  <td>
                    {t.attention_required ? (
                      <Badge variant="amber" size="sm">
                        ATTENTION
                      </Badge>
                    ) : (
                      <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Automated</span>
                    )}
                  </td>
                  <td style={{ fontSize: '0.75rem', color: '#64748b' }}>
                    {formatRelativeAge(t.created_at)}
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => onOpenTimeline(t)}
                    >
                      Timeline
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile Card View */}
      <div className="md:hidden" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {transfers.map((t) => {
          const isSettled = t.state === 'SETTLED';
          const isCancelled = t.state === 'CANCELLED';

          return (
            <div
              key={t.transfer_id}
              style={{
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px',
                padding: '1rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
              }}
            >
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span className="font-mono" style={{ color: '#0df2a6', fontWeight: 700, fontSize: '0.75rem' }}>
                    {truncateId(t.transfer_id, 8, 4)}
                  </span>
                  <CopyButton text={t.transfer_id} />
                </div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
                  {formatINR(t.amount_minor)}
                </div>
              </div>

              {/* Route & Badges */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span className="font-mono">{t.source_ledger_id}</span>
                  <span style={{ color: '#0df2a6' }}>→</span>
                  <span className="font-mono">{t.destination_ledger_id}</span>
                </div>
                <div style={{ display: 'flex', gap: '0.35rem' }}>
                  <Badge variant={isSettled ? 'mint' : isCancelled ? 'rose' : 'amber'} size="sm">
                    {t.state}
                  </Badge>
                  {t.decision && (
                    <Badge variant={t.decision === 'COMMIT' ? 'mint' : 'rose'} size="sm">
                      {t.decision}
                    </Badge>
                  )}
                </div>
              </div>

              {/* Action */}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onOpenTimeline(t)}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                Inspect TCC Timeline ({formatRelativeAge(t.created_at)})
              </Button>
            </div>
          );
        })}
      </div>
    </>
  );
}
