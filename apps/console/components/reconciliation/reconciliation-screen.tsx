import { OverviewData, ReconciliationReport } from '../../lib/types';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { formatINR } from '../../lib/format';
import { AuditSummaryCard } from './audit-summary-card';
import { FindingsTable } from './findings-table';

interface ReconciliationScreenProps {
  report: ReconciliationReport | null;
  overview?: OverviewData | null;
  onRunAudit: () => void;
  isReconciling: boolean;
}

export function ReconciliationScreen({
  report,
  overview,
  onRunAudit,
  isReconciling,
}: ReconciliationScreenProps) {
  const reachableCount = Object.values(overview?.reachability || {}).filter(Boolean).length;
  const totalNodes = Object.keys(overview?.reachability || {}).length || 3;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Top Action Bar */}
      <Card style={{ padding: '1.5rem' }}>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.02em' }}>
              Multi-Database Double-Entry Audit Engine
            </h2>
            <p style={{ fontSize: '0.8125rem', color: '#94a3b8', marginTop: '0.25rem', maxWidth: '640px', lineHeight: 1.5 }}>
              Executes local double-entry reconciliation verifying that all journals balance, wallet caches match posted lines,
              and trial balance debits equal credits across accounts.
            </p>
          </div>

          <Button
            variant="primary"
            size="md"
            onClick={onRunAudit}
            isLoading={isReconciling}
            icon={
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <polyline points="9 12 11 14 15 10" />
              </svg>
            }
          >
            {isReconciling ? 'Auditing Cluster...' : 'Execute Live Audit'}
          </Button>
        </div>
      </Card>

      {/* Distributed Platform Telemetry Banner */}
      {overview && (
        <Card style={{ padding: '1.15rem 1.5rem', background: 'rgba(255, 255, 255, 0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <span style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
                Platform Telemetry (From Coordinator Overview Directory)
              </span>
              <div style={{ fontSize: '0.875rem', color: '#f8fafc', fontWeight: 600, marginTop: '0.2rem' }}>
                Inter-Ledger Net Clearing Sum: <span className="font-mono" style={{ color: overview.clearing_sum === 0 ? '#0df2a6' : '#fb7185' }}>{formatINR(overview.clearing_sum)}</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                Reachable Participant Nodes:
              </span>
              <Badge variant="blue" size="sm">
                {reachableCount}/{totalNodes} Active
              </Badge>
            </div>
          </div>
        </Card>
      )}

      {/* Audit Report View */}
      {report ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <AuditSummaryCard report={report} />

          {/* Findings Card */}
          <Card style={{ padding: 0, overflow: 'hidden' }}>
            <CardHeader style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <div>
                <CardTitle>Reconciliation Findings & Discrepancies</CardTitle>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.15rem' }}>
                  Granular invariant checks across journals, accounts, and clearing tables
                </div>
              </div>
            </CardHeader>
            <FindingsTable findings={report.findings} />
          </Card>
        </div>
      ) : (
        <Card style={{ padding: '3.5rem 1.5rem', textAlign: 'center' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '14px',
              backgroundColor: 'rgba(56, 189, 248, 0.12)',
              border: '1px solid rgba(56, 189, 248, 0.28)',
              color: '#38bdf8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.25rem auto',
            }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <polyline points="9 12 11 14 15 10" />
            </svg>
          </div>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.4rem' }}>
            No Audit Executed in Current Session
          </h3>
          <p style={{ fontSize: '0.8125rem', color: '#94a3b8', maxWidth: '440px', margin: '0 auto 1.5rem auto', lineHeight: 1.5 }}>
            Trigger an on-demand audit to inspect inter-ledger clearing conservation, journal equality, and active holds across all participants.
          </p>
          <Button
            variant="primary"
            size="md"
            onClick={onRunAudit}
            isLoading={isReconciling}
          >
            Execute Live Audit
          </Button>
        </Card>
      )}

      {/* Verified Audit Scope Matrix */}
      <Card style={{ padding: '1.5rem' }}>
        <CardTitle style={{ marginBottom: '0.85rem' }}>Enforced Reconciliation Invariants</CardTitle>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '1rem',
            fontSize: '0.8125rem',
            color: '#94a3b8',
          }}
        >
          <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '0.875rem 1rem', borderRadius: '10px' }}>
            <span style={{ color: '#0df2a6', fontWeight: 600, display: 'block', marginBottom: '0.2rem' }}>
              1. Clearing Conservation (Σ ΔL = 0)
            </span>
            Clearing account balance on Ledger 1 and Ledger 2 must sum to exactly zero paise at all times.
          </div>
          <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '0.875rem 1rem', borderRadius: '10px' }}>
            <span style={{ color: '#0df2a6', fontWeight: 600, display: 'block', marginBottom: '0.2rem' }}>
              2. Balanced Double-Entry Postings
            </span>
            Every journal entry across all participant ledgers enforces Total Debits = Total Credits per currency.
          </div>
          <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '0.875rem 1rem', borderRadius: '10px' }}>
            <span style={{ color: '#0df2a6', fontWeight: 600, display: 'block', marginBottom: '0.2rem' }}>
              3. Hold & Balance Cache Consistency
            </span>
            Cached available balance in `account_balances` exactly equals posted balance minus active unexpired holds.
          </div>
        </div>
      </Card>
    </div>
  );
}
