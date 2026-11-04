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
  const isHealthy =
    overview &&
    Object.values(overview.reachability).every(Boolean) &&
    overview.clearing_sum === 0 &&
    attentionTransfers.length === 0;

  if (loading && !overview) {
    return (
      <div className="py-20 text-center font-mono text-xs uppercase tracking-widest text-[#64748B]">
        Polling 3-database topology &amp; invariant telemetry...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Top Editorial Banner */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-[#1E293B]">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 bg-[#38BDF8]" />
            Continuous Operational Workspace
          </div>
          <h1 className="text-3xl md:text-4xl font-serif text-[#F8FAFC] font-normal tracking-tight">
            Platform Telemetry &amp; Conservation State
          </h1>
          <p className="text-xs text-[#94A3B8] max-w-2xl mt-1">
            Application-level TCC coordination across three independently reachable PostgreSQL instances. Transactional outbox relays, participant hold reservations, and cross-ledger reconciliation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/console/reconciliation"
            className="px-4 py-2 bg-[#1D4ED8] hover:bg-[#2563EB] text-white text-xs font-mono uppercase tracking-wider transition-colors no-underline"
          >
            Run Audit Invariant
          </Link>
          <Link
            href="/console/experiments"
            className="px-4 py-2 bg-[#1E293B] hover:bg-[#334155] text-[#E2E8F0] text-xs font-mono uppercase tracking-wider transition-colors no-underline"
          >
            Failure Lab
          </Link>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-[#7F1D1D]/30 border-l-2 border-[#DC2626] text-xs text-[#FCA5A5] flex items-center justify-between">
          <span>Failed to refresh platform telemetry: {error}</span>
          <button onClick={loadData} className="font-mono underline bg-transparent border-0 text-inherit cursor-pointer">
            Retry
          </button>
        </div>
      )}

      {/* Primary KPI Grid (Tabular Numerals, Square Panels) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-5 bg-[#0F172A] border border-[#1E293B] flex flex-col justify-between">
          <span className="font-mono text-[11px] uppercase tracking-wider text-[#64748B]">Total Accounts</span>
          <div className="mt-3">
            <span className="text-3xl font-mono font-bold text-white tracking-tight">
              {formatNumber(overview?.total_accounts ?? 0)}
            </span>
            <span className="block text-[10px] text-[#94A3B8] mt-1">Across Ledger 1 &amp; Ledger 2</span>
          </div>
        </div>

        <div className="p-5 bg-[#0F172A] border border-[#1E293B] flex flex-col justify-between">
          <span className="font-mono text-[11px] uppercase tracking-wider text-[#64748B]">Registered Customers</span>
          <div className="mt-3">
            <span className="text-3xl font-mono font-bold text-white tracking-tight">
              {formatNumber(overview?.total_customers ?? 0)}
            </span>
            <span className="block text-[10px] text-[#94A3B8] mt-1">Provisioned in Coordinator Directory</span>
          </div>
        </div>

        <div className="p-5 bg-[#0F172A] border border-[#1E293B] flex flex-col justify-between">
          <span className="font-mono text-[11px] uppercase tracking-wider text-[#64748B]">Settled Transfers</span>
          <div className="mt-3">
            <span className="text-3xl font-mono font-bold text-[#10B981] tracking-tight">
              {formatNumber(overview?.settled_transfers ?? 0)}
            </span>
            <span className="block text-[10px] text-[#94A3B8] mt-1">
              Of {formatNumber(overview?.total_transfers ?? 0)} Total Created
            </span>
          </div>
        </div>

        <div className="p-5 bg-[#0F172A] border border-[#1E293B] flex flex-col justify-between">
          <span className="font-mono text-[11px] uppercase tracking-wider text-[#64748B]">In-Flight TCC</span>
          <div className="mt-3">
            <span className={`text-3xl font-mono font-bold tracking-tight ${overview?.pending_transfers ? 'text-[#F59E0B]' : 'text-[#94A3B8]'}`}>
              {formatNumber(overview?.pending_transfers ?? 0)}
            </span>
            <span className="block text-[10px] text-[#94A3B8] mt-1">
              {overview?.oldest_pending_age_seconds
                ? `Oldest: ${overview.oldest_pending_age_seconds}s age`
                : 'Zero residual queue lag'}
            </span>
          </div>
        </div>
      </div>

      {/* Split Operational Telemetry: Three Independently Reachable PostgreSQL Instances + Clearing Conservation Invariant */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: 3-Database Topology */}
        <div className="lg:col-span-6 p-6 bg-[#0F172A] border border-[#1E293B] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
              <span className="font-mono text-xs uppercase tracking-wider text-[#38BDF8] font-semibold">
                Autonomous Database Topology
              </span>
              <span className="font-mono text-[11px] text-[#10B981] bg-[#064E3B]/40 px-2 py-0.5">
                PostgreSQL 17.x
              </span>
            </div>

            <p className="text-xs text-[#94A3B8] my-4 leading-relaxed">
              LedgerGuard coordinates three independently reachable PostgreSQL instances using an application-level TCC workflow. The Coordinator database manages transfer intents, durable decision state, and account routing. Ledger 1 and Ledger 2 participant databases maintain independent double-entry journals.
            </p>

            {/* 3 Node Rows */}
            <div className="flex flex-col gap-3">
              {/* Coordinator */}
              <div className="p-3.5 bg-[#0B0F17] border border-[#1E293B] flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`w-2 h-2 ${overview?.reachability?.coordinator ? 'bg-[#10B981]' : 'bg-[#EF4444]'}`} />
                  <div>
                    <div className="font-mono text-xs font-semibold text-white">Coordinator DB</div>
                    <div className="text-[11px] text-[#64748B]">localhost:5442 · coordinator_db</div>
                  </div>
                </div>
                <div className="text-right font-mono text-[11px]">
                  <span className={overview?.reachability?.coordinator ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                    {overview?.reachability?.coordinator ? 'REACHABLE' : 'UNREACHABLE'}
                  </span>
                  <div className="text-[10px] text-[#64748B]">TCC Decisions &amp; Directory</div>
                </div>
              </div>

              {/* Ledger 1 */}
              <div className="p-3.5 bg-[#0B0F17] border border-[#1E293B] flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`w-2 h-2 ${overview?.reachability?.['ledger-1'] ? 'bg-[#10B981]' : 'bg-[#EF4444]'}`} />
                  <div>
                    <div className="font-mono text-xs font-semibold text-white">Participant Ledger 1</div>
                    <div className="text-[11px] text-[#64748B]">localhost:5443 · ledger1_db</div>
                  </div>
                </div>
                <div className="text-right font-mono text-[11px]">
                  <span className={overview?.reachability?.['ledger-1'] ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                    {overview?.reachability?.['ledger-1'] ? 'REACHABLE' : 'UNREACHABLE'}
                  </span>
                  <div className="text-[10px] text-[#64748B]">Double-Entry &amp; Holds</div>
                </div>
              </div>

              {/* Ledger 2 */}
              <div className="p-3.5 bg-[#0B0F17] border border-[#1E293B] flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`w-2 h-2 ${overview?.reachability?.['ledger-2'] ? 'bg-[#10B981]' : 'bg-[#EF4444]'}`} />
                  <div>
                    <div className="font-mono text-xs font-semibold text-white">Participant Ledger 2</div>
                    <div className="text-[11px] text-[#64748B]">localhost:5444 · ledger2_db</div>
                  </div>
                </div>
                <div className="text-right font-mono text-[11px]">
                  <span className={overview?.reachability?.['ledger-2'] ? 'text-[#10B981]' : 'text-[#EF4444]'}>
                    {overview?.reachability?.['ledger-2'] ? 'REACHABLE' : 'UNREACHABLE'}
                  </span>
                  <div className="text-[10px] text-[#64748B]">Double-Entry &amp; Holds</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Clearing Conservation Invariant */}
        <div className="lg:col-span-6 p-6 bg-[#0F172A] border border-[#1E293B] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
              <span className="font-mono text-xs uppercase tracking-wider text-[#38BDF8] font-semibold">
                Clearing Conservation Invariant
              </span>
              <span className={`font-mono text-[11px] px-2 py-0.5 ${overview?.clearing_sum === 0 ? 'text-[#10B981] bg-[#064E3B]/40' : 'text-[#EF4444] bg-[#7F1D1D]/40'}`}>
                {overview?.clearing_sum === 0 ? 'Σ ΔL = ₹0.00 (VERIFIED)' : 'INVARIANT BREACH'}
              </span>
            </div>

            <p className="text-xs text-[#94A3B8] my-4 leading-relaxed">
              Funds in cross-ledger transfers pass through dedicated clearing liability accounts. At all times, the algebraic sum of net balance changes across all clearing accounts must equal exactly zero.
            </p>

            <div className="p-4 bg-[#0B0F17] border border-[#1E293B] flex flex-col gap-3 font-mono text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-[#1E293B]">
                <span className="text-[#94A3B8]">Clearing Sum Across Ledgers:</span>
                <span className={`text-base font-bold ${overview?.clearing_sum === 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                  {formatINR(overview?.clearing_sum ?? 0)}
                </span>
              </div>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-[#64748B]">Last Reconciliation Status:</span>
                <span className="text-white font-semibold">
                  {overview?.last_reconciliation_status || 'UNKNOWN'}
                </span>
              </div>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-[#64748B]">Fault Injection Sandbox:</span>
                <span className={overview?.fault_injection_enabled ? 'text-[#F59E0B]' : 'text-[#64748B]'}>
                  {overview?.fault_injection_enabled ? 'ENABLED (NON-PRODUCTION)' : 'DISABLED (PRODUCTION SAFE)'}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-4 mt-4 border-t border-[#1E293B] flex items-center justify-between text-xs">
            <span className="text-[#64748B]">Audited via stopped-and-drained multi-db query</span>
            <Link href="/console/reconciliation" className="text-[#38BDF8] hover:underline font-mono text-xs">
              View Detailed Audit Findings &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Attention & Recovery Queue (Only renders if attention_required transfers exist) */}
      {attentionTransfers.length > 0 && (
        <div className="p-6 bg-[#451A03]/20 border border-[#F59E0B]/40">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-[#F59E0B]/20">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-[#F59E0B] animate-pulse" />
              <span className="font-mono text-xs uppercase tracking-wider text-[#F59E0B] font-bold">
                Recovery Attention Queue ({attentionTransfers.length} Transfers Pending Forward Recovery)
              </span>
            </div>
            <span className="text-[11px] font-mono text-[#FCD34D]">
              Orchestrator Worker Active
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="text-[#A1A1AA] border-b border-[#F59E0B]/20">
                  <th className="py-2">Transfer ID</th>
                  <th className="py-2">Route</th>
                  <th className="py-2">Amount</th>
                  <th className="py-2">Current State</th>
                  <th className="py-2">Attention Reason</th>
                  <th className="py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F59E0B]/10">
                {attentionTransfers.map((tx) => (
                  <tr key={tx.transfer_id} className="text-[#FDE68A]">
                    <td className="py-2.5 font-bold">{tx.transfer_id.slice(0, 12)}...</td>
                    <td className="py-2.5">{tx.source_ledger_id} &rarr; {tx.destination_ledger_id}</td>
                    <td className="py-2.5">{formatINR(tx.amount_minor)}</td>
                    <td className="py-2.5">{tx.state}</td>
                    <td className="py-2.5 text-[#FBBF24]">{tx.attention_reason || 'Crash during commit boundary'}</td>
                    <td className="py-2.5 text-right">
                      <Link
                        href={`/console/transfers/${tx.transfer_id}`}
                        className="text-[#38BDF8] hover:underline"
                      >
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

      {/* Recent Workflow Activity Table */}
      <div className="p-6 bg-[#0F172A] border border-[#1E293B]">
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-[#1E293B]">
          <div>
            <h2 className="text-base font-serif text-white tracking-tight">Recent Distributed Transfers</h2>
            <p className="text-xs text-[#94A3B8]">Latest cross-ledger TCC orchestrations and settled transfers</p>
          </div>
          <Link
            href="/console/transfers"
            className="text-xs font-mono text-[#38BDF8] hover:underline"
          >
            Explore All Transfers &rarr;
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="font-mono text-[#64748B] border-b border-[#1E293B]">
                <th className="py-2.5 font-medium">Transfer ID</th>
                <th className="py-2.5 font-medium">Amount</th>
                <th className="py-2.5 font-medium">Route</th>
                <th className="py-2.5 font-medium">Decision</th>
                <th className="py-2.5 font-medium">State</th>
                <th className="py-2.5 font-medium">Created</th>
                <th className="py-2.5 font-medium text-right">Timeline</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E293B] font-mono text-[#CBD5E1]">
              {transfers.slice(0, 8).map((tx) => (
                <tr key={tx.transfer_id} className="hover:bg-[#1E293B]/40 transition-colors">
                  <td className="py-3 font-semibold text-white">
                    <Link href={`/console/transfers/${tx.transfer_id}`} className="text-inherit hover:text-[#38BDF8] no-underline">
                      {tx.transfer_id.slice(0, 8)}...
                    </Link>
                  </td>
                  <td className="py-3 font-bold text-white">{formatINR(tx.amount_minor)}</td>
                  <td className="py-3 text-[11px] text-[#94A3B8]">
                    {tx.source_ledger_id} &rarr; {tx.destination_ledger_id}
                  </td>
                  <td className="py-3">
                    <span
                      className={`px-1.5 py-0.5 text-[10px] ${
                        tx.decision === 'COMMIT'
                          ? 'bg-[#064E3B] text-[#10B981]'
                          : tx.decision === 'CANCEL'
                          ? 'bg-[#7F1D1D] text-[#EF4444]'
                          : 'bg-[#1E293B] text-[#94A3B8]'
                      }`}
                    >
                      {tx.decision || 'PENDING'}
                    </span>
                  </td>
                  <td className="py-3">
                    <span
                      className={`px-1.5 py-0.5 text-[10px] ${
                        tx.state === 'SETTLED'
                          ? 'bg-[#064E3B]/60 text-[#10B981]'
                          : tx.state === 'CANCELLED'
                          ? 'bg-[#7F1D1D]/60 text-[#EF4444]'
                          : 'bg-[#78350F]/60 text-[#F59E0B]'
                      }`}
                    >
                      {tx.state}
                    </span>
                  </td>
                  <td className="py-3 text-[11px] text-[#64748B]">
                    {new Date(tx.created_at).toLocaleTimeString()}
                  </td>
                  <td className="py-3 text-right">
                    <Link
                      href={`/console/transfers/${tx.transfer_id}`}
                      className="text-[#38BDF8] hover:underline"
                    >
                      Inspect &rarr;
                    </Link>
                  </td>
                </tr>
              ))}
              {transfers.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-[#64748B]">
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
