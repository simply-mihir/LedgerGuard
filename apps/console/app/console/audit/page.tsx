'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../lib/auth-context';

interface LedgerChainReport {
  ledger_id: string;
  status: string;
  verified_range: { first: number; last: number };
  entries_checked: number;
  first_broken_sequence?: number | null;
  expected_hash?: string | null;
  observed_hash?: string | null;
  reason: string;
}

interface AllLedgersResponse {
  status: string;
  ledgers: Record<string, LedgerChainReport>;
}

export default function AuditIntegrityPage() {
  const { csrfToken } = useAuth();
  const [data, setData] = useState<AllLedgersResponse | null>(null);
  const [checkpointMsg, setCheckpointMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadVerification = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/operator/audit/verify', { cache: 'no-store' });
      if (res.ok) {
        setData(await res.json());
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVerification();
  }, []);

  const handleCreateCheckpoint = async (ledgerId: string) => {
    setCheckpointMsg(null);
    const res = await fetch(`/api/operator/audit/checkpoint?ledger_id=${ledgerId}`, {
      method: 'POST',
      headers: {
        ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      },
    });
    if (res.ok) {
      const cp = await res.json();
      setCheckpointMsg(`Checkpoint ${cp.checkpoint_id} attested for ${ledgerId} (seq ${cp.first_sequence}..${cp.last_sequence}, root ${cp.merkle_root.slice(0, 16)}...)`);
    } else {
      const err = await res.json().catch(() => null);
      setCheckpointMsg(err?.detail || 'Checkpoint creation failed');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
            Tamper-Evident Audit Integrity
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
            Canonical SHA-256 journal hash chains and cross-boundary Merkle checkpoint attestations.
          </p>
        </div>
        <button
          type="button"
          onClick={loadVerification}
          disabled={loading}
          style={{
            padding: '0.6rem 1.1rem',
            borderRadius: '14px',
            background: 'linear-gradient(135deg, #2563EB, #1D4ED8)',
            border: '1px solid rgba(96, 165, 250, 0.5)',
            color: '#FFFFFF',
            fontWeight: 600,
            fontSize: '0.8125rem',
            cursor: 'pointer',
          }}
        >
          {loading ? 'Verifying...' : 'Verify All Ledgers'}
        </button>
      </header>

      {checkpointMsg && (
        <div style={{ padding: '0.875rem 1rem', borderRadius: '14px', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#6EE7B7', fontSize: '0.8125rem' }}>
          {checkpointMsg}
        </div>
      )}

      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem' }}>
          {Object.values(data.ledgers).map((rep) => (
            <section
              key={rep.ledger_id}
              style={{
                padding: '1.25rem',
                borderRadius: '24px',
                background: 'rgba(15, 23, 42, 0.72)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#F8FAFC' }}>{rep.ledger_id}</h2>
                <span
                  style={{
                    padding: '0.2rem 0.6rem',
                    borderRadius: '9999px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    background: rep.status === 'PASS' ? 'rgba(5, 150, 105, 0.2)' : 'rgba(244, 63, 94, 0.2)',
                    color: rep.status === 'PASS' ? '#34D399' : '#FDA4AF',
                  }}
                >
                  {rep.status}
                </span>
              </div>
              <div style={{ fontSize: '0.8125rem', color: '#94A3B8' }}>
                Verified range: seq {rep.verified_range.first}..{rep.verified_range.last} ({rep.entries_checked} entries)
              </div>
              <div style={{ fontSize: '0.8125rem', color: '#CBD5E1' }}>{rep.reason}</div>
              {rep.first_broken_sequence && (
                <div style={{ fontSize: '0.75rem', color: '#FDA4AF', fontFamily: 'var(--font-mono)' }}>
                  Broken at seq {rep.first_broken_sequence}
                </div>
              )}
              <button
                type="button"
                onClick={() => handleCreateCheckpoint(rep.ledger_id)}
                style={{
                  marginTop: '0.25rem',
                  padding: '0.5rem 0.9rem',
                  borderRadius: '12px',
                  background: 'rgba(255, 255, 255, 0.06)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#E2E8F0',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  alignSelf: 'flex-start',
                }}
              >
                Create & Attest Checkpoint
              </button>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
