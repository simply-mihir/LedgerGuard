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
      <div className="min-h-screen bg-[#F9F8F6] flex items-center justify-center p-6 text-sm text-[#737373]">
        <span className="font-mono text-xs uppercase tracking-widest text-[#171717]">
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
    <div className="min-h-screen flex flex-col md:flex-row bg-[#F9F8F6] text-[#171717] selection:bg-[#1D4ED8] selection:text-white">
      {/* Mobile Header Bar */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 bg-[#F9F8F6] border-b border-[#E5E2DA]">
        <Link href="/console" className="flex items-center gap-2 text-inherit no-underline">
          <span className="w-2.5 h-2.5 bg-[#171717]" />
          <span className="font-mono text-xs uppercase tracking-widest font-semibold text-[#171717]">
            LedgerGuard
          </span>
        </Link>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-1.5 text-xs font-mono uppercase bg-white border border-[#E5E2DA]"
        >
          {mobileMenuOpen ? 'Close' : 'Menu'}
        </button>
      </div>

      {/* Desktop Pale Stone Sidebar Navigation Rail */}
      <aside
        className={`${
          mobileMenuOpen ? 'block' : 'hidden'
        } md:flex flex-col w-full md:w-64 bg-[#F9F8F6] border-r border-[#E5E2DA] flex-shrink-0 z-20`}
      >
        {/* Brand & Platform Header */}
        <div className="p-6 border-b border-[#E5E2DA]">
          <Link href="/" className="flex items-center gap-2 group text-inherit no-underline">
            <span className="w-2.5 h-2.5 bg-[#171717] group-hover:bg-[#1D4ED8] transition-colors" />
            <span className="font-mono text-xs uppercase tracking-widest font-semibold text-[#171717]">
              LedgerGuard
            </span>
          </Link>
          <div className="mt-2 text-[11px] font-mono uppercase tracking-wider text-[#737373]">
            Operator Control Plane
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 p-3 flex flex-col gap-1 overflow-y-auto">
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
                className={`flex items-center gap-3 px-3 py-2.5 text-xs font-medium rounded-none transition-colors no-underline ${
                  isActive
                    ? 'bg-[#1D4ED8] text-white font-semibold'
                    : 'text-[#404040] hover:bg-[#EAE7DF] hover:text-[#171717]'
                }`}
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
                  className={isActive ? 'text-white' : 'text-[#737373]'}
                >
                  <path d={item.icon} />
                </svg>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Cluster Connectivity Telemetry Widget */}
        <div className="p-4 mx-3 mb-3 bg-white border border-[#E5E2DA] flex flex-col gap-2">
          <div className="flex items-center justify-between text-[11px] font-mono uppercase">
            <span className="text-[#737373]">3-Node Mesh</span>
            <span className={allReachable ? 'text-[#16A34A] font-bold' : 'text-[#DC2626] font-bold'}>
              {allReachable ? 'Synchronized' : 'Degraded'}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-1 pt-1 border-t border-[#F5F4F0] text-[10px] font-mono text-center">
            <div className={`p-1 ${overview?.reachability?.coordinator ? 'bg-[#F0FDF4] text-[#16A34A]' : 'bg-[#FEF2F2] text-[#DC2626]'}`}>
              Coord :42
            </div>
            <div className={`p-1 ${overview?.reachability?.['ledger-1'] ? 'bg-[#F0FDF4] text-[#16A34A]' : 'bg-[#FEF2F2] text-[#DC2626]'}`}>
              L1 :43
            </div>
            <div className={`p-1 ${overview?.reachability?.['ledger-2'] ? 'bg-[#F0FDF4] text-[#16A34A]' : 'bg-[#FEF2F2] text-[#DC2626]'}`}>
              L2 :44
            </div>
          </div>
        </div>

        {/* Operator Identity & Sign Out */}
        <div className="p-4 border-t border-[#E5E2DA] bg-[#FAF9F5] flex items-center justify-between">
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-semibold text-[#171717] truncate">
              {operator?.username || 'Operator'}
            </span>
            <span className="text-[10px] font-mono uppercase text-[#737373]">
              {operator?.role || 'OPERATOR'} · {operator?.totp_enabled ? 'MFA' : 'Standard'}
            </span>
          </div>
          <button
            onClick={() => logout()}
            className="text-xs text-[#737373] hover:text-[#DC2626] font-mono uppercase bg-transparent border-0 cursor-pointer p-1"
            title="Revoke session and sign out"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Right Viewport: Dark Continuous Operational Workspace */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#0B0F17] text-[#F3F4F6]">
        {/* Top Operational Bar */}
        <header className="h-14 px-6 border-b border-[#1E293B] bg-[#0B0F17]/95 sticky top-0 z-10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-[#38BDF8] uppercase tracking-wider font-semibold">
              Live Topology
            </span>
            <span className="text-[#475569] text-xs">/</span>
            <span className="text-xs text-[#94A3B8]">
              {pathname === '/console' && 'Cluster Overview & Conservation Telemetry'}
              {pathname.startsWith('/console/accounts') && 'Partitioned Customer Ledgers & Immutable Statements'}
              {pathname.startsWith('/console/transfers') && 'Try-Confirm-Cancel Distributed Workflow Engine'}
              {pathname.startsWith('/console/reconciliation') && 'Cross-Ledger Clearing Invariant Audit'}
              {pathname.startsWith('/console/experiments') && 'Deterministic Fault Injection & Recovery Lab'}
              {pathname.startsWith('/console/security') && 'Operator Credentials & Session Management'}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[11px] font-mono text-[#64748B]">
              {lastRefreshedAt
                ? `Sync ${lastRefreshedAt.toLocaleTimeString()}`
                : 'Connecting...'}
            </span>
            <button
              onClick={refreshTelemetry}
              disabled={isRefreshing}
              className="px-2.5 py-1 text-xs font-mono text-[#94A3B8] hover:text-white bg-[#1E293B] hover:bg-[#334155] border-0 transition-colors disabled:opacity-50 cursor-pointer"
            >
              {isRefreshing ? 'Syncing...' : '↻ Refresh'}
            </button>
          </div>
        </header>

        {/* Content Body */}
        <main className="flex-1 p-6 md:p-8 max-w-[1600px] w-full mx-auto overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
