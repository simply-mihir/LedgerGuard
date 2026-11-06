import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { TransferItem } from '../../lib/types';
import { formatINR, truncateId } from '../../lib/format';

interface AttentionQueueCardProps {
  attentionTransfers: TransferItem[];
  onInspectTransfer: (transfer: TransferItem) => void;
}

export function AttentionQueueCard({
  attentionTransfers,
  onInspectTransfer,
}: AttentionQueueCardProps) {
  const hasItems = attentionTransfers.length > 0;

  return (
    <Card accent={hasItems ? 'amber' : 'none'}>
      <CardHeader>
        <div>
          <CardTitle>Operator Attention Queue</CardTitle>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.15rem' }}>
            Workflows flagged for timeout or human audit
          </div>
        </div>
        <Badge variant={hasItems ? 'amber' : 'mint'} size="sm">
          {hasItems ? `${attentionTransfers.length} Action Needed` : 'All Automated'}
        </Badge>
      </CardHeader>

      <CardContent style={{ padding: '1.25rem 1.5rem' }}>
        {hasItems ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {attentionTransfers.map((t) => (
              <div
                key={t.transfer_id}
                style={{
                  background: 'rgba(245, 158, 11, 0.05)',
                  border: '1px solid rgba(245, 158, 11, 0.25)',
                  borderRadius: '10px',
                  padding: '0.85rem 1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '1rem',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="font-mono" style={{ fontSize: '0.8125rem', color: '#fbbf24', fontWeight: 600 }}>
                      {truncateId(t.transfer_id, 10)}
                    </span>
                    <Badge variant="amber" size="sm">
                      {t.state}
                    </Badge>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#f8fafc' }}>
                      {formatINR(t.amount_minor)}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#cbd5e1', marginTop: '0.25rem' }}>
                    Reason: {t.attention_reason || 'In-flight reservation exceeded normal forward SLA'}
                  </div>
                </div>

                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onInspectTransfer(t)}
                >
                  Inspect Timeline
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              padding: '1.75rem 1rem',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: 'rgba(13, 242, 166, 0.12)',
                border: '1px solid rgba(13, 242, 166, 0.28)',
                color: '#0df2a6',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '0.75rem',
                fontSize: '1rem',
              }}
            >
              ✓
            </div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#f8fafc' }}>
              Zero Attention Items Required
            </div>
            <p style={{ fontSize: '0.75rem', color: '#64748b', maxWidth: '360px', marginTop: '0.25rem' }}>
              All two-phase transfers resolved deterministically or recovered forward by background workers.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
