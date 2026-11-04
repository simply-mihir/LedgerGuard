'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { AccountItem, StatementEntry } from '../../../../lib/types';
import { getAccounts, getAccountStatement } from '../../../../lib/api';
import { formatINR } from '../../../../lib/format';

export default function AccountDetailPage() {
  const params = useParams();
  const accountId = params?.accountId as string;

  const [account, setAccount] = useState<AccountItem | null>(null);
  const [statement, setStatement] = useState<StatementEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accountId) return;

    const loadData = async () => {
      setLoading(true);
      try {
        const [accts, stmt] = await Promise.all([
          getAccounts(),
          getAccountStatement(accountId, 50),
        ]);
        const found = accts.find((a) => a.account_id === accountId);
        setAccount(found || null);
        setStatement(stmt.entries || []);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch account ledger statement');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [accountId]);

  return (
    <div className="flex flex-col gap-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center gap-2 text-xs font-mono text-[#94A3B8]">
        <Link href="/console/accounts" className="hover:text-white no-underline text-inherit">
          &larr; Accounts Explorer
        </Link>
        <span>/</span>
        <span className="text-[#38BDF8]">{accountId}</span>
      </div>

      {/* Account Identity Header */}
      <div className="p-6 bg-[#0F172A] border border-[#1E293B] flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 bg-[#38BDF8]" />
            Authoritative Ledger Account
          </div>
          <h1 className="text-2xl md:text-3xl font-mono text-white font-bold tracking-tight">
            {accountId}
          </h1>
          <div className="flex flex-wrap items-center gap-3 mt-3 text-xs font-mono text-[#94A3B8]">
            <span>Customer: {account?.customer_id || 'Unknown'}</span>
            <span>&bull;</span>
            <span className="text-[#38BDF8]">Partition: {account?.ledger_id || 'ledger-1'}</span>
            <span>&bull;</span>
            <span>Currency: {account?.currency || 'INR'}</span>
            <span>&bull;</span>
            <span
              className={`px-2 py-0.5 text-[10px] ${
                account?.status === 'ACTIVE'
                  ? 'bg-[#064E3B] text-[#10B981]'
                  : 'bg-[#78350F] text-[#F59E0B]'
              }`}
            >
              {account?.status || 'ACTIVE'}
            </span>
          </div>
        </div>

        {/* Balance Breakdown Matrix */}
        <div className="grid grid-cols-3 gap-3 font-mono text-xs">
          <div className="p-3 bg-[#0B0F17] border border-[#1E293B]">
            <span className="text-[10px] text-[#64748B] uppercase block">Posted Balance</span>
            <span className="text-base font-bold text-white">
              {formatINR(account?.posted_balance_minor ?? 0)}
            </span>
          </div>
          <div className="p-3 bg-[#0B0F17] border border-[#1E293B]">
            <span className="text-[10px] text-[#64748B] uppercase block">Held in TCC</span>
            <span className="text-base font-bold text-[#F59E0B]">
              {formatINR(account?.held_amount_minor ?? 0)}
            </span>
          </div>
          <div className="p-3 bg-[#0B0F17] border border-[#1E293B]">
            <span className="text-[10px] text-[#64748B] uppercase block">Available</span>
            <span className="text-base font-bold text-[#10B981]">
              {formatINR(account?.available_balance_minor ?? 0)}
            </span>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-[#7F1D1D]/30 border-l-2 border-[#DC2626] text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      {/* Immutable Double-Entry Journal Statement */}
      <div className="p-6 bg-[#0F172A] border border-[#1E293B]">
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-[#1E293B]">
          <div>
            <h2 className="text-base font-serif text-white tracking-tight">
              Immutable Double-Entry Statement
            </h2>
            <p className="text-xs text-[#94A3B8]">
              Append-only journals persisted in participant database. Enforced by database trigger &lsquo;trg_prevent_journal_modification&rsquo;.
            </p>
          </div>
          <span className="font-mono text-xs text-[#64748B]">
            {statement.length} Recorded Entries
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="text-[#64748B] border-b border-[#1E293B] bg-[#0B0F17]">
                <th className="py-2.5 px-3 font-medium">Seq</th>
                <th className="py-2.5 px-3 font-medium">Journal ID</th>
                <th className="py-2.5 px-3 font-medium">Operation</th>
                <th className="py-2.5 px-3 font-medium">Side</th>
                <th className="py-2.5 px-3 font-medium text-right">Amount</th>
                <th className="py-2.5 px-3 font-medium">Timestamp</th>
                <th className="py-2.5 px-3 font-medium">Correlation / Transfer</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E293B] text-[#CBD5E1]">
              {statement.map((entry) => (
                <tr key={`${entry.journal_id}-${entry.line_no}`} className="hover:bg-[#1E293B]/40 transition-colors">
                  <td className="py-2.5 px-3 text-[#64748B]">{entry.account_sequence}</td>
                  <td className="py-2.5 px-3 text-white font-medium">{entry.journal_id.slice(0, 8)}...</td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 bg-[#0B0F17] border border-[#1E293B] text-[10px] text-[#38BDF8]">
                      {entry.operation_type}
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-1.5 py-0.5 text-[10px] font-bold ${
                        entry.side === 'DEBIT' ? 'text-[#F59E0B]' : 'text-[#10B981]'
                      }`}
                    >
                      {entry.side}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right font-bold text-white">
                    {formatINR(entry.amount_minor)}
                  </td>
                  <td className="py-2.5 px-3 text-[#64748B] text-[11px]">
                    {new Date(entry.created_at).toLocaleTimeString()}
                  </td>
                  <td className="py-2.5 px-3 text-[11px] text-[#94A3B8]">
                    {entry.transfer_id ? (
                      <Link
                        href={`/console/transfers/${entry.transfer_id}`}
                        className="text-[#38BDF8] hover:underline"
                      >
                        {entry.transfer_id.slice(0, 8)}...
                      </Link>
                    ) : (
                      entry.correlation_id || 'LOCAL'
                    )}
                  </td>
                </tr>
              ))}
              {statement.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-[#64748B]">
                    No journal lines posted yet for this account.
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
