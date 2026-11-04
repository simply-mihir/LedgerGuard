import React from 'react';
import { NavigationTab, OverviewData } from '../../lib/types';
import { Badge } from '../ui/badge';

interface NavigationRailProps {
  activeTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  accountsCount: number;
  transfersCount: number;
  overview: OverviewData | null;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export function NavigationRail({
  activeTab,
  onSelectTab,
  accountsCount,
  transfersCount,
  overview,
  isCollapsed,
  onToggleCollapse,
}: NavigationRailProps) {
  const isAllReachable =
    overview?.reachability?.coordinator &&
    overview?.reachability?.['ledger-1'] &&
    overview?.reachability?.['ledger-2'];

  const navItems: {
    id: NavigationTab;
    label: string;
    badge?: React.ReactNode;
    icon: React.ReactNode;
  }[] = [
    {
      id: 'overview',
      label: 'Overview',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="7" height="9" rx="1" />
          <rect x="14" y="3" width="7" height="5" rx="1" />
          <rect x="14" y="12" width="7" height="9" rx="1" />
          <rect x="3" y="16" width="7" height="5" rx="1" />
        </svg>
      ),
    },
    {
      id: 'accounts',
      label: 'Accounts',
      badge: accountsCount > 0 ? <Badge size="sm" variant="neutral">{accountsCount}</Badge> : null,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      ),
    },
    {
      id: 'transfers',
      label: 'Transfers',
      badge: transfersCount > 0 ? <Badge size="sm" variant={overview?.pending_transfers ? 'amber' : 'neutral'}>{transfersCount}</Badge> : null,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="17 1 21 5 17 9" />
          <path d="M3 11V9a4 4 0 0 1 4-4h14" />
          <polyline points="7 23 3 19 7 15" />
          <path d="M21 13v2a4 4 0 0 1-4 4H3" />
        </svg>
      ),
    },
    {
      id: 'reconciliation',
      label: 'Reconciliation',
      badge: overview ? (
        <Badge size="sm" variant={overview.last_reconciliation_status === 'PASS' ? 'mint' : 'rose'}>
          {overview.last_reconciliation_status}
        </Badge>
      ) : null,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <polyline points="9 12 11 14 15 10" />
        </svg>
      ),
    },
    {
      id: 'experiments',
      label: 'Failure Lab',
      badge: <Badge size="sm" variant="blue">TCC</Badge>,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 2v7.31M14 2v7.31" />
          <path d="M8.5 2h7" />
          <path d="M14 9.3a6.5 6.5 0 1 1-4 0" />
        </svg>
      ),
    },
  ];

  return (
    <aside
      className="hidden md:flex"
      style={{
        width: isCollapsed ? '76px' : '260px',
        height: '100vh',
        position: 'sticky',
        top: 0,
        backgroundColor: '#0c0e12',
        borderRight: '1px solid rgba(255, 255, 255, 0.08)',
        flexDirection: 'column',
        justifyContent: 'space-between',
        transition: 'width 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
        zIndex: 40,
        flexShrink: 0,
      }}
    >
      {/* Brand & Wordmark */}
      <div>
        <div
          style={{
            height: '68px',
            padding: isCollapsed ? '0' : '0 1.25rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: isCollapsed ? 'center' : 'flex-start',
            gap: '0.75rem',
          }}
        >
          {/* Signal Mark */}
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, rgba(13, 242, 166, 0.2) 0%, rgba(56, 189, 248, 0.2) 100%)',
              border: '1px solid rgba(13, 242, 166, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              boxShadow: '0 2px 8px rgba(13, 242, 166, 0.15)',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 2L3 7V12C3 17.5 7 21.5 12 22C17 21.5 21 17.5 21 12V7L12 2Z"
                stroke="#0df2a6"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M9 12L11 14L15 10"
                stroke="#0df2a6"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          {!isCollapsed && (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ fontSize: '0.9375rem', fontWeight: 700, letterSpacing: '-0.02em', color: '#f8fafc' }}>
                  LedgerGuard
                </span>
                <span
                  style={{
                    fontSize: '0.5625rem',
                    fontWeight: 700,
                    letterSpacing: '0.06em',
                    color: '#0df2a6',
                    background: 'rgba(13, 242, 166, 0.12)',
                    padding: '0.1rem 0.35rem',
                    borderRadius: '4px',
                    border: '1px solid rgba(13, 242, 166, 0.25)',
                  }}
                >
                  SIGNAL
                </span>
              </div>
              <span style={{ fontSize: '0.6875rem', color: '#64748b', letterSpacing: '-0.01em' }}>
                TCC Distributed Engine
              </span>
            </div>
          )}
        </div>

        {/* Navigation List */}
        <nav
          aria-label="Sidebar Navigation"
          style={{
            padding: isCollapsed ? '1rem 0.5rem' : '1rem 0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.35rem',
          }}
        >
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                title={isCollapsed ? item.label : undefined}
                className="btn-interactive"
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: isCollapsed ? 'center' : 'space-between',
                  padding: isCollapsed ? '0.65rem 0' : '0.625rem 0.85rem',
                  borderRadius: '10px',
                  background: isActive ? 'rgba(13, 242, 166, 0.10)' : 'transparent',
                  border: isActive ? '1px solid rgba(13, 242, 166, 0.24)' : '1px solid transparent',
                  color: isActive ? '#0df2a6' : '#94a3b8',
                  fontSize: '0.8125rem',
                  fontWeight: isActive ? 600 : 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  position: 'relative',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{ color: isActive ? '#0df2a6' : '#64748b', display: 'flex' }}>
                    {item.icon}
                  </span>
                  {!isCollapsed && <span>{item.label}</span>}
                </div>
                {!isCollapsed && item.badge && <div>{item.badge}</div>}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Cluster Health Footer */}
      <div
        style={{
          padding: isCollapsed ? '1rem 0.5rem' : '1rem 0.875rem',
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
          backgroundColor: '#0a0b0e',
        }}
      >
        {!isCollapsed ? (
          <div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '0.6rem',
              }}
            >
              <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Database Topology
              </span>
              <span
                style={{
                  fontSize: '0.625rem',
                  fontWeight: 600,
                  color: isAllReachable ? '#0df2a6' : '#fb7185',
                }}
              >
                {isAllReachable ? '3/3 INSTANCES LIVE' : 'DEGRADED'}
              </span>
            </div>

            {/* Micro node indicators */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.6875rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#94a3b8' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: overview?.reachability?.coordinator ? '#0df2a6' : '#f43f5e',
                    }}
                  />
                  <span>Coord</span>
                </span>
                <span className="font-mono" style={{ color: '#64748b', fontSize: '0.625rem' }}>:5442</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#94a3b8' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: overview?.reachability?.['ledger-1'] ? '#0df2a6' : '#f43f5e',
                    }}
                  />
                  <span>Ledger 1</span>
                </span>
                <span className="font-mono" style={{ color: '#64748b', fontSize: '0.625rem' }}>:5443</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#94a3b8' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: overview?.reachability?.['ledger-2'] ? '#0df2a6' : '#f43f5e',
                    }}
                  />
                  <span>Ledger 2</span>
                </span>
                <span className="font-mono" style={{ color: '#64748b', fontSize: '0.625rem' }}>:5444</span>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <span
              title="Database Topology"
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: isAllReachable ? '#0df2a6' : '#f43f5e',
                boxShadow: isAllReachable ? '0 0 8px rgba(13, 242, 166, 0.4)' : '0 0 8px rgba(244, 63, 94, 0.4)',
              }}
            />
          </div>
        )}

        {/* Collapse toggle */}
        <button
          onClick={onToggleCollapse}
          aria-label={isCollapsed ? 'Expand navigation rail' : 'Collapse navigation rail'}
          className="btn-interactive"
          style={{
            marginTop: '0.75rem',
            width: '100%',
            height: '28px',
            borderRadius: '6px',
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            color: '#64748b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            fontSize: '0.6875rem',
          }}
        >
          {isCollapsed ? '→' : '← Collapse'}
        </button>
      </div>
    </aside>
  );
}
