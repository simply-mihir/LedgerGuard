'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '../../lib/auth-context';
import { OverviewData } from '../../lib/types';
import { getOverview } from '../../lib/api';

const NAV_ITEMS = [
  { href: '/console', label: 'Platform Overview', icon: 'M3 3h7v9H3zm11 0h7v5h-7zm0 8h7v9h-7zM3 15h7v5H3z' },
  { href: '/console/accounts', label: 'Accounts & Ledgers', icon: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 7a4 4 0 1 0 0-8 4 4 0 0 0 0 8z' },
  { href: '/console/transfers', label: 'TCC Transfers', icon: 'M17 1l4 4-4 4M3 11V9a4 4 0 0 1 4-4h14M7 23l-4-4 4-4M21 13v2a4 4 0 0 1-4 4H3' },
  { href: '/console/reconciliation', label: 'Reconciliation', icon: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10zM9 12l2 2 4-4' },
  { href: '/console/experiments', label: 'Failure Lab', icon: 'M10 2v7.31M14 2v7.31M8.5 2h7M14 9.3a6.5 6.5 0 1 1-4 0' },
  { href: '/console/security', label: 'Operator Security', icon: 'M12 2a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V7a5 5 0 0 0-5-5zm-3 8V7a3 3 0 0 1 6 0v3H9z' },
];

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, operator, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Authentication barrier: redirect unauthenticated requests to /login
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      const returnUrl = encodeURIComponent(pathname);
      router.replace(`/login?returnUrl=${returnUrl}`);
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  const refreshTelemetry = async () => {
    setIsRefreshing(true);
    try {
      const data = await getOverview();
      setOverview(data);
      setLastRefreshedAt(new Date());
    } catch {
      // Handled in individual screen views
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      refreshTelemetry();
      const interval = setInterval(refreshTelemetry, 15000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated]);

  if (isLoading) {
    return (
      <div
        className="dark-operational-field"
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#94A3B8',
          fontSize: '0.875rem',
        }}
      >
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: '#F1F5F9' }}>
          Verifying Operator Credentials...
        </span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  const allReachable =
    overview?.reachability?.coordinator &&
    overview?.reachability?.['ledger-1'] &&
    overview?.reachability?.['ledger-2'];

  return (
    <div
      className="dark-operational-field"
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        color: 'var(--text-operational)',
        fontFamily: 'var(--font-sans)',
      }}
    >
      {/* Mobile Top Header */}
      <div
        className="md:hidden"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.875rem 1.25rem',
          background: 'rgba(11, 15, 25, 0.90)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          position: 'sticky',
          top: 0,
          zIndex: 40,
        }}
      >
        <Link href="/console" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none', color: '#F8FAFC' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#38BDF8', boxShadow: '0 0 10px #38BDF8' }} />
          <span style={{ fontFamily: 'var(--font-serif)', fontSize: '1.1rem', fontWeight: 700 }}>
            LedgerGuard
          </span>
        </Link>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          style={{
            padding: '0.4rem 0.8rem',
            fontSize: '0.75rem',
            fontFamily: 'var(--font-mono)',
            textTransform: 'uppercase',
            background: 'rgba(255, 255, 255, 0.08)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: 'var(--radius-control, 14px)',
            color: '#F1F5F9',
            cursor: 'pointer',
          }}
        >
          {mobileMenuOpen ? 'Close' : 'Menu'}
        </button>
      </div>

      <div style={{ display: 'flex', flex: 1, minWidth: 0, padding: '1rem', gap: '1rem' }}>
        {/* Desktop Rounded Floating Navigation Rail */}
        <aside
          className={`${mobileMenuOpen ? 'block' : 'hidden'} md:flex flex-col`}
          style={{
            width: '270px',
            background: 'rgba(14, 20, 34, 0.82)',
            backdropFilter: 'blur(28px)',
            WebkitBackdropFilter: 'blur(28px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 'var(--radius-primary, 28px)',
            boxShadow: '0 20px 48px -12px rgba(0, 0, 0, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
            flexShrink: 0,
            zIndex: 30,
            overflow: 'hidden',
          }}
        >
          {/* Brand & Platform Header */}
          <div style={{ padding: '1.5rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
            <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', textDecoration: 'none', color: '#F8FAFC' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#38BDF8', boxShadow: '0 0 10px #38BDF8' }} />
              <span style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                LedgerGuard
              </span>
            </Link>
            <div style={{ marginTop: '0.35rem', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#64748B' }}>
              Operator Control Plane
            </div>
          </div>

          {/* Navigation Items */}
          <nav style={{ flex: 1, padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.375rem', overflowY: 'auto' }}>
            {NAV_ITEMS.map((item) => {
              const isActive =
                item.href === '/console'
                  ? pathname === '/console'
                  : pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    padding: '0.65rem 0.95rem',
                    fontSize: '0.8125rem',
                    fontWeight: isActive ? 600 : 500,
                    borderRadius: 'var(--radius-control, 14px)',
                    textDecoration: 'none',
                    color: isActive ? '#FFFFFF' : '#94A3B8',
                    background: isActive
                      ? 'linear-gradient(135deg, rgba(29, 78, 216, 0.40) 0%, rgba(37, 99, 235, 0.20) 100%)'
                      : 'transparent',
                    border: isActive
                      ? '1px solid rgba(59, 130, 246, 0.45)'
                      : '1px solid transparent',
                    boxShadow: isActive ? '0 4px 14px rgba(29, 78, 216, 0.25)' : 'none',
                    transition: 'all 0.18s cubic-bezier(0.16, 1, 0.3, 1)',
                  }}
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{ color: isActive ? '#60A5FA' : '#64748B' }}
                  >
                    <path d={item.icon} />
                  </svg>
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* Cluster Connectivity Telemetry Widget */}
          <div
            style={{
              margin: '0.75rem',
              padding: '1rem',
              background: 'rgba(20, 28, 48, 0.65)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 'var(--radius-secondary, 20px)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>
              <span style={{ color: '#94A3B8' }}>3 Databases</span>
              <span style={{ color: allReachable ? '#34D399' : '#EF4444', fontWeight: 700 }}>
                {allReachable ? 'Synchronized' : 'Degraded'}
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.35rem', paddingTop: '0.35rem', borderTop: '1px solid rgba(255, 255, 255, 0.06)', fontSize: '0.625rem', fontFamily: 'var(--font-mono)', textAlign: 'center' }}>
              <div style={{ padding: '0.35rem 0.2rem', borderRadius: 'var(--radius-xs)', background: overview?.reachability?.coordinator ? 'rgba(5, 150, 105, 0.15)' : 'rgba(220, 38, 38, 0.15)', color: overview?.reachability?.coordinator ? '#34D399' : '#FCA5A5' }}>
                Coord :42
              </div>
              <div style={{ padding: '0.35rem 0.2rem', borderRadius: 'var(--radius-xs)', background: overview?.reachability?.['ledger-1'] ? 'rgba(5, 150, 105, 0.15)' : 'rgba(220, 38, 38, 0.15)', color: overview?.reachability?.['ledger-1'] ? '#34D399' : '#FCA5A5' }}>
                L1 :43
              </div>
              <div style={{ padding: '0.35rem 0.2rem', borderRadius: 'var(--radius-xs)', background: overview?.reachability?.['ledger-2'] ? 'rgba(5, 150, 105, 0.15)' : 'rgba(220, 38, 38, 0.15)', color: overview?.reachability?.['ledger-2'] ? '#34D399' : '#FCA5A5' }}>
                L2 :44
              </div>
            </div>
          </div>

          {/* Operator Identity & Sign Out */}
          <div
            style={{
              padding: '1rem 1.25rem',
              borderTop: '1px solid rgba(255, 255, 255, 0.06)',
              background: 'rgba(11, 15, 25, 0.85)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#F8FAFC', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {operator?.username || 'Operator'}
              </span>
              <span style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', color: '#64748B' }}>
                {operator?.role || 'OPERATOR'} · {operator?.totp_enabled ? 'MFA' : 'Standard'}
              </span>
            </div>
            <button
              onClick={() => logout()}
              style={{
                fontSize: '0.75rem',
                color: '#94A3B8',
                fontFamily: 'var(--font-mono)',
                textTransform: 'uppercase',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 'var(--radius-sm, 10px)',
                cursor: 'pointer',
                padding: '0.35rem 0.65rem',
                transition: 'all 0.18s ease',
              }}
              title="Revoke session and sign out"
            >
              Sign Out
            </button>
          </div>
        </aside>

        {/* Main Operational Workspace Canvas */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            minWidth: 0,
            background: 'rgba(11, 15, 25, 0.70)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 'var(--radius-primary, 28px)',
            boxShadow: '0 24px 64px -16px rgba(0, 0, 0, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
            overflow: 'hidden',
          }}
        >
          {/* Frosted Top Operational Bar */}
          <header
            style={{
              height: '3.75rem',
              padding: '0 1.75rem',
              borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
              background: 'rgba(14, 20, 34, 0.85)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  color: '#38BDF8',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  fontWeight: 700,
                  background: 'rgba(6, 182, 212, 0.12)',
                  padding: '0.2rem 0.55rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  border: '1px solid rgba(6, 182, 212, 0.25)',
                }}
              >
                Live Topology
              </span>
              <span style={{ color: '#475569', fontSize: '0.75rem' }}>/</span>
              <span style={{ fontSize: '0.8125rem', color: '#94A3B8' }}>
                {pathname === '/console' && 'Cluster Overview & Clearing Conservation Telemetry'}
                {pathname.startsWith('/console/accounts') && 'Partitioned Customer Ledgers & Immutable Statements'}
                {pathname.startsWith('/console/transfers') && 'Try-Confirm-Cancel Distributed Workflow Engine'}
                {pathname.startsWith('/console/reconciliation') && 'Cross-Ledger Clearing Invariant Audit'}
                {pathname.startsWith('/console/experiments') && 'Deterministic Fault Injection & Recovery Lab'}
                {pathname.startsWith('/console/security') && 'Operator Credentials & Session Management'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <span style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: '#64748B' }}>
                {lastRefreshedAt
                  ? `Sync ${lastRefreshedAt.toLocaleTimeString()}`
                  : 'Connecting...'}
              </span>
              <button
                onClick={refreshTelemetry}
                disabled={isRefreshing}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                  color: '#E2E8F0',
                  background: 'rgba(255, 255, 255, 0.08)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: 'var(--radius-control, 14px)',
                  cursor: isRefreshing ? 'not-allowed' : 'pointer',
                  opacity: isRefreshing ? 0.6 : 1,
                  transition: 'all 0.18s ease',
                }}
              >
                {isRefreshing ? 'Syncing...' : '↻ Refresh'}
              </button>
            </div>
          </header>

          {/* Content Body */}
          <main
            style={{
              flex: 1,
              padding: '2rem',
              overflowY: 'auto',
              width: '100%',
              maxWidth: '1600px',
              margin: '0 auto',
            }}
          >
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
