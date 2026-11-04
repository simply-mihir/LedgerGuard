import React from 'react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { ReconciliationReport } from '../../lib/types';
import { formatDateTime, formatINR, formatNumber } from '../../lib/format';

interface AuditSummaryCardProps {
  report: ReconciliationReport;
}

export function AuditSummaryCard({ report }: AuditSummaryCardProps) {
  const isPass = report.status === 'PASS';

  return (
    <Card
      accent={isPass ? 'mint' : 'rose'}
      style={{
        padding: '1.5rem',
        background: isPass
          ? 'linear-gradient(135deg, rgba(13, 242, 166, 0.05) 0%, rgba(19, 22, 28, 0.85) 100%)'
          : 'linear-gradient(135deg, rgba(244, 63, 94, 0.06) 0%, rgba(19, 22, 28, 0.85) 100%)',
      }}
    >
      {/* Top Banner */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          paddingBottom: '1.25rem',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          marginBottom: '1.25rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '12px',
              background: isPass ? 'rgba(13, 242, 166, 0.15)' : 'rgba(244, 63, 94, 0.15)',
              border: `1px solid ${isPass ? 'rgba(13, 242, 166, 0.35)' : 'rgba(244, 63, 94, 0.35)'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: isPass ? '#0df2a6' : '#fb7185',
              fontSize: '1.25rem',
              fontWeight: 700,
            }}
          >
            {isPass ? '✓' : '✕'}
          </div>
          <div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.02em' }}>
              Audit Outcome: {report.status}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.15rem' }}>
              Executed {formatDateTime(report.run_at)} • Comprehensive multi-database verification
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <Badge variant={isPass ? 'mint' : 'rose'} size="md" dot={true}>
            {report.status} AUDIT
          </Badge>
          <Badge variant="blue" size="md">
            {report.coverage} COVERAGE
          </Badge>
        </div>
      </div>

      {/* Audit Metric Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '1rem',
        }}
      >
        <div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            Clearing Balance Sum
          </div>
          <div
            className="font-mono"
            style={{
              fontSize: '1.4rem',
              fontWeight: 700,
              color: report.clearing_balance_sum === 0 ? '#0df2a6' : '#fb7185',
              marginTop: '0.25rem',
            }}
          >
            {formatINR(report.clearing_balance_sum)}
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Invariant: L1 + L2 Clearing == 0
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            Participant Reachability
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.25rem' }}>
            {report.reachable_ledgers.length}/3 Ledgers
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Coordinator, Ledger 1, Ledger 2
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            Transfers Examined
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.25rem' }}>
            {formatNumber(report.transfers_examined)}
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Cross-ledger transfer state records
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            Audit Discrepancies
          </div>
          <div
            style={{
              fontSize: '1.4rem',
              fontWeight: 700,
              color: report.findings.length === 0 ? '#0df2a6' : '#fb7185',
              marginTop: '0.25rem',
            }}
          >
            {report.findings.length} Findings
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            {report.findings.length === 0 ? 'Zero integrity violations' : 'Action required'}
          </div>
        </div>
      </div>
    </Card>
  );
}
