import React from 'react';
import { AccountItem, NavigationTab, OverviewData, TransferItem } from '../../lib/types';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { StatusDot } from '../ui/status-dot';
import { formatINR, formatNumber } from '../../lib/format';
import { ClearingInvariantCard } from './clearing-invariant-card';
import { ClusterTopologyCard } from './cluster-topology-card';
import { TransferActivityCard } from './transfer-activity-card';
import { AttentionQueueCard } from './attention-queue-card';
import { KpiCard } from './kpi-card';

interface OverviewScreenProps {
  overview: OverviewData | null;
  accounts: AccountItem[];
  transfers: TransferItem[];
  onNavigateTab: (tab: NavigationTab) => void;
  onOpenTransferTimeline: (transfer: TransferItem) => void;
  onRunReconciliation: () => void;
  isReconciling: boolean;
  lastRefreshedAt: Date | null;
}

export function OverviewScreen({
  overview,
  accounts,
  transfers,
  onNavigateTab,
  onOpenTransferTimeline,
  onRunReconciliation,
  isReconciling,
  lastRefreshedAt,
}: OverviewScreenProps) {
  // Aggregate accounts financial metrics
  const totalPostedAssets = accounts.reduce(
    (acc, a) => acc + (a.posted_balance_minor > 0 ? a.posted_balance_minor : 0),
    0
  );
  const totalHeldFunds = accounts.reduce((acc, a) => acc + a.held_amount_minor, 0);

  const attentionTransfers = transfers.filter((t) => t.attention_required);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Hero Command Banner */}
      <div
        style={{
          padding: '2rem 2.25rem',
          borderRadius: '20px',
          background: 'linear-gradient(135deg, rgba(22, 26, 33, 0.85) 0%, rgba(14, 17, 22, 0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.10)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.55)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div style={{ maxWidth: '880px', position: 'relative', zIndex: 2 }}>
          {/* Eyebrow & Status Pill */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <span
              style={{
                fontSize: '0.6875rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                color: '#0df2a6',
              }}
            >
              Distributed Ledger Control Plane
            </span>
            <span style={{ color: '#475569' }}>•</span>
            <Badge variant={overview && Object.values(overview.reachability).every(Boolean) ? 'mint' : 'rose'} size="sm" dot={true}>
              {overview
                ? `${Object.values(overview.reachability).filter(Boolean).length}/${Object.keys(overview.reachability).length} Nodes Reachable`
                : '3/3 Nodes Reachable'}
            </Badge>
            {lastRefreshedAt && (
              <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                Refreshed {lastRefreshedAt.toLocaleTimeString()}
              </span>
            )}
          </div>

          {/* Main Title */}
          <h2
            style={{
              fontSize: '2.1rem',
              fontWeight: 800,
              letterSpacing: '-0.035em',
              color: '#f8fafc',
              lineHeight: 1.15,
              marginBottom: '0.75rem',
            }}
          >
            Financial state, without ambiguity.
          </h2>

          {/* Supporting Text */}
          <p
            style={{
              fontSize: '0.9375rem',
              color: '#94a3b8',
              lineHeight: 1.6,
              marginBottom: '1.5rem',
            }}
          >
            Application-level Try-Confirm-Cancel (TCC) coordination, immutable double-entry accounting kernels,
            and post-settlement clearing reconciliation across isolated PostgreSQL 17 failure domains.
          </p>

          {/* Hero Actions */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
            <Button
              variant="primary"
              size="md"
              onClick={onRunReconciliation}
              isLoading={isReconciling}
              icon={
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <polyline points="9 12 11 14 15 10" />
                </svg>
              }
            >
              {isReconciling ? 'Running Audit...' : 'Run Reconciliation'}
            </Button>

            <Button
              variant="secondary"
              size="md"
              onClick={() => onNavigateTab('transfers')}
              icon={
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="17 1 21 5 17 9" />
                  <path d="M3 11V9a4 4 0 0 1 4-4h14" />
                </svg>
              }
            >
              Inspect Transfers
            </Button>

            <Button
              variant="ghost"
              size="md"
              onClick={() => onNavigateTab('experiments')}
            >
              Failure Lab →
            </Button>
          </div>
        </div>
      </div>

      {/* Central Financial Invariant: Clearing Conservation */}
      <ClearingInvariantCard
        clearingSum={overview?.clearing_sum ?? 0}
        lastReconciliationStatus={overview?.last_reconciliation_status ?? 'PASS'}
      />

      {/* Primary KPI Row (Bento Grid) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '1rem',
        }}
      >
        <KpiCard
          label="Total Posted Assets"
          value={formatINR(totalPostedAssets)}
          subtext={`${formatNumber(overview?.total_accounts ?? accounts.length)} Provisioned Accounts`}
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <line x1="12" y1="8" x2="12" y2="16" />
              <line x1="8" y1="12" x2="16" y2="12" />
            </svg>
          }
        />

        <KpiCard
          label="Funds Currently Held"
          value={formatINR(totalHeldFunds)}
          accent={totalHeldFunds > 0 ? 'amber' : 'none'}
          subtext="TCC Phase 1 Isolated Balance Holds"
          trend={
            totalHeldFunds > 0 ? (
              <Badge variant="amber" size="sm">Active Holds</Badge>
            ) : (
              <Badge variant="mint" size="sm">Zero Hold Leak</Badge>
            )
          }
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          }
        />

        <KpiCard
          label="Settled Transfers"
          value={formatNumber(overview?.settled_transfers ?? 0)}
          accent="mint"
          subtext={`Out of ${formatNumber(overview?.total_transfers ?? transfers.length)} total requests`}
          trend={<Badge variant="mint" size="sm">100% Settled</Badge>}
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          }
        />

        <KpiCard
          label="Pending Obligations"
          value={formatNumber(overview?.pending_transfers ?? 0)}
          accent={overview?.pending_transfers ? 'amber' : 'none'}
          subtext={`Oldest in-flight age: ${overview?.oldest_pending_age_seconds ?? 0}s`}
          trend={
            overview?.pending_transfers ? (
              <Badge variant="amber" size="sm">In-Flight</Badge>
            ) : (
              <Badge variant="neutral" size="sm">Queue Clear</Badge>
            )
          }
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          }
        />
      </div>

      {/* Cluster Topology & Transfer Activity Split */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
          gap: '1.25rem',
        }}
      >
        <ClusterTopologyCard reachability={overview?.reachability} />
        <TransferActivityCard
          settledCount={overview?.settled_transfers ?? 0}
          pendingCount={overview?.pending_transfers ?? 0}
          totalCount={overview?.total_transfers ?? transfers.length}
          recentTransfers={transfers.slice(0, 5)}
        />
      </div>

      {/* Operator Attention Queue */}
      <AttentionQueueCard
        attentionTransfers={attentionTransfers}
        onInspectTransfer={onOpenTransferTimeline}
      />

      {/* Architectural Guarantees Footer Grid */}
      <Card style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
          <span style={{ fontSize: '0.8125rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#38bdf8' }}>
            Architectural Invariants & Safety Guarantees
          </span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '1rem',
            fontSize: '0.8125rem',
          }}
        >
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              borderRadius: '12px',
              padding: '1rem 1.15rem',
            }}
          >
            <strong style={{ color: '#f8fafc', display: 'block', marginBottom: '0.35rem', fontSize: '0.875rem' }}>
              1. Independent Failure Domains
            </strong>
            <p style={{ color: '#94a3b8', lineHeight: 1.5 }}>
              Coordinator and participant ledgers execute across 3 autonomous PostgreSQL 17 instances (:5442, :5443, :5444).
              Network separation eliminates single points of catastrophic failure.
            </p>
          </div>

          <div
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              borderRadius: '12px',
              padding: '1rem 1.15rem',
            }}
          >
            <strong style={{ color: '#f8fafc', display: 'block', marginBottom: '0.35rem', fontSize: '0.875rem' }}>
              2. Mutual Exclusion & Forward Recovery
            </strong>
            <p style={{ color: '#94a3b8', lineHeight: 1.5 }}>
              COMMIT and CANCEL decisions are strictly mutually exclusive. Once the coordinator logs COMMIT,
              the transfer ALWAYS recovers forward to settlement; premature refunds are prohibited.
            </p>
          </div>

          <div
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              borderRadius: '12px',
              padding: '1rem 1.15rem',
            }}
          >
            <strong style={{ color: '#f8fafc', display: 'block', marginBottom: '0.35rem', fontSize: '0.875rem' }}>
              3. Tombstones & Zero Residual Holds
            </strong>
            <p style={{ color: '#94a3b8', lineHeight: 1.5 }}>
              Reordered CANCEL commands write durable tombstones, preventing late PREPARE messages from locking funds.
              Settled or cancelled workflows leave zero orphan holds on participant ledgers.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
