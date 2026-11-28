'use client';

import React, { useState } from 'react';

interface HistoricalProof {
  account_id: string;
  ledger_id: string;
  as_of: string;
  entries_replayed: number;
  holds_active_at_t: number;
  posted_balance_minor: number;
  held_amount_minor: number;
  available_balance_minor: number;
  present_posted_balance_minor?: number | null;
  verification_status: string;
  reason: string;
  included_entries: { journal_id: string; operation_type: string; side: string; amount_minor: number; created_at: string }[];
  excluded_entries: { journal_id: string; operation_type: string; side: string; amount_minor: number; created_at: string }[];
}

export default function HistoricalBalancesPage() {
  const [accountId, setAccountId] = useState('');
  const [ledgerId, setLedgerId] = useState<'ledger-1' | 'ledger-2'>('ledger-1');
  const [asOf, setAsOf] = useState(new Date().toISOString());
  const [proof, setProof] = useState<HistoricalProof | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleQuery = async () => {
    setError(null);
    if (!accountId.trim()) {
      setError('Enter an account UUID.');
      return;
    }
    const res = await fetch(
      `/api/operator/history/accounts/${encodeURIComponent(accountId.trim())}/balance?as_of=${encodeURIComponent(asOf)}&ledger_id=${ledgerId}`,
      { cache: 'no-store' }
    );
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      setError(body?.detail || `Failed (${res.status})`);
      return;
    }
    setProof(await res.json());
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
          As-of-Time Balance Reconstruction
        </h1>
        <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
          Reconstruct historical posted, held, and available balances using checksummed snapshots and deterministic sequence replay.
        </p>
      </header>

      <section style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', alignItems: 'end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.75rem', color: '#94A3B8' }}>
          <span>Account ID (UUID)</span>
          <input value={accountId} onChange={(e) => setAccountId(e.target.value)} placeholder="Account UUID" style={{ padding: '0.55rem 0.75rem', borderRadius: '12px', background: 'rgba(2, 6, 23, 0.6)', border: '1px solid rgba(255,255,255,0.12)', color: '#F8FAFC' }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.75rem', color: '#94A3B8' }}>
          <span>Ledger</span>
          <select value={ledgerId} onChange={(e) => setLedgerId(e.target.value as 'ledger-1' | 'ledger-2')} style={{ padding: '0.55rem 0.75rem', borderRadius: '12px', background: 'rgba(2, 6, 23, 0.6)', border: '1px solid rgba(255,255,255,0.12)', color: '#F8FAFC' }}>
            <option value="ledger-1">ledger-1</option>
            <option value="ledger-2">ledger-2</option>
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.75rem', color: '#94A3B8' }}>
          <span>As-of UTC Timestamp</span>
          <input value={asOf} onChange={(e) => setAsOf(e.target.value)} style={{ padding: '0.55rem 0.75rem', borderRadius: '12px', background: 'rgba(2, 6, 23, 0.6)', border: '1px solid rgba(255,255,255,0.12)', color: '#F8FAFC' }} />
        </label>
        <button type="button" onClick={handleQuery} style={{ padding: '0.65rem 1.25rem', borderRadius: '14px', background: 'linear-gradient(135deg, #2563EB, #1D4ED8)', border: '1px solid rgba(96,165,250,0.5)', color: '#FFF', fontWeight: 600, cursor: 'pointer' }}>
          Reconstruct Balance
        </button>
      </section>

      {error && <div role="alert" style={{ padding: '0.875rem', borderRadius: '14px', background: 'rgba(244,63,94,0.14)', color: '#FDA4AF' }}>{error}</div>}

      {proof && (
        <section style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#F8FAFC' }}>Reconstruction Proof ({proof.verification_status})</h2>
            <span style={{ fontSize: '0.75rem', color: '#34D399' }}>{proof.reason}</span>
          </div>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.875rem', color: '#E2E8F0' }}>
            <span>Posted (as-of): <strong>{proof.posted_balance_minor} paise</strong></span>
            <span>Held (as-of): <strong>{proof.held_amount_minor} paise</strong></span>
            <span>Available (as-of): <strong>{proof.available_balance_minor} paise</strong></span>
            <span>Present Posted: <strong>{proof.present_posted_balance_minor ?? 'N/A'} paise</strong></span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>
            Included entries: {proof.included_entries.length} • Excluded (post-T) entries: {proof.excluded_entries.length}
          </div>
        </section>
      )}
    </div>
  );
}
