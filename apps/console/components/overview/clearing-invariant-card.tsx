import React from 'react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { formatINR } from '../../lib/format';

interface ClearingInvariantCardProps {
  clearingSum: number;
  lastReconciliationStatus: string;
}

export function ClearingInvariantCard({
  clearingSum,
  lastReconciliationStatus,
}: ClearingInvariantCardProps) {
  const isPassing = clearingSum === 0;

  return (
    <Card
      accent={isPassing ? 'mint' : 'rose'}
      style={{
        padding: '1.4rem 1.5rem',
        background: isPassing
          ? 'linear-gradient(145deg, rgba(13, 242, 166, 0.05) 0%, rgba(19, 22, 28, 0.8) 100%)'
          : 'linear-gradient(145deg, rgba(244, 63, 94, 0.06) 0%, rgba(19, 22, 28, 0.8) 100%)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Top Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span
            style={{
              fontSize: '0.6875rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: isPassing ? '#0df2a6' : '#fb7185',
            }}
          >
            Core Financial Invariant
          </span>
          <span style={{ color: '#475569' }}>•</span>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Inter-Ledger Conservation</span>
        </div>

        <Badge
          variant={isPassing ? 'mint' : 'rose'}
          dot={true}
          size="md"
        >
          {isPassing ? 'INVARIANT PASS' : 'INVARIANT BREACH'}
        </Badge>
      </div>

      {/* Prominent Formula & Value */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '1rem',
          margin: '0.5rem 0 0.85rem 0',
        }}
      >
        <div>
          <div
            className="font-mono"
            style={{
              fontSize: '2.1rem',
              fontWeight: 700,
              letterSpacing: '-0.04em',
              color: isPassing ? '#f8fafc' : '#fb7185',
              lineHeight: 1.1,
            }}
          >
            Σ ΔL = {formatINR(clearingSum)}
          </div>
          <div style={{ fontSize: '0.8125rem', color: '#94a3b8', marginTop: '0.35rem' }}>
            Net clearing obligations across Ledger 1 and Ledger 2 balance to zero.
          </div>
        </div>

        {/* Audit Status Pill */}
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Latest Audit
          </div>
          <div
            style={{
              fontSize: '0.9375rem',
              fontWeight: 700,
              color: lastReconciliationStatus === 'PASS' ? '#0df2a6' : '#fb7185',
              marginTop: '0.15rem',
            }}
          >
            {lastReconciliationStatus === 'PASS' ? '100% Balanced' : lastReconciliationStatus}
          </div>
        </div>
      </div>

      {/* Restrained Balance Visualizer (Stabilizes cleanly, respects reduced-motion) */}
      <div
        style={{
          width: '100%',
          height: '6px',
          borderRadius: '9999px',
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          overflow: 'hidden',
          position: 'relative',
          marginTop: '0.5rem',
        }}
      >
        <div
          className="invariant-pulse-bar"
          style={{
            height: '100%',
            width: isPassing ? '100%' : '60%',
            borderRadius: '9999px',
            background: isPassing
              ? 'linear-gradient(90deg, #0df2a6 0%, #38bdf8 100%)'
              : 'linear-gradient(90deg, #f43f5e 0%, #f59e0b 100%)',
            boxShadow: isPassing
              ? '0 0 12px rgba(13, 242, 166, 0.35)'
              : '0 0 12px rgba(244, 63, 94, 0.35)',
          }}
        />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.6875rem',
          color: '#64748b',
          marginTop: '0.5rem',
        }}
      >
        <span>Ledger 1 (Clearing A/C)</span>
        <span className="font-mono">Exact Zero Equivalence</span>
        <span>Ledger 2 (Clearing A/C)</span>
      </div>
    </Card>
  );
}
