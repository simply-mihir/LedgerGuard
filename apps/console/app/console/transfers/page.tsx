'use client';

import React, { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { TransferItem } from '../../../lib/types';
import { getTransfers } from '../../../lib/api';
import { formatINR } from '../../../lib/format';

export default function TransfersPage() {
  const [transfers, setTransfers] = useState<TransferItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedState, setSelectedState] = useState<string>('ALL');
  const [selectedRoute, setSelectedRoute] = useState<string>('ALL');
  const [attentionOnly, setAttentionOnly] = useState(false);

  const loadData = async () => {
    try {
      const data = await getTransfers(100);
      setTransfers(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch transfers');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredTransfers = useMemo(() => {
    return transfers.filter((tx) => {
      if (attentionOnly && !tx.attention_required) return false;
      if (selectedState !== 'ALL' && tx.state !== selectedState) return false;
      if (selectedRoute === 'L1_TO_L2' && !(tx.source_ledger_id === 'ledger-1' && tx.destination_ledger_id === 'ledger-2')) return false;
      if (selectedRoute === 'L2_TO_L1' && !(tx.source_ledger_id === 'ledger-2' && tx.destination_ledger_id === 'ledger-1')) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          tx.transfer_id.toLowerCase().includes(q) ||
          tx.source_account_id.toLowerCase().includes(q) ||
          tx.destination_account_id.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [transfers, attentionOnly, selectedState, selectedRoute, searchQuery]);

  return (
    <div className="flex flex-col gap-6">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-[#1E293B]">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 bg-[#38BDF8]" />
            Distributed Coordination Engine
          </div>
          <h1 className="text-3xl md:text-4xl font-serif text-[#F8FAFC] font-normal tracking-tight">
            Try-Confirm-Cancel Transfers
          </h1>
          <p className="text-xs text-[#94A3B8] max-w-2xl mt-1">
            Application-level 3-phase TCC lifecycle. Source funds are reserved via temporary holds, destination accounts are prepared, a durable COMMIT decision is logged, and outbox workers asynchronously confirm or recover.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/console/experiments"
            className="px-4 py-2 bg-[#1E293B] hover:bg-[#334155] text-white text-xs font-mono uppercase tracking-wider transition-colors no-underline"
          >
            Inject Failure &rarr;
          </Link>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-[#7F1D1D]/30 border-l-2 border-[#DC2626] text-xs text-[#FCA5A5] flex items-center justify-between">
          <span>Failed to load transfers: {error}</span>
          <button onClick={loadData} className="font-mono underline bg-transparent border-0 text-inherit cursor-pointer">
            Retry
          </button>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="p-4 bg-[#0F172A] border border-[#1E293B] flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
        <div className="flex-1 max-w-md">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by Transfer ID or Account ID..."
            className="w-full bg-[#0B0F17] border border-[#1E293B] px-3.5 py-2 text-xs font-mono text-white placeholder:text-[#64748B] focus:outline-none focus:border-[#1D4ED8]"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Attention toggle */}
          <button
            onClick={() => setAttentionOnly(!attentionOnly)}
            className={`px-3 py-1 text-[11px] font-mono border-0 cursor-pointer ${
              attentionOnly ? 'bg-[#F59E0B] text-black font-bold' : 'bg-[#0B0F17] text-[#94A3B8] hover:bg-[#1E293B]'
            }`}
          >
            {attentionOnly ? '⚠ Attention Required Only' : 'Show All'}
          </button>

          {/* Route filter */}
          <div className="flex items-center gap-1 font-mono text-xs">
            <span className="text-[#64748B] text-[11px] uppercase mr-1">Route:</span>
            {(['ALL', 'L1_TO_L2', 'L2_TO_L1'] as const).map((r) => (
              <button
                key={r}
                onClick={() => setSelectedRoute(r)}
                className={`px-2.5 py-1 text-[11px] border-0 cursor-pointer font-mono ${
                  selectedRoute === r
                    ? 'bg-[#1D4ED8] text-white font-semibold'
                    : 'bg-[#0B0F17] text-[#94A3B8] hover:bg-[#1E293B]'
                }`}
              >
                {r === 'ALL' ? 'All Routes' : r === 'L1_TO_L2' ? 'L1 → L2' : 'L2 → L1'}
              </button>
            ))}
          </div>

          {/* State filter */}
          <div className="flex items-center gap-1 font-mono text-xs">
            <span className="text-[#64748B] text-[11px] uppercase mr-1">State:</span>
            {(['ALL', 'SETTLED', 'CANCELLED', 'COMMITTED', 'PREPARING'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setSelectedState(st)}
                className={`px-2.5 py-1 text-[11px] border-0 cursor-pointer font-mono ${
                  selectedState === st
                    ? 'bg-[#1D4ED8] text-white font-semibold'
                    : 'bg-[#0B0F17] text-[#94A3B8] hover:bg-[#1E293B]'
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Dense Transfers Table */}
      <div className="bg-[#0F172A] border border-[#1E293B] overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead>
            <tr className="text-[#64748B] border-b border-[#1E293B] bg-[#0B0F17]">
              <th className="py-3 px-4 font-medium">Transfer ID</th>
              <th className="py-3 px-4 font-medium">Amount</th>
              <th className="py-3 px-4 font-medium">Route</th>
              <th className="py-3 px-4 font-medium">Durable Decision</th>
              <th className="py-3 px-4 font-medium">Workflow State</th>
              <th className="py-3 px-4 font-medium">Created Timestamp</th>
              <th className="py-3 px-4 font-medium text-right">TCC Lifecycle</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1E293B] text-[#CBD5E1]">
            {filteredTransfers.map((tx) => (
              <tr key={tx.transfer_id} className="hover:bg-[#1E293B]/40 transition-colors">
                <td className="py-3 px-4 font-semibold text-white">
                  <Link
                    href={`/console/transfers/${tx.transfer_id}`}
                    className="text-inherit hover:text-[#38BDF8] no-underline flex items-center gap-2"
                  >
                    {tx.attention_required && <span className="w-2 h-2 bg-[#F59E0B]" title="Requires recovery attention" />}
                    <span>{tx.transfer_id.slice(0, 12)}...</span>
                  </Link>
                </td>
                <td className="py-3 px-4 font-bold text-white">
                  {formatINR(tx.amount_minor)}
                </td>
                <td className="py-3 px-4 text-[#94A3B8] text-[11px]">
                  {tx.source_ledger_id} &rarr; {tx.destination_ledger_id}
                </td>
                <td className="py-3 px-4">
                  <span
                    className={`px-2 py-0.5 text-[10px] ${
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
                <td className="py-3 px-4">
                  <span
                    className={`px-2 py-0.5 text-[10px] ${
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
                <td className="py-3 px-4 text-[11px] text-[#64748B]">
                  {new Date(tx.created_at).toLocaleTimeString()}
                </td>
                <td className="py-3 px-4 text-right">
                  <Link
                    href={`/console/transfers/${tx.transfer_id}`}
                    className="text-[#38BDF8] hover:underline"
                  >
                    Inspect Timeline &rarr;
                  </Link>
                </td>
              </tr>
            ))}
            {filteredTransfers.length === 0 && !loading && (
              <tr>
                <td colSpan={7} className="py-12 text-center text-[#64748B]">
                  No transfers found matching filter criteria.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
