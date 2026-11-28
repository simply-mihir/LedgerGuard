'use client';

import React, { useEffect, useState } from 'react';

interface RecoveryExplanation {
  transfer_id: string;
  classification: string;
  current_state: string;
  reason: string;
  safety_implication: string;
  next_action: string;
  responsible_component: string;
  retry_schedule: string;
  blocking_dependency?: string | null;
  operator_action_required: boolean;
  evidence_references: string[];
}

interface RecoveryQueueItem {
  transfer_id: string;
  state: string;
  amount_minor: number;
  currency: string;
  created_at: string;
  explanation: RecoveryExplanation;
}

export default function RecoveryQueuePage() {
  const [queue, setQueue] = useState<RecoveryQueueItem[]>([]);
  const [loading, setLoading] = useState(false);

  const loadQueue = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/operator/recovery/queue', { cache: 'no-store' });
      if (res.ok) {
        setQueue(await res.json());
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
            Explainable Recovery Queue
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
            Deterministic rule-based diagnostics citing authoritative coordinator, hold, and participant states.
          </p>
        </div>
        <button
          type="button"
          onClick={loadQueue}
          disabled={loading}
          style={{
            padding: '0.6rem 1.1rem',
            borderRadius: '14px',
            background: 'rgba(59, 130, 246, 0.16)',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            color: '#93C5FD',
            fontWeight: 600,
            fontSize: '0.8125rem',
            cursor: 'pointer',
          }}
        >
          {loading ? 'Refreshing...' : 'Refresh Queue'}
        </button>
      </header>

      {queue.length === 0 ? (
        <div style={{ padding: '1.5rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', color: '#94A3B8' }}>
          Zero unresolved transfers in the recovery queue. All durable commitments have settled or cancelled cleanly.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {queue.map((item) => (
            <section
              key={item.transfer_id}
              style={{
                padding: '1.25rem',
                borderRadius: '24px',
                background: 'rgba(15, 23, 42, 0.72)',
                border: '1px solid rgba(255,255,255,0.08)',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.6rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: '#F8FAFC' }}>
                  {item.transfer_id}
                </span>
                <span style={{ padding: '0.2rem 0.6rem', borderRadius: '9999px', fontSize: '0.72rem', fontWeight: 700, background: 'rgba(245, 158, 11, 0.2)', color: '#FCD34D' }}>
                  {item.explanation.classification}
                </span>
              </div>
              <div style={{ fontSize: '0.875rem', color: '#E2E8F0' }}>{item.explanation.reason}</div>
              <div style={{ fontSize: '0.8125rem', color: '#93C5FD' }}>
                Safety: {item.explanation.safety_implication}
              </div>
              <div style={{ fontSize: '0.8125rem', color: '#34D399' }}>
                Next Action: {item.explanation.next_action} (Owner: {item.explanation.responsible_component})
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
