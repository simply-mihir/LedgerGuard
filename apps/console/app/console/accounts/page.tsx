'use client';

import React, { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { AccountItem } from '../../../lib/types';
import { getAccounts } from '../../../lib/api';
import { formatINR } from '../../../lib/format';

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLedger, setSelectedLedger] = useState<'ALL' | 'ledger-1' | 'ledger-2'>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');

  const loadData = async () => {
    try {
      const data = await getAccounts();
      setAccounts(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch customer accounts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredAccounts = useMemo(() => {
    return accounts.filter((acct) => {
      if (selectedLedger !== 'ALL' && acct.ledger_id !== selectedLedger) return false;
      if (selectedStatus !== 'ALL' && acct.status !== selectedStatus) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          acct.account_id.toLowerCase().includes(q) ||
          acct.customer_id.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [accounts, selectedLedger, selectedStatus, searchQuery]);

  const totalPosted = filteredAccounts.reduce((acc, a) => acc + Math.max(0, a.posted_balance_minor), 0);
  const totalHeld = filteredAccounts.reduce((acc, a) => acc + a.held_amount_minor, 0);

  return (
    <div className="flex flex-col gap-6">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-[#1E293B]">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 bg-[#38BDF8]" />
            Partitioned Balance Store
          </div>
          <h1 className="text-3xl md:text-4xl font-serif text-[#F8FAFC] font-normal tracking-tight">
            Customer Ledgers &amp; Accounts
          </h1>
          <p className="text-xs text-[#94A3B8] max-w-2xl mt-1">
            Authoritative accounts partitioned across Ledger 1 and Ledger 2 PostgreSQL instances. Each account balances posted state, holds for in-flight TCC transfers, and immutable double-entry lines.
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="p-3 bg-[#0F172A] border border-[#1E293B]">
            <span className="text-[#64748B] block text-[10px] uppercase">Aggregated Posted Assets</span>
            <span className="text-white font-bold text-base">{formatINR(totalPosted)}</span>
          </div>
          <div className="p-3 bg-[#0F172A] border border-[#1E293B]">
            <span className="text-[#64748B] block text-[10px] uppercase">Active TCC Holds</span>
            <span className="text-[#F59E0B] font-bold text-base">{formatINR(totalHeld)}</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-[#7F1D1D]/30 border-l-2 border-[#DC2626] text-xs text-[#FCA5A5] flex items-center justify-between">
          <span>Failed to load accounts: {error}</span>
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
            placeholder="Search by Account ID or Customer UUID..."
            className="w-full bg-[#0B0F17] border border-[#1E293B] px-3.5 py-2 text-xs font-mono text-white placeholder:text-[#64748B] focus:outline-none focus:border-[#1D4ED8]"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Ledger Selector */}
          <div className="flex items-center gap-1 font-mono text-xs">
            <span className="text-[#64748B] text-[11px] uppercase mr-1">Partition:</span>
            {(['ALL', 'ledger-1', 'ledger-2'] as const).map((lid) => (
              <button
                key={lid}
                onClick={() => setSelectedLedger(lid)}
                className={`px-2.5 py-1 text-[11px] border-0 cursor-pointer font-mono ${
                  selectedLedger === lid
                    ? 'bg-[#1D4ED8] text-white font-semibold'
                    : 'bg-[#0B0F17] text-[#94A3B8] hover:bg-[#1E293B]'
                }`}
              >
                {lid === 'ALL' ? 'All Ledgers' : lid}
              </button>
            ))}
          </div>

          {/* Status Selector */}
          <div className="flex items-center gap-1 font-mono text-xs">
            <span className="text-[#64748B] text-[11px] uppercase mr-1">Status:</span>
            {(['ALL', 'ACTIVE', 'FROZEN', 'CLOSED'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setSelectedStatus(st)}
                className={`px-2.5 py-1 text-[11px] border-0 cursor-pointer font-mono ${
                  selectedStatus === st
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

      {/* Dense Accounts Table */}
      <div className="bg-[#0F172A] border border-[#1E293B] overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead>
            <tr className="text-[#64748B] border-b border-[#1E293B] bg-[#0B0F17]">
              <th className="py-3 px-4 font-medium">Account ID</th>
              <th className="py-3 px-4 font-medium">Customer Ref</th>
              <th className="py-3 px-4 font-medium">Ledger Partition</th>
              <th className="py-3 px-4 font-medium text-right">Posted Balance</th>
              <th className="py-3 px-4 font-medium text-right">Held in TCC</th>
              <th className="py-3 px-4 font-medium text-right">Available Balance</th>
              <th className="py-3 px-4 font-medium text-center">Status</th>
              <th className="py-3 px-4 font-medium text-right">Statement</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1E293B] text-[#CBD5E1]">
            {filteredAccounts.map((acct) => (
              <tr key={acct.account_id} className="hover:bg-[#1E293B]/40 transition-colors">
                <td className="py-3 px-4 font-semibold text-white">
                  <Link
                    href={`/console/accounts/${acct.account_id}`}
                    className="text-inherit hover:text-[#38BDF8] no-underline"
                  >
                    {acct.account_id}
                  </Link>
                </td>
                <td className="py-3 px-4 text-[#94A3B8] text-[11px]">
                  {acct.customer_id.slice(0, 8)}...
                </td>
                <td className="py-3 px-4">
                  <span className="px-2 py-0.5 bg-[#0B0F17] border border-[#1E293B] text-[11px] text-[#38BDF8]">
                    {acct.ledger_id}
                  </span>
                </td>
                <td className="py-3 px-4 text-right font-bold text-white">
                  {formatINR(acct.posted_balance_minor)}
                </td>
                <td className="py-3 px-4 text-right">
                  <span className={acct.held_amount_minor > 0 ? 'text-[#F59E0B] font-bold' : 'text-[#64748B]'}>
                    {formatINR(acct.held_amount_minor)}
                  </span>
                </td>
                <td className="py-3 px-4 text-right font-bold text-[#10B981]">
                  {formatINR(acct.available_balance_minor)}
                </td>
                <td className="py-3 px-4 text-center">
                  <span
                    className={`px-2 py-0.5 text-[10px] ${
                      acct.status === 'ACTIVE'
                        ? 'bg-[#064E3B] text-[#10B981]'
                        : acct.status === 'FROZEN'
                        ? 'bg-[#78350F] text-[#F59E0B]'
                        : 'bg-[#7F1D1D] text-[#EF4444]'
                    }`}
                  >
                    {acct.status}
                  </span>
                </td>
                <td className="py-3 px-4 text-right">
                  <Link
                    href={`/console/accounts/${acct.account_id}`}
                    className="text-[#38BDF8] hover:underline"
                  >
                    Statement &rarr;
                  </Link>
                </td>
              </tr>
            ))}
            {filteredAccounts.length === 0 && !loading && (
              <tr>
                <td colSpan={8} className="py-12 text-center text-[#64748B]">
                  No accounts match the specified criteria or query.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
