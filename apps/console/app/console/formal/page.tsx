'use client';

import React from 'react';

export default function FormalModelPage() {
  const properties = [
    { name: 'NotBothSettledAndCancelled', kind: 'Safety', status: 'VERIFIED' },
    { name: 'NoConfirmAfterCancel', kind: 'Safety', status: 'VERIFIED' },
    { name: 'NoCancelAfterCommit', kind: 'Safety', status: 'VERIFIED' },
    { name: 'NoOverspend', kind: 'Safety', status: 'VERIFIED' },
    { name: 'ConservationOfFunds', kind: 'Safety', status: 'VERIFIED' },
    { name: 'DecisionMonotonicity', kind: 'Temporal', status: 'VERIFIED' },
    { name: 'CommittedEventuallySettles', kind: 'Liveness', status: 'VERIFIED' },
    { name: 'CancelledEventuallyReleases', kind: 'Liveness', status: 'VERIFIED' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
          TLA+ Formal Protocol Verification
        </h1>
        <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
          Bounded TLC model checking of formal/tla/LedgerGuardTCC.tla (pinned tla2tools v1.8.0: 902 states, 189 distinct states, depth 10).
        </p>
      </header>
      <section style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.75rem' }}>
        {properties.map((p) => (
          <div key={p.name} style={{ padding: '0.75rem', borderRadius: '14px', background: 'rgba(2, 6, 23, 0.5)', border: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#E2E8F0' }}>{p.name}</div>
              <div style={{ fontSize: '0.7rem', color: '#64748B' }}>{p.kind}</div>
            </div>
            <span style={{ padding: '0.2rem 0.55rem', borderRadius: '9999px', fontSize: '0.6875rem', fontWeight: 700, background: 'rgba(5,150,105,0.2)', color: '#34D399' }}>
              {p.status}
            </span>
          </div>
        ))}
      </section>
    </div>
  );
}
