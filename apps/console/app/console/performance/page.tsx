'use client';

import React from 'react';

export default function PerformanceEvidencePage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
          Concurrency & Performance Evidence
        </h1>
        <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
          12-profile reproducible study with fixed seeds, warmup windows, and raw CSV/JSON/SVG artifacts in docs/performance/.
        </p>
      </header>
      <section style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', color: '#CBD5E1', fontSize: '0.875rem', lineHeight: 1.6 }}>
        <p>Run the reproducible benchmark suite locally:</p>
        <pre style={{ marginTop: '0.75rem', padding: '0.85rem', borderRadius: '12px', background: 'rgba(2, 6, 23, 0.7)', fontFamily: 'var(--font-mono)', fontSize: '0.78rem', overflowX: 'auto' }}>
          uv run python scripts/run_v2_perf_study.py --smoke
        </pre>
        <p style={{ marginTop: '0.75rem', color: '#94A3B8' }}>
          Outputs raw_results.json, raw_results.csv, latency_comparison.svg, and v2_baseline.md.
        </p>
      </section>
    </div>
  );
}
