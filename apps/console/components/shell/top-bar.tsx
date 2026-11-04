import React from 'react';
import { NavigationTab } from '../../lib/types';
import { Button } from '../ui/button';
import { StatusDot } from '../ui/status-dot';

interface TopBarProps {
  activeTab: NavigationTab;
  lastRefreshedAt: Date | null;
  isRefreshing: boolean;
  onRefresh: () => void;
  screenActions?: React.ReactNode;
}

const TAB_METADATA: Record<NavigationTab, { title: string; subtitle: string }> = {
  overview: {
    title: 'Platform Overview',
    subtitle: 'Autonomous PostgreSQL 17 cluster mesh & invariant telemetry',
  },
  accounts: {
    title: 'Customer Accounts',
    subtitle: 'Authoritative posted balances, active holds, and immutable journals',
  },
  transfers: {
    title: 'TCC Transfer Engine',
    subtitle: 'Reserve/confirm/cancel protocol state & durable decision log',
  },
  reconciliation: {
    title: 'Reconciliation Audit',
    subtitle: 'Post-settlement double-entry equality & clearing balance conservation',
  },
  experiments: {
    title: 'Failure Lab',
    subtitle: 'Deterministic crash injection & autonomous forward recovery tests',
  },
};

export function TopBar({
  activeTab,
  lastRefreshedAt,
  isRefreshing,
  onRefresh,
  screenActions,
}: TopBarProps) {
  const meta = TAB_METADATA[activeTab];

  return (
    <header
      style={{
        height: '68px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        backgroundColor: 'rgba(9, 10, 12, 0.85)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        position: 'sticky',
        top: 0,
        zIndex: 30,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.5rem',
        gap: '1rem',
      }}
    >
      {/* Title & Context Breadcrumb */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <h1
            style={{
              fontSize: '1.0625rem',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: '#f8fafc',
            }}
          >
            {meta.title}
          </h1>
        </div>
        <p
          style={{
            fontSize: '0.75rem',
            color: '#64748b',
            letterSpacing: '-0.01em',
            marginTop: '0.1rem',
          }}
        >
          {meta.subtitle}
        </p>
      </div>

      {/* Right Controls: Telemetry Pill, Refresh Button, Screen Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        {/* Live Status Pill */}
        <div
          style={{
            display: 'none',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.35rem 0.75rem',
            borderRadius: '9999px',
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            fontSize: '0.6875rem',
            color: '#94a3b8',
          }}
          className="sm:flex"
        >
          <StatusDot status="active" pulse={true} size={6} />
          <span style={{ fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.04em' }}>LIVE</span>
          <span style={{ color: '#475569' }}>•</span>
          <span>
            {lastRefreshedAt
              ? `Sync ${lastRefreshedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
              : 'Connecting...'}
          </span>
        </div>

        {/* Screen-Specific Action Slot */}
        {screenActions && <div>{screenActions}</div>}

        {/* Refresh Action */}
        <Button
          variant="secondary"
          size="sm"
          onClick={onRefresh}
          disabled={isRefreshing}
          aria-label="Refresh platform state"
          icon={
            <span
              style={{
                display: 'inline-block',
                animation: isRefreshing ? 'spin 0.6s linear infinite' : 'none',
              }}
            >
              ↻
            </span>
          }
        >
          {isRefreshing ? 'Syncing...' : 'Refresh'}
        </Button>
      </div>
    </header>
  );
}
