'use client';

import React, { useEffect, useState } from 'react';

interface ParticipantHealth {
  participant_id: string;
  circuit_state: string;
  failure_count: number;
  in_flight_count: number;
  outbox_depth: number;
  oldest_pending_age_seconds: number;
  p95_latency_ms: number;
  next_probe_at?: string | null;
  operator_explanation: string;
}

export default function ResiliencePage() {
  const [items, setItems] = useState<ParticipantHealth[]>([]);

  const load = async () => {
    const res = await fetch('/api/operator/resilience', { cache: 'no-store' });
    if (res.ok) {
      setItems(await res.json());
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
            Adaptive Backpressure & Circuit State
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
            Per-participant circuit breakers (CLOSED / OPEN / HALF_OPEN), outbox depth, and durable obligation protection.
          </p>
        </div>
        <button type="button" onClick={load} style={{ padding: '0.55rem 1rem', borderRadius: '12px', background: 'rgba(59,130,246,0.16)', border: '1px solid rgba(59,130,246,0.4)', color: '#93C5FD', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer' }}>
          Refresh Health
        </button>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem' }}>
        {items.map((p) => (
          <section key={p.participant_id} style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#F8FAFC' }}>{p.participant_id}</h2>
              <span style={{ padding: '0.2rem 0.6rem', borderRadius: '9999px', fontSize: '0.72rem', fontWeight: 700, background: p.circuit_state === 'CLOSED' ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)', color: p.circuit_state === 'CLOSED' ? '#34D399' : '#FCD34D' }}>
                {p.circuit_state}
              </span>
            </div>
            <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>
              In-flight: {p.in_flight_count} • Outbox depth: {p.outbox_depth} • Oldest obligation: {p.oldest_pending_age_seconds}s
            </div>
            <div style={{ fontSize: '0.8rem', color: '#CBD5E1' }}>{p.operator_explanation}</div>
          </section>
        ))}
      </div>
    </div>
  );
}
