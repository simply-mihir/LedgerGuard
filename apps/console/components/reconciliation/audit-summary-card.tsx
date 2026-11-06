import React from 'react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { CopyButton } from '../ui/copy-button';
import { ReconciliationReport } from '../../lib/types';
import { formatDateTime, formatINR, formatNumber } from '../../lib/format';

interface AuditSummaryCardProps {
  report: ReconciliationReport;
}

export function AuditSummaryCard({ report }: AuditSummaryCardProps) {
  const isPass = report.status === 'PASS';
  const isTrialBalanced = report.trial_balance_debit === report.trial_balance_credit;

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
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.15rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>Executed {formatDateTime(report.run_at)}</span>
              <span>•</span>
              <span className="font-mono" style={{ color: '#64748b' }}>
                Run {report.run_id.slice(0, 8)}...
              </span>
              <CopyButton text={report.run_id} label="Copy Run ID" />
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <Badge variant={isPass ? 'mint' : 'rose'} size="md" dot={true}>
            {report.status} AUDIT
          </Badge>
          <Badge variant="blue" size="md">
            {formatNumber(report.lines_examined)} LINES AUDITED
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
        {/* Trial Balance Invariant */}
        <div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            Trial Balance Invariant
          </div>
          <div
            className="font-mono"
            style={{
              fontSize: '1.3rem',
              fontWeight: 700,
              color: isTrialBalanced ? '#0df2a6' : '#fb7185',
              marginTop: '0.25rem',
            }}
          >
            {isTrialBalanced ? '100% BALANCED' : 'IMBALANCE'}
          </div>
          <div className="font-mono" style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Debits: {formatINR(report.trial_balance_debit)} • Credits: {formatINR(report.trial_balance_credit)}
          </div>
        </div>

        {/* Accounts Examined */}
        <div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            Accounts Examined
          </div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.25rem' }}>
            {formatNumber(report.accounts_examined)}
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Double-entry balances & cached available sums
          </div>
        </div>

        {/* Journals & Lines */}
        <div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            Journals Examined
          </div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.25rem' }}>
            {formatNumber(report.journals_examined)}
          </div>
          <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Across {formatNumber(report.lines_examined)} immutable posting lines
          </div>
        </div>

        {/* Findings Discrepancies */}
        <div>
          <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            Audit Discrepancies
          </div>
          <div
            style={{
              fontSize: '1.3rem',
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
