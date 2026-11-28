'use client';

import React from 'react';

export default function DisasterRecoveryPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
          Disaster Recovery & Restore Verification
        </h1>
        <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
          Isolated disposable-database backup, destructive loss, pg_restore, forward replay, and post-restore invariant verification.
        </p>
      </header>
      <section style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', color: '#CBD5E1', fontSize: '0.875rem', lineHeight: 1.6 }}>
        <p>Execute the isolated DR drill (requires explicit disposable confirmation):</p>
        <pre style={{ marginTop: '0.75rem', padding: '0.85rem', borderRadius: '12px', background: 'rgba(2, 6, 23, 0.7)', fontFamily: 'var(--font-mono)', fontSize: '0.78rem', overflowX: 'auto' }}>
          ./scripts/demo_disaster_recovery.sh --confirm-disposable
        </pre>
        <p style={{ marginTop: '0.75rem', color: '#94A3B8' }}>
          Measures RPO, RTO, transactions replayed, journal hash chain integrity, Merkle checkpoint attestation, and drained clearing conservation.
        </p>
      </section>
    </div>
  );
}
