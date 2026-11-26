'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../lib/auth-context';

interface DisputeItem {
  dispute_id: string;
  transfer_id: string;
  state: string;
  amount_minor: number;
  reason_code: string;
  created_by: string;
  decided_by?: string | null;
  compensation_transfer_id?: string | null;
  created_at: string;
}

export default function DisputesPage() {
  const { csrfToken } = useAuth();
  const [disputes, setDisputes] = useState<DisputeItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadDisputes = async () => {
    const res = await fetch('/api/operator/disputes', { cache: 'no-store' });
    if (res.ok) {
      setDisputes(await res.json());
    }
  };

  useEffect(() => {
    loadDisputes();
  }, []);

  const handleTransition = async (disputeId: string, toState: string) => {
    setError(null);
    const res = await fetch(`/api/operator/disputes/${disputeId}/transition`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      },
      body: JSON.stringify({ to_state: toState }),
    });
    if (!res.ok) {
      const b = await res.json().catch(() => null);
      setError(b?.detail || 'Transition failed');
      return;
    }
    loadDisputes();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
          Reversals, Refunds & Chargeback Disputes
        </h1>
        <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
          Compensating financial workflows preserving immutable journal history (invariant I12).
        </p>
      </header>

      {error && <div role="alert" style={{ padding: '0.875rem', borderRadius: '14px', background: 'rgba(244,63,94,0.14)', color: '#FDA4AF' }}>{error}</div>}

      {disputes.length === 0 ? (
        <div style={{ padding: '1.5rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', color: '#94A3B8' }}>
          No active or historical disputes recorded yet.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {disputes.map((d) => (
            <section key={d.dispute_id} style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: '#F8FAFC' }}>{d.dispute_id}</div>
                <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>
                  Transfer: {d.transfer_id} • {d.amount_minor} paise • Reason: {d.reason_code}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <span style={{ padding: '0.25rem 0.65rem', borderRadius: '9999px', fontSize: '0.72rem', fontWeight: 700, background: 'rgba(59, 130, 246, 0.2)', color: '#93C5FD' }}>
                  {d.state}
                </span>
                {d.state === 'OPENED' && (
                  <button type="button" onClick={() => handleTransition(d.dispute_id, 'UNDER_REVIEW')} style={{ padding: '0.4rem 0.75rem', borderRadius: '10px', background: 'rgba(255,255,255,0.08)', color: '#E2E8F0', border: 'none', cursor: 'pointer', fontSize: '0.75rem' }}>
                    Review
                  </button>
                )}
                {d.state === 'UNDER_REVIEW' && (
                  <button type="button" onClick={() => handleTransition(d.dispute_id, 'APPROVED')} style={{ padding: '0.4rem 0.75rem', borderRadius: '10px', background: 'rgba(16,185,129,0.2)', color: '#34D399', border: 'none', cursor: 'pointer', fontSize: '0.75rem' }}>
                    Approve & Compensate
                  </button>
                )}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
