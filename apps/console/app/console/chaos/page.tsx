'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../lib/auth-context';

interface InvariantResult {
  id: string;
  name: string;
  status: string;
  details: string;
}

interface FaultTimelineEntry {
  step: number;
  fault_type: string;
  target: string;
  injected_at: string;
  restored_at?: string;
  recovered: boolean;
  details: string;
}

interface ChaosReport {
  campaign_id: string;
  seed: number;
  git_sha: string;
  status: string;
  operations_attempted: number;
  settled_count: number;
  cancelled_count: number;
  recovered_count: number;
  duplicate_messages_ignored: number;
  fault_counts: Record<string, number>;
  max_unresolved_duration_ms: number;
  recovery_latency_ms: { p50?: number; p95?: number; max?: number };
  invariant_results: InvariantResult[];
  reconciliation_result: {
    status: string;
    coverage: string;
    findings_count: number;
  };
  fault_timeline: FaultTimelineEntry[];
}

export default function ChaosCampaignPage() {
  const { csrfToken } = useAuth();
  const [seed, setSeed] = useState(42);
  const [ops, setOps] = useState(16);
  const [workers, setWorkers] = useState(4);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ChaosReport | null>(null);
  const [history, setHistory] = useState<ChaosReport[]>([]);

  useEffect(() => {
    fetch('/api/operator/chaos/campaigns', { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setHistory(data);
          setReport(data[0]);
        }
      })
      .catch(() => {});
  }, []);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch('/api/operator/chaos/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
        },
        body: JSON.stringify({
          seed,
          operation_count: ops,
          worker_count: workers,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Chaos campaign failed (${res.status})`);
      }
      const data: ChaosReport = await res.json();
      setReport(data);
      setHistory((prev) => [data, ...prev]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to run chaos campaign');
    } finally {
      setRunning(false);
    }
  };

  const handleDownloadJson = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${report.campaign_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
            Automated Chaos Campaigns
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
            Deterministic fault injection, forward recovery verification, and invariant matrix (disabled in production).
          </p>
        </div>
        {report && (
          <button
            type="button"
            onClick={handleDownloadJson}
            style={{
              padding: '0.6rem 1rem',
              borderRadius: '14px',
              background: 'rgba(59, 130, 246, 0.16)',
              border: '1px solid rgba(59, 130, 246, 0.4)',
              color: '#93C5FD',
              fontSize: '0.8125rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Download JSON Report
          </button>
        )}
      </header>

      {/* Configuration Summary & Trigger */}
      <section
        aria-label="Chaos campaign configuration"
        style={{
          padding: '1.25rem',
          borderRadius: '24px',
          background: 'rgba(15, 23, 42, 0.72)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '1rem',
          alignItems: 'end',
        }}
      >
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.75rem', color: '#94A3B8' }}>
          <span>Deterministic Seed</span>
          <input
            type="number"
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value) || 42)}
            style={{ padding: '0.55rem 0.75rem', borderRadius: '12px', background: 'rgba(2, 6, 23, 0.6)', border: '1px solid rgba(255,255,255,0.12)', color: '#F8FAFC' }}
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.75rem', color: '#94A3B8' }}>
          <span>Operations</span>
          <input
            type="number"
            min={4}
            max={200}
            value={ops}
            onChange={(e) => setOps(Number(e.target.value) || 16)}
            style={{ padding: '0.55rem 0.75rem', borderRadius: '12px', background: 'rgba(2, 6, 23, 0.6)', border: '1px solid rgba(255,255,255,0.12)', color: '#F8FAFC' }}
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.75rem', color: '#94A3B8' }}>
          <span>Workers</span>
          <input
            type="number"
            min={1}
            max={16}
            value={workers}
            onChange={(e) => setWorkers(Number(e.target.value) || 4)}
            style={{ padding: '0.55rem 0.75rem', borderRadius: '12px', background: 'rgba(2, 6, 23, 0.6)', border: '1px solid rgba(255,255,255,0.12)', color: '#F8FAFC' }}
          />
        </label>
        <button
          type="button"
          disabled={running}
          onClick={handleRun}
          style={{
            padding: '0.65rem 1.25rem',
            borderRadius: '14px',
            background: running ? 'rgba(100, 116, 139, 0.3)' : 'linear-gradient(135deg, #2563EB, #1D4ED8)',
            border: '1px solid rgba(96, 165, 250, 0.5)',
            color: '#FFFFFF',
            fontWeight: 600,
            fontSize: '0.875rem',
            cursor: running ? 'wait' : 'pointer',
          }}
        >
          {running ? 'Running Campaign...' : 'Run Chaos Campaign'}
        </button>
      </section>

      {error && (
        <div role="alert" style={{ padding: '0.875rem 1rem', borderRadius: '14px', background: 'rgba(244, 63, 94, 0.14)', border: '1px solid rgba(244, 63, 94, 0.35)', color: '#FDA4AF' }}>
          {error}
        </div>
      )}

      {report && (
        <>
          {/* Summary & Recovery Result */}
          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
            <div style={{ padding: '1rem', borderRadius: '20px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Campaign Status</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem', color: report.status === 'PASS' ? '#34D399' : '#FB7185' }}>
                {report.status}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.25rem' }}>
                Seed {report.seed} • {report.git_sha}
              </div>
            </div>
            <div style={{ padding: '1rem', borderRadius: '20px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Operations / Recovered</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem', color: '#F8FAFC' }}>
                {report.settled_count}/{report.operations_attempted} settled
              </div>
              <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.25rem' }}>
                {report.recovered_count} forward-recovered • {report.duplicate_messages_ignored} dupes ignored
              </div>
            </div>
            <div style={{ padding: '1rem', borderRadius: '20px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Recovery Latency (P95)</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem', color: '#F8FAFC' }}>
                {report.recovery_latency_ms?.p95 ?? 0} ms
              </div>
              <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.25rem' }}>
                Max unresolved: {report.max_unresolved_duration_ms} ms
              </div>
            </div>
            <div style={{ padding: '1rem', borderRadius: '20px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Reconciliation</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem', color: report.reconciliation_result.status === 'PASS' ? '#34D399' : '#FB7185' }}>
                {report.reconciliation_result.status}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.25rem' }}>
                Coverage: {report.reconciliation_result.coverage} • Findings: {report.reconciliation_result.findings_count}
              </div>
            </div>
          </section>

          {/* Invariant Matrix */}
          <section style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#F8FAFC', marginBottom: '0.875rem' }}>
              Invariant Verification Matrix (I1–I16)
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.65rem' }}>
              {report.invariant_results.map((inv) => (
                <div
                  key={inv.id}
                  style={{
                    padding: '0.75rem',
                    borderRadius: '14px',
                    background: 'rgba(2, 6, 23, 0.5)',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#E2E8F0' }}>
                      {inv.id}: {inv.name}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: '#64748B' }}>{inv.details}</div>
                  </div>
                  <span
                    style={{
                      padding: '0.2rem 0.55rem',
                      borderRadius: '9999px',
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      background: inv.status === 'PASS' ? 'rgba(5, 150, 105, 0.2)' : 'rgba(244, 63, 94, 0.2)',
                      color: inv.status === 'PASS' ? '#34D399' : '#FDA4AF',
                    }}
                  >
                    {inv.status}
                  </span>
                </div>
              ))}
            </div>
          </section>

          {/* Fault Timeline */}
          <section style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#F8FAFC', marginBottom: '0.875rem' }}>
              Fault Injection & Recovery Timeline ({report.fault_timeline.length} events)
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '300px', overflowY: 'auto' }}>
              {report.fault_timeline.map((f, idx) => (
                <div
                  key={`${f.step}-${idx}`}
                  style={{
                    padding: '0.65rem 0.875rem',
                    borderRadius: '12px',
                    background: 'rgba(2, 6, 23, 0.45)',
                    border: '1px solid rgba(255,255,255,0.05)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '1rem',
                    fontSize: '0.8125rem',
                  }}
                >
                  <div>
                    <span style={{ fontWeight: 600, color: '#93C5FD' }}>Step {f.step}</span>
                    <span style={{ color: '#64748B' }}> • </span>
                    <span style={{ color: '#E2E8F0' }}>{f.fault_type}</span>
                    <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '0.15rem' }}>{f.details}</div>
                  </div>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, color: f.recovered ? '#34D399' : '#FB7185' }}>
                    {f.recovered ? 'RECOVERED' : 'UNRESOLVED'}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {history.length > 1 && (
        <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
          Recent campaigns in session: {history.length}
        </div>
      )}
    </div>
  );
}
