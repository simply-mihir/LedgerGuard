'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { OverviewData, TransferItem } from '../../lib/types';
import { getOverview, getTransfers } from '../../lib/api';
import { formatINR, formatNumber } from '../../lib/format';

export default function ConsoleOverviewPage() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [transfers, setTransfers] = useState<TransferItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [ovData, txData] = await Promise.all([getOverview(), getTransfers(15)]);
      setOverview(ovData);
      setTransfers(txData);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch platform telemetry');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 10000);
    return () => clearInterval(timer);
  }, []);

  const attentionTransfers = transfers.filter((t) => t.attention_required);
  const allNodesReachable =
    overview &&
    overview.reachability?.coordinator &&
    overview.reachability?.['ledger-1'] &&
    overview.reachability?.['ledger-2'];

  if (loading && !overview) {
    return (
      <div
        style={{
          padding: '5rem 0',
          textAlign: 'center',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.8125rem',
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          color: '#94A3B8',
        }}
      >
        Polling 3-database topology &amp; invariant telemetry...
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Primary Grouped Operational Surface */}
      <div
        className="glass-operational"
        style={{
          borderRadius: 'var(--radius-primary, 28px)',
          background: 'rgba(14, 20, 34, 0.78)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.09)',
          boxShadow: '0 24px 64px -16px rgba(0, 0, 0, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.10)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Top Control Plane Banner */}
        <div
          style={{
            padding: '2rem 2.25rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.25rem',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '1rem',
            }}
          >
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.45rem',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.6875rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: '#38BDF8',
                  background: 'rgba(6, 182, 212, 0.12)',
                  padding: '0.2rem 0.6rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  border: '1px solid rgba(6, 182, 212, 0.25)',
                  marginBottom: '0.5rem',
                }}
              >
                <span>●</span>
                <span>Operational Control Plane</span>
              </div>
              <h1
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: 'clamp(1.75rem, 3vw, 2.5rem)',
                  fontWeight: 700,
                  color: '#F8FAFC',
                  letterSpacing: '-0.02em',
                  lineHeight: 1.15,
                }}
              >
                Platform Telemetry &amp; Conservation State
              </h1>
              <p style={{ fontSize: '0.875rem', color: '#94A3B8', maxWidth: '720px', marginTop: '0.35rem', lineHeight: 1.5 }}>
                Application-level TCC coordination across three independently reachable PostgreSQL instances. Transactional outbox relays, participant hold reservations, and cross-ledger reconciliation.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <Link
                href="/console/reconciliation"
                className="btn-editorial btn-primary"
                style={{ fontSize: '0.75rem', padding: '0.5rem 1rem', borderRadius: 'var(--radius-pill, 9999px)' }}
              >
                Run Audit Invariant
              </Link>
              <Link
                href="/console/experiments"
                className="btn-editorial btn-secondary"
                style={{ fontSize: '0.75rem', padding: '0.5rem 1rem', borderRadius: 'var(--radius-pill, 9999px)' }}
              >
                Failure Lab
              </Link>
            </div>
          </div>

          {error && (
            <div
              role="alert"
              style={{
                padding: '0.875rem 1.25rem',
                borderRadius: 'var(--radius-control, 14px)',
                background: 'rgba(220, 38, 38, 0.15)',
                border: '1px solid rgba(220, 38, 38, 0.35)',
                color: '#FCA5A5',
                fontSize: '0.8125rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span>Failed to refresh platform telemetry: {error}</span>
              <button
                onClick={loadData}
                style={{
                  fontFamily: 'var(--font-mono)',
                  textDecoration: 'underline',
                  background: 'none',
                  border: 'none',
                  color: 'inherit',
                  cursor: 'pointer',
                }}
              >
                Retry
              </button>
            </div>
          )}
        </div>

        {/* Integrated KPI Metrics Band (Grouped within surface, separated by clean dividers) */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            backgroundColor: 'rgba(20, 28, 48, 0.50)',
          }}
        >
          {/* KPI 1 */}
          <div
            style={{
              padding: '1.5rem 2rem',
              borderRight: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8' }}>
              Total Accounts
            </span>
            <div style={{ marginTop: '0.6rem' }}>
              <span className="font-mono" style={{ fontSize: '1.85rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
                {formatNumber(overview?.total_accounts ?? 0)}
              </span>
              <span style={{ display: 'block', fontSize: '0.6875rem', color: '#64748B', marginTop: '0.2rem' }}>
                Across Ledger 1 &amp; Ledger 2
              </span>
            </div>
          </div>

          {/* KPI 2 */}
          <div
            style={{
              padding: '1.5rem 2rem',
              borderRight: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8' }}>
              Registered Customers
            </span>
            <div style={{ marginTop: '0.6rem' }}>
              <span className="font-mono" style={{ fontSize: '1.85rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
                {formatNumber(overview?.total_customers ?? 0)}
              </span>
              <span style={{ display: 'block', fontSize: '0.6875rem', color: '#64748B', marginTop: '0.2rem' }}>
                Provisioned in Coordinator Directory
              </span>
            </div>
          </div>

          {/* KPI 3 */}
          <div
            style={{
              padding: '1.5rem 2rem',
              borderRight: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8' }}>
              Settled Transfers
            </span>
            <div style={{ marginTop: '0.6rem' }}>
              <span className="font-mono" style={{ fontSize: '1.85rem', fontWeight: 700, color: '#34D399', letterSpacing: '-0.02em' }}>
                {formatNumber(overview?.settled_transfers ?? 0)}
              </span>
              <span style={{ display: 'block', fontSize: '0.6875rem', color: '#64748B', marginTop: '0.2rem' }}>
                Of {formatNumber(overview?.total_transfers ?? 0)} Total Created
              </span>
            </div>
          </div>

          {/* KPI 4 */}
          <div
            style={{
              padding: '1.5rem 2rem',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8' }}>
              In-Flight TCC
            </span>
            <div style={{ marginTop: '0.6rem' }}>
              <span
                className="font-mono"
                style={{
                  fontSize: '1.85rem',
                  fontWeight: 700,
                  letterSpacing: '-0.02em',
                  color: overview?.pending_transfers ? '#F59E0B' : '#94A3B8',
                }}
              >
                {formatNumber(overview?.pending_transfers ?? 0)}
              </span>
              <span style={{ display: 'block', fontSize: '0.6875rem', color: '#64748B', marginTop: '0.2rem' }}>
                {overview?.oldest_pending_age_seconds
                  ? `Oldest: ${overview.oldest_pending_age_seconds}s age`
                  : 'Zero residual queue lag'}
              </span>
            </div>
          </div>
        </div>

        {/* Grouped Operational Mesh: 3-Database Topology + Clearing Conservation */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
            padding: '2rem',
            gap: '2rem',
          }}
        >
          {/* Left Sub-Region: Three Independently Reachable PostgreSQL Instances */}
          <div
            style={{
              background: 'rgba(20, 28, 48, 0.60)',
              borderRadius: 'var(--radius-secondary, 20px)',
              padding: '1.75rem',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingBottom: '1rem',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                  marginBottom: '1rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: allNodesReachable ? '#10B981' : '#EF4444',
                      boxShadow: allNodesReachable ? '0 0 10px #10B981' : '0 0 10px #EF4444',
                    }}
                  />
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#38BDF8' }}>
                    Three Autonomous PostgreSQL Instances
                  </span>
                </div>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.6875rem',
                    color: allNodesReachable ? '#34D399' : '#FCA5A5',
                    background: allNodesReachable ? 'rgba(5, 150, 105, 0.15)' : 'rgba(220, 38, 38, 0.15)',
                    padding: '0.2rem 0.55rem',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    fontWeight: 700,
                  }}
                >
                  {allNodesReachable ? 'ONLINE / HEALTHY' : 'PARTIAL DEGRADED'}
                </span>
              </div>

              <p style={{ fontSize: '0.8125rem', color: '#94A3B8', lineHeight: 1.5, marginBottom: '1.25rem' }}>
                LedgerGuard coordinates three independently reachable PostgreSQL 17 instances using an application-level TCC workflow without distributed locks.
              </p>

              {/* 3 Node Cards */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {/* Node 1: Coordinator */}
                <div
                  style={{
                    padding: '1rem 1.25rem',
                    borderRadius: 'var(--radius-control, 14px)',
                    background: 'rgba(11, 15, 25, 0.70)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: overview?.reachability?.coordinator ? '#10B981' : '#EF4444',
                      }}
                    />
                    <div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', fontWeight: 700, color: '#F8FAFC' }}>
                        Coordinator DB
                      </div>
                      <div style={{ fontSize: '0.6875rem', color: '#64748B' }}>localhost:5442 · coordinator_db</div>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.6875rem' }}>
                    <span style={{ color: overview?.reachability?.coordinator ? '#34D399' : '#EF4444', fontWeight: 700 }}>
                      {overview?.reachability?.coordinator ? 'REACHABLE' : 'UNREACHABLE'}
                    </span>
                    <div style={{ fontSize: '0.625rem', color: '#64748B' }}>TCC Decisions &amp; Routing</div>
                  </div>
                </div>

                {/* Node 2: Ledger 1 */}
                <div
                  style={{
                    padding: '1rem 1.25rem',
                    borderRadius: 'var(--radius-control, 14px)',
                    background: 'rgba(11, 15, 25, 0.70)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: overview?.reachability?.['ledger-1'] ? '#10B981' : '#EF4444',
                      }}
                    />
                    <div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', fontWeight: 700, color: '#F8FAFC' }}>
                        Participant Ledger 1
                      </div>
                      <div style={{ fontSize: '0.6875rem', color: '#64748B' }}>localhost:5443 · ledger1_db</div>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.6875rem' }}>
                    <span style={{ color: overview?.reachability?.['ledger-1'] ? '#34D399' : '#EF4444', fontWeight: 700 }}>
                      {overview?.reachability?.['ledger-1'] ? 'REACHABLE' : 'UNREACHABLE'}
                    </span>
                    <div style={{ fontSize: '0.625rem', color: '#64748B' }}>Double-Entry &amp; Holds</div>
                  </div>
                </div>

                {/* Node 3: Ledger 2 */}
                <div
                  style={{
                    padding: '1rem 1.25rem',
                    borderRadius: 'var(--radius-control, 14px)',
                    background: 'rgba(11, 15, 25, 0.70)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: overview?.reachability?.['ledger-2'] ? '#10B981' : '#EF4444',
                      }}
                    />
                    <div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', fontWeight: 700, color: '#F8FAFC' }}>
                        Participant Ledger 2
                      </div>
                      <div style={{ fontSize: '0.6875rem', color: '#64748B' }}>localhost:5444 · ledger2_db</div>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.6875rem' }}>
                    <span style={{ color: overview?.reachability?.['ledger-2'] ? '#34D399' : '#EF4444', fontWeight: 700 }}>
                      {overview?.reachability?.['ledger-2'] ? 'REACHABLE' : 'UNREACHABLE'}
                    </span>
                    <div style={{ fontSize: '0.625rem', color: '#64748B' }}>Double-Entry &amp; Holds</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Sub-Region: Clearing Conservation Invariant */}
          <div
            style={{
              background: 'rgba(20, 28, 48, 0.60)',
              borderRadius: 'var(--radius-secondary, 20px)',
              padding: '1.75rem',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingBottom: '1rem',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                  marginBottom: '1rem',
                }}
              >
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#38BDF8', fontWeight: 700 }}>
                  Clearing Conservation Invariant
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.6875rem',
                    padding: '0.2rem 0.55rem',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    background: overview?.clearing_sum === 0 ? 'rgba(5, 150, 105, 0.15)' : 'rgba(220, 38, 38, 0.15)',
                    color: overview?.clearing_sum === 0 ? '#34D399' : '#EF4444',
                    fontWeight: 700,
                  }}
                >
                  {overview?.clearing_sum === 0 ? 'Σ ΔL = ₹0.00 (VERIFIED)' : 'INVARIANT BREACH'}
                </span>
              </div>

              <p style={{ fontSize: '0.8125rem', color: '#94A3B8', lineHeight: 1.5, marginBottom: '1.25rem' }}>
                Funds in cross-ledger transfers pass through dedicated clearing liability accounts. At all times, the algebraic sum of net balance changes across all clearing accounts must equal exactly zero.
              </p>

              <div
                style={{
                  padding: '1.25rem',
                  borderRadius: 'var(--radius-control, 14px)',
                  background: 'rgba(11, 15, 25, 0.70)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <span style={{ color: '#94A3B8' }}>Clearing Sum Across Ledgers:</span>
                  <span style={{ fontSize: '1.1rem', fontWeight: 700, color: overview?.clearing_sum === 0 ? '#34D399' : '#EF4444' }}>
                    {formatINR(overview?.clearing_sum ?? 0)}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748B' }}>Last Reconciliation Audit:</span>
                  <span style={{ color: '#F8FAFC', fontWeight: 600 }}>
                    {overview?.last_reconciliation_status || 'UNKNOWN'}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ color: '#64748B' }}>Fault Injection Sandbox:</span>
                  <span style={{ color: overview?.fault_injection_enabled ? '#F59E0B' : '#64748B', fontWeight: 600 }}>
                    {overview?.fault_injection_enabled ? 'ENABLED (NON-PRODUCTION)' : 'DISABLED (PRODUCTION SAFE)'}
                  </span>
                </div>
              </div>
            </div>

            <div
              style={{
                marginTop: '1.5rem',
                paddingTop: '1rem',
                borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '0.75rem',
              }}
            >
              <span style={{ color: '#64748B' }}>Audited via stopped-and-drained multi-db query</span>
              <Link href="/console/reconciliation" style={{ color: '#38BDF8', textDecoration: 'none', fontFamily: 'var(--font-mono)' }}>
                View Audit Findings →
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Attention & Recovery Queue (Only renders if attention_required transfers exist) */}
      {attentionTransfers.length > 0 && (
        <div
          style={{
            padding: '1.75rem',
            background: 'rgba(69, 26, 3, 0.35)',
            border: '1px solid rgba(245, 158, 11, 0.40)',
            borderRadius: 'var(--radius-secondary, 20px)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(245, 158, 11, 0.20)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#F59E0B', animation: 'spin 1.5s linear infinite' }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#FCD34D', fontWeight: 700 }}>
                Recovery Attention Queue ({attentionTransfers.length} Transfers Pending Forward Recovery)
              </span>
            </div>
            <span style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: '#FDE68A' }}>
              Orchestrator Worker Active
            </span>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', textAlign: 'left', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
              <thead>
                <tr style={{ color: '#A1A1AA', borderBottom: '1px solid rgba(245, 158, 11, 0.20)' }}>
                  <th style={{ padding: '0.5rem 0' }}>Transfer ID</th>
                  <th style={{ padding: '0.5rem 0' }}>Route</th>
                  <th style={{ padding: '0.5rem 0' }}>Amount</th>
                  <th style={{ padding: '0.5rem 0' }}>Current State</th>
                  <th style={{ padding: '0.5rem 0' }}>Attention Reason</th>
                  <th style={{ padding: '0.5rem 0', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody style={{ color: '#FDE68A' }}>
                {attentionTransfers.map((tx) => (
                  <tr key={tx.transfer_id} style={{ borderBottom: '1px solid rgba(245, 158, 11, 0.10)' }}>
                    <td style={{ padding: '0.65rem 0', fontWeight: 700 }}>{tx.transfer_id.slice(0, 12)}...</td>
                    <td style={{ padding: '0.65rem 0' }}>{tx.source_ledger_id} → {tx.destination_ledger_id}</td>
                    <td style={{ padding: '0.65rem 0' }}>{formatINR(tx.amount_minor)}</td>
                    <td style={{ padding: '0.65rem 0' }}>{tx.state}</td>
                    <td style={{ padding: '0.65rem 0', color: '#FBBF24' }}>{tx.attention_reason || 'Crash during commit boundary'}</td>
                    <td style={{ padding: '0.65rem 0', textAlign: 'right' }}>
                      <Link href={`/console/transfers/${tx.transfer_id}`} style={{ color: '#38BDF8', textDecoration: 'none' }}>
                        Inspect Timeline
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent Workflow Activity Table (Rounded Container & Translucent Header) */}
      <div
        className="glass-supporting-dark"
        style={{
          borderRadius: 'var(--radius-primary, 28px)',
          background: 'rgba(14, 20, 34, 0.75)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 16px 40px -12px rgba(0, 0, 0, 0.55)',
          padding: '2rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: '1.25rem', marginBottom: '1.25rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <div>
            <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', fontWeight: 700, color: '#F8FAFC' }}>
              Recent Distributed Transfers
            </h2>
            <p style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '0.2rem' }}>
              Latest cross-ledger TCC orchestrations and settled transfers
            </p>
          </div>
          <Link
            href="/console/transfers"
            style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: '#38BDF8', textDecoration: 'none' }}
          >
            Explore All Transfers →
          </Link>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', textAlign: 'left', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6875rem', color: '#94A3B8', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <th style={{ padding: '0.75rem 1rem 0.75rem 0', fontWeight: 600 }}>Transfer ID</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>Amount</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>Route</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>Decision</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>State</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>Created</th>
                <th style={{ padding: '0.75rem 0 0.75rem 1rem', fontWeight: 600, textAlign: 'right' }}>Timeline</th>
              </tr>
            </thead>
            <tbody style={{ fontFamily: 'var(--font-mono)', color: '#CBD5E1' }}>
              {transfers.slice(0, 8).map((tx) => (
                <tr
                  key={tx.transfer_id}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    transition: 'background-color 0.15s ease',
                  }}
                >
                  <td style={{ padding: '0.85rem 1rem 0.85rem 0', fontWeight: 600, color: '#F8FAFC' }}>
                    <Link
                      href={`/console/transfers/${tx.transfer_id}`}
                      style={{ color: 'inherit', textDecoration: 'none', display: 'inline-block', minHeight: '24px', lineHeight: '24px' }}
                    >
                      {tx.transfer_id.slice(0, 8)}...
                    </Link>
                  </td>
                  <td style={{ padding: '0.85rem 1rem', fontWeight: 700, color: '#FFFFFF' }}>{formatINR(tx.amount_minor)}</td>
                  <td style={{ padding: '0.85rem 1rem', fontSize: '0.75rem', color: '#94A3B8' }}>
                    {tx.source_ledger_id} → {tx.destination_ledger_id}
                  </td>
                  <td style={{ padding: '0.85rem 1rem' }}>
                    <span
                      style={{
                        padding: '0.2rem 0.55rem',
                        fontSize: '0.625rem',
                        borderRadius: 'var(--radius-pill, 9999px)',
                        fontWeight: 700,
                        backgroundColor:
                          tx.decision === 'COMMIT'
                            ? 'rgba(5, 150, 105, 0.15)'
                            : tx.decision === 'CANCEL'
                            ? 'rgba(220, 38, 38, 0.15)'
                            : 'rgba(255, 255, 255, 0.08)',
                        color:
                          tx.decision === 'COMMIT'
                            ? '#34D399'
                            : tx.decision === 'CANCEL'
                            ? '#EF4444'
                            : '#94A3B8',
                      }}
                    >
                      {tx.decision || 'PENDING'}
                    </span>
                  </td>
                  <td style={{ padding: '0.85rem 1rem' }}>
                    <span
                      style={{
                        padding: '0.2rem 0.55rem',
                        fontSize: '0.625rem',
                        borderRadius: 'var(--radius-pill, 9999px)',
                        fontWeight: 700,
                        backgroundColor:
                          tx.state === 'SETTLED'
                            ? 'rgba(5, 150, 105, 0.15)'
                            : tx.state === 'CANCELLED'
                            ? 'rgba(220, 38, 38, 0.15)'
                            : 'rgba(245, 158, 11, 0.15)',
                        color:
                          tx.state === 'SETTLED'
                            ? '#34D399'
                            : tx.state === 'CANCELLED'
                            ? '#EF4444'
                            : '#F59E0B',
                      }}
                    >
                      {tx.state}
                    </span>
                  </td>
                  <td style={{ padding: '0.85rem 1rem', fontSize: '0.75rem', color: '#94A3B8' }}>
                    {new Date(tx.created_at).toLocaleTimeString()}
                  </td>
                  <td style={{ padding: '0.85rem 0 0.85rem 1rem', textAlign: 'right' }}>
                    <Link
                      href={`/console/transfers/${tx.transfer_id}`}
                      style={{ color: '#38BDF8', textDecoration: 'none', display: 'inline-block', minHeight: '24px', lineHeight: '24px' }}
                    >
                      Inspect →
                    </Link>
                  </td>
                </tr>
              ))}
              {transfers.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ padding: '2rem', textAlign: 'center', color: '#64748B' }}>
                    No transfers executed yet in current coordinator database.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
