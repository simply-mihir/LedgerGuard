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
        <Link href="/console/accounts" className="hover:text-white no-underline text-inherit flex items-center gap-1.5 transition-colors">
          <span>←</span>
          <span>Accounts Explorer</span>
        </Link>
        <span>/</span>
        <span className="text-[#38BDF8]">{accountId}</span>
      </div>

      {/* Account Identity Header Surface */}
      <div
        style={{
          borderRadius: 'var(--radius-primary, 28px)',
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5)',
          padding: '1.75rem',
        }}
        className="flex flex-col md:flex-row md:items-center justify-between gap-6"
      >
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] shadow-[0_0_8px_rgba(56,189,248,0.6)]" />
            Authoritative Ledger Account
          </div>
          <h1 className="text-2xl md:text-3xl font-mono text-white font-bold tracking-tight">
            {accountId}
          </h1>
          <div className="flex flex-wrap items-center gap-3 mt-3 text-xs font-mono text-[#94A3B8]">
            <span>Customer: <span className="text-[#CBD5E1]">{account?.customer_id || 'Unknown'}</span></span>
            <span>•</span>
            <span className="text-[#38BDF8]">Partition: {account?.ledger_id || 'ledger-1'}</span>
            <span>•</span>
            <span>Currency: {account?.currency || 'INR'}</span>
            <span>•</span>
            <span
              style={{
                padding: '0.2rem 0.6rem',
                fontSize: '0.625rem',
                borderRadius: 'var(--radius-pill, 9999px)',
                fontWeight: 700,
                backgroundColor:
                  account?.status === 'ACTIVE'
                    ? 'rgba(5, 150, 105, 0.15)'
                    : 'rgba(245, 158, 11, 0.15)',
                color: account?.status === 'ACTIVE' ? '#34D399' : '#F59E0B',
              }}
            >
              {account?.status || 'ACTIVE'}
            </span>
          </div>
        </div>

        {/* Balance Breakdown Matrix */}
        <div className="grid grid-cols-3 gap-3 font-mono text-xs">
          <div
            style={{
              padding: '0.875rem 1rem',
              borderRadius: 'var(--radius-control, 14px)',
              background: 'rgba(11, 15, 23, 0.7)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <span className="text-[10px] text-[#94A3B8] uppercase block font-medium">Posted Balance</span>
            <span className="text-base font-bold text-white mt-0.5 block">
              {formatINR(account?.posted_balance_minor ?? 0)}
            </span>
          </div>
          <div
            style={{
              padding: '0.875rem 1rem',
              borderRadius: 'var(--radius-control, 14px)',
              background: 'rgba(11, 15, 23, 0.7)',
              border: '1px solid rgba(245, 158, 11, 0.2)',
            }}
          >
            <span className="text-[10px] text-[#94A3B8] uppercase block font-medium">Held in TCC</span>
            <span className="text-base font-bold text-[#F59E0B] mt-0.5 block">
              {formatINR(account?.held_amount_minor ?? 0)}
            </span>
          </div>
          <div
            style={{
              padding: '0.875rem 1rem',
              borderRadius: 'var(--radius-control, 14px)',
              background: 'rgba(11, 15, 23, 0.7)',
              border: '1px solid rgba(16, 185, 129, 0.2)',
            }}
          >
            <span className="text-[10px] text-[#94A3B8] uppercase block font-medium">Available</span>
            <span className="text-base font-bold text-[#34D399] mt-0.5 block">
              {formatINR(account?.available_balance_minor ?? 0)}
            </span>
          </div>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '1rem 1.25rem',
            borderRadius: 'var(--radius-control, 14px)',
            background: 'rgba(127, 29, 29, 0.3)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#FCA5A5',
            fontSize: '0.75rem',
          }}
        >
          {error}
        </div>
      )}

      {/* Immutable Double-Entry Journal Statement */}
      <div
        style={{
          borderRadius: 'var(--radius-primary, 28px)',
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5)',
          padding: '1.75rem',
        }}
      >
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-white/[0.08]">
          <div>
            <h2 className="text-base font-serif text-white tracking-tight">
              Immutable Double-Entry Statement
            </h2>
            <p className="text-xs text-[#94A3B8] mt-0.5">
              Append-only journals persisted in participant database. Enforced by database trigger &lsquo;trg_prevent_journal_modification&rsquo;.
            </p>
          </div>
          <span
            style={{
              padding: '0.25rem 0.65rem',
              borderRadius: 'var(--radius-pill, 9999px)',
              background: 'rgba(11, 15, 23, 0.6)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6875rem',
              color: '#94A3B8',
            }}
          >
            {statement.length} Recorded Entries
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', textAlign: 'left', fontSize: '0.8125rem', fontFamily: 'var(--font-mono)', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ color: '#94A3B8', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', background: 'rgba(11, 15, 23, 0.5)', fontSize: '0.6875rem' }}>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>Seq</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>Journal ID</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>Operation</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>Side</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600, textAlign: 'right' }}>Amount</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>Timestamp</th>
                <th style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>Correlation / Transfer</th>
              </tr>
            </thead>
            <tbody style={{ color: '#CBD5E1' }}>
              {statement.map((entry) => (
                <tr
                  key={`${entry.journal_id}-${entry.line_no}`}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    transition: 'background-color 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.03)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <td style={{ padding: '0.75rem 1rem', color: '#64748B' }}>{entry.account_sequence}</td>
                  <td style={{ padding: '0.75rem 1rem', color: '#FFFFFF', fontWeight: 600 }}>{entry.journal_id.slice(0, 8)}...</td>
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <span
                      style={{
                        padding: '0.2rem 0.55rem',
                        background: 'rgba(11, 15, 23, 0.7)',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: 'var(--radius-pill, 9999px)',
                        fontSize: '0.625rem',
                        color: '#38BDF8',
                      }}
                    >
                      {entry.operation_type}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <span
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        color: entry.side === 'DEBIT' ? '#F59E0B' : '#34D399',
                      }}
                    >
                      {entry.side}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem 1rem', textAlign: 'right', fontWeight: 700, color: '#FFFFFF' }}>
                    {formatINR(entry.amount_minor)}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', color: '#94A3B8', fontSize: '0.75rem' }}>
                    {new Date(entry.created_at).toLocaleTimeString()}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#94A3B8' }}>
                    {entry.transfer_id ? (
                      <Link
                        href={`/console/transfers/${entry.transfer_id}`}
                        style={{ color: '#38BDF8', textDecoration: 'none' }}
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
                  <td colSpan={7} style={{ padding: '3rem', textAlign: 'center', color: '#64748B' }}>
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
