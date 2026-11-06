import React, { useState, useEffect } from 'react';
import { NavigationTab, OverviewData } from '../../lib/types';
import { Badge } from '../ui/badge';
import { StatusDot } from '../ui/status-dot';

interface MobileNavProps {
  activeTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  accountsCount: number;
  transfersCount: number;
  overview: OverviewData | null;
}

export function MobileNav({
  activeTab,
  onSelectTab,
  accountsCount,
  transfersCount,
  overview,
}: MobileNavProps) {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape') setIsOpen(false);
      };
      window.addEventListener('keydown', handleEscape);
      return () => {
        window.removeEventListener('keydown', handleEscape);
        document.body.style.overflow = '';
      };
    }
  }, [isOpen]);

  const navItems: { id: NavigationTab; label: string; badge?: React.ReactNode }[] = [
    { id: 'overview', label: 'Overview' },
    {
      id: 'accounts',
      label: 'Accounts',
      badge: accountsCount > 0 ? <Badge size="sm" variant="neutral">{accountsCount}</Badge> : null,
    },
    {
      id: 'transfers',
      label: 'Transfers',
      badge: transfersCount > 0 ? <Badge size="sm" variant={overview?.pending_transfers ? 'amber' : 'neutral'}>{transfersCount}</Badge> : null,
    },
    {
      id: 'reconciliation',
      label: 'Reconciliation',
      badge: overview ? (
        <Badge size="sm" variant={overview.last_reconciliation_status === 'PASS' ? 'mint' : 'rose'}>
          {overview.last_reconciliation_status}
        </Badge>
      ) : null,
    },
    { id: 'experiments', label: 'Failure Lab', badge: <Badge size="sm" variant="blue">TCC</Badge> },
  ];

  return (
    <div className="md:hidden">
      {/* Mobile Sticky Top Header */}
      <div
        style={{
          height: '56px',
          backgroundColor: '#0c0e12',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 1rem',
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, rgba(13, 242, 166, 0.2) 0%, rgba(56, 189, 248, 0.2) 100%)',
              border: '1px solid rgba(13, 242, 166, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span style={{ color: '#0df2a6', fontSize: '0.75rem', fontWeight: 800 }}>LG</span>
          </div>
          <span style={{ fontSize: '0.9375rem', fontWeight: 700, color: '#f8fafc' }}>
            LedgerGuard
          </span>
          <span
            style={{
              fontSize: '0.5625rem',
              fontWeight: 700,
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

        {/* Hamburger Toggle */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          aria-label={isOpen ? 'Close menu' : 'Open navigation menu'}
          aria-expanded={isOpen}
          className="btn-interactive"
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.10)',
            color: '#f8fafc',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            fontSize: '1.125rem',
          }}
        >
          {isOpen ? '✕' : '☰'}
        </button>
      </div>

      {/* Slide-over Drawer */}
      {isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 100,
            display: 'flex',
          }}
        >
          {/* Backdrop */}
          <div
            onClick={() => setIsOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(5, 7, 9, 0.8)',
              backdropFilter: 'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
            }}
          />

          {/* Drawer content */}
          <div
            style={{
              position: 'relative',
              width: '280px',
              height: '100%',
              backgroundColor: '#0c0e12',
              borderRight: '1px solid rgba(255, 255, 255, 0.12)',
              boxShadow: '8px 0 32px rgba(0, 0, 0, 0.8)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              zIndex: 101,
              animation: 'slide-in-right 0.24s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            <div>
              <div
                style={{
                  height: '56px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0 1.25rem',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#f8fafc' }}>
                  Navigation
                </span>
                <button
                  onClick={() => setIsOpen(false)}
                  aria-label="Close menu"
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#94a3b8',
                    cursor: 'pointer',
                    fontSize: '1rem',
                  }}
                >
                  ✕
                </button>
              </div>

              <nav style={{ padding: '1rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                {navItems.map((item) => {
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        onSelectTab(item.id);
                        setIsOpen(false);
                      }}
                      className="btn-interactive"
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.75rem 1rem',
                        borderRadius: '10px',
                        background: isActive ? 'rgba(13, 242, 166, 0.12)' : 'transparent',
                        border: isActive ? '1px solid rgba(13, 242, 166, 0.28)' : '1px solid transparent',
                        color: isActive ? '#0df2a6' : '#94a3b8',
                        fontSize: '0.875rem',
                        fontWeight: isActive ? 600 : 500,
                        cursor: 'pointer',
                        textAlign: 'left',
                      }}
                    >
                      <span>{item.label}</span>
                      {item.badge}
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Mobile Cluster Status */}
            <div
              style={{
                padding: '1.25rem',
                borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                backgroundColor: '#0a0b0e',
              }}
            >
              <div style={{ fontSize: '0.6875rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                Cluster Node Status
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>Coordinator (:5442)</span>
                  <StatusDot status={overview?.reachability?.coordinator ?? false} size={5} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>Ledger 1 (:5443)</span>
                  <StatusDot status={overview?.reachability?.['ledger-1'] ?? false} size={5} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>Ledger 2 (:5444)</span>
                  <StatusDot status={overview?.reachability?.['ledger-2'] ?? false} size={5} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
