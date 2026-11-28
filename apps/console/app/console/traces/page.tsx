'use client';

import React, { useEffect, useState } from 'react';

interface TraceSummary {
  trace_id: string;
  transfer_id?: string | null;
  span_count: number;
  total_duration_ms: number;
  has_error: boolean;
  has_recovery: boolean;
  root_name: string;
}

interface SpanItem {
  trace_id: string;
  span_id: string;
  parent_span_id?: string | null;
  name: string;
  duration_ms: number;
  status: string;
  attributes: Record<string, unknown>;
}

interface WaterfallResponse {
  transfer_id: string;
  spans: SpanItem[];
  metrics: {
    total_settlement_ms?: number;
    participant_latency_ms?: number;
    recovery_span_count?: number;
    error_span_count?: number;
    retry_count?: number;
  };
}

export default function TraceExplorerPage() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [selectedTransfer, setSelectedTransfer] = useState<string>('');
  const [waterfall, setWaterfall] = useState<WaterfallResponse | null>(null);

  const loadTraces = async () => {
    const res = await fetch('/api/operator/traces', { cache: 'no-store' });
    if (res.ok) {
      const data: TraceSummary[] = await res.json();
      setTraces(data);
      const firstWithTx = data.find((t) => t.transfer_id);
      if (firstWithTx?.transfer_id && !selectedTransfer) {
        setSelectedTransfer(firstWithTx.transfer_id);
        loadWaterfall(firstWithTx.transfer_id);
      }
    }
  };

  const loadWaterfall = async (transferId: string) => {
    setSelectedTransfer(transferId);
    const res = await fetch(`/api/operator/transfers/${transferId}/trace`, { cache: 'no-store' });
    if (res.ok) {
      setWaterfall(await res.json());
    }
  };

  useEffect(() => {
    loadTraces();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
            End-to-End Trace Explorer
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
            OpenTelemetry span waterfalls across API, TCC Coordinator, Outbox, Participant Inbox, and Forward Recovery.
          </p>
        </div>
        <button
          type="button"
          onClick={loadTraces}
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
          Refresh Traces
        </button>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1fr) minmax(360px, 2fr)', gap: '1rem' }}>
        <section style={{ padding: '1rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <h2 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#F8FAFC', marginBottom: '0.75rem' }}>
            Recent Traces ({traces.length})
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '420px', overflowY: 'auto' }}>
            {traces.map((t) => (
              <button
                key={t.trace_id}
                type="button"
                onClick={() => t.transfer_id && loadWaterfall(t.transfer_id)}
                style={{
                  textAlign: 'left',
                  padding: '0.7rem',
                  borderRadius: '14px',
                  background: t.transfer_id === selectedTransfer ? 'rgba(37, 99, 235, 0.22)' : 'rgba(2, 6, 23, 0.5)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  color: '#E2E8F0',
                  cursor: t.transfer_id ? 'pointer' : 'default',
                }}
              >
                <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>{t.root_name}</div>
                <div style={{ fontSize: '0.72rem', color: '#94A3B8', fontFamily: 'var(--font-mono)' }}>
                  {t.trace_id.slice(0, 16)}... • {t.span_count} spans • {t.total_duration_ms} ms
                </div>
                {t.has_recovery && (
                  <span style={{ fontSize: '0.65rem', color: '#FBBF24' }}>RECOVERY</span>
                )}
              </button>
            ))}
          </div>
        </section>

        <section style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <h2 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#F8FAFC', marginBottom: '0.75rem' }}>
            Span Waterfall {selectedTransfer ? `(${selectedTransfer})` : ''}
          </h2>
          {waterfall && waterfall.spans.length > 0 ? (
            <>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.75rem', color: '#94A3B8', marginBottom: '0.75rem' }}>
                <span>Total: <strong style={{ color: '#F8FAFC' }}>{waterfall.metrics.total_settlement_ms} ms</strong></span>
                <span>Participant: <strong style={{ color: '#F8FAFC' }}>{waterfall.metrics.participant_latency_ms} ms</strong></span>
                <span>Recovery spans: <strong style={{ color: '#FBBF24' }}>{waterfall.metrics.recovery_span_count}</strong></span>
                <span>Errors: <strong style={{ color: '#FB7185' }}>{waterfall.metrics.error_span_count}</strong></span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                {waterfall.spans.map((s) => (
                  <div
                    key={s.span_id}
                    style={{
                      padding: '0.6rem 0.8rem',
                      borderRadius: '12px',
                      background: 'rgba(2, 6, 23, 0.5)',
                      border: '1px solid rgba(255,255,255,0.05)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '0.8rem',
                    }}
                  >
                    <span style={{ fontWeight: 600, color: s.status === 'ERROR' ? '#FDA4AF' : '#E2E8F0' }}>{s.name}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', color: '#94A3B8' }}>{s.duration_ms} ms</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{ fontSize: '0.8125rem', color: '#64748B' }}>
              Select a transfer trace or submit a transfer to inspect its end-to-end span waterfall.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
