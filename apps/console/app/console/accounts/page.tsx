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
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] shadow-[0_0_8px_rgba(56,189,248,0.6)]" />
            Partitioned Balance Store
          </div>
          <h1 className="text-3xl md:text-4xl font-serif text-[#F8FAFC] font-normal tracking-tight">
            Customer Ledgers &amp; Accounts
          </h1>
          <p className="text-xs text-[#94A3B8] max-w-2xl mt-1 leading-relaxed">
            Authoritative accounts partitioned across Ledger 1 and Ledger 2 PostgreSQL instances. Each account balances posted state, holds for in-flight TCC transfers, and immutable double-entry lines.
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          <div
            style={{
              padding: '0.875rem 1.25rem',
              borderRadius: 'var(--radius-secondary, 20px)',
              background: 'rgba(15, 23, 42, 0.65)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              boxShadow: '0 8px 24px -6px rgba(0, 0, 0, 0.4)',
            }}
          >
            <span className="text-[#94A3B8] block text-[10px] uppercase font-semibold tracking-wider">Aggregated Posted Assets</span>
            <span className="text-white font-bold text-base mt-0.5 block">{formatINR(totalPosted)}</span>
          </div>
          <div
            style={{
              padding: '0.875rem 1.25rem',
              borderRadius: 'var(--radius-secondary, 20px)',
              background: 'rgba(15, 23, 42, 0.65)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid rgba(245, 158, 11, 0.2)',
              boxShadow: '0 8px 24px -6px rgba(0, 0, 0, 0.4)',
            }}
          >
            <span className="text-[#94A3B8] block text-[10px] uppercase font-semibold tracking-wider">Active TCC Holds</span>
            <span className="text-[#F59E0B] font-bold text-base mt-0.5 block">{formatINR(totalHeld)}</span>
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
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>Failed to load accounts: {error}</span>
          <button onClick={loadData} className="font-mono underline bg-transparent border-0 text-inherit cursor-pointer">
            Retry
          </button>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div
        style={{
          padding: '1rem 1.25rem',
          borderRadius: 'var(--radius-secondary, 20px)',
          background: 'rgba(15, 23, 42, 0.7)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 12px 30px -10px rgba(0, 0, 0, 0.4)',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
        }}
        className="md:flex-row md:items-center md:justify-between"
      >
        <div className="flex-1 max-w-md">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by Account ID or Customer UUID..."
            style={{
              width: '100%',
              background: 'rgba(11, 15, 23, 0.8)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 'var(--radius-control, 14px)',
              padding: '0.625rem 1rem',
              fontSize: '0.75rem',
              fontFamily: 'var(--font-mono)',
              color: '#F8FAFC',
              outline: 'none',
              transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
            }}
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Ledger Selector */}
          <div className="flex items-center gap-1 font-mono text-xs">
            <span className="text-[#94A3B8] text-[11px] uppercase mr-1">Partition:</span>
            {(['ALL', 'ledger-1', 'ledger-2'] as const).map((lid) => (
              <button
                key={lid}
                onClick={() => setSelectedLedger(lid)}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.6875rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'pointer',
                  border: selectedLedger === lid ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.06)',
                  backgroundColor: selectedLedger === lid ? 'rgba(29, 78, 216, 0.8)' : 'rgba(11, 15, 23, 0.6)',
                  color: selectedLedger === lid ? '#FFFFFF' : '#94A3B8',
                  fontWeight: selectedLedger === lid ? 600 : 400,
                  transition: 'all 0.18s ease',
                }}
              >
                {lid === 'ALL' ? 'All Ledgers' : lid}
              </button>
            ))}
          </div>

          {/* Status Selector */}
          <div className="flex items-center gap-1 font-mono text-xs">
            <span className="text-[#94A3B8] text-[11px] uppercase mr-1">Status:</span>
            {(['ALL', 'ACTIVE', 'FROZEN', 'CLOSED'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setSelectedStatus(st)}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.6875rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'pointer',
                  border: selectedStatus === st ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.06)',
                  backgroundColor: selectedStatus === st ? 'rgba(29, 78, 216, 0.8)' : 'rgba(11, 15, 23, 0.6)',
                  color: selectedStatus === st ? '#FFFFFF' : '#94A3B8',
                  fontWeight: selectedStatus === st ? 600 : 400,
                  transition: 'all 0.18s ease',
                }}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Dense Accounts Table Container */}
      <div
        style={{
          borderRadius: 'var(--radius-primary, 28px)',
          background: 'rgba(15, 23, 42, 0.7)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', textAlign: 'left', fontSize: '0.8125rem', fontFamily: 'var(--font-mono)', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ color: '#94A3B8', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', background: 'rgba(11, 15, 23, 0.5)', fontSize: '0.6875rem' }}>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600 }}>Account ID</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600 }}>Customer Ref</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600 }}>Ledger Partition</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600, textAlign: 'right' }}>Posted Balance</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600, textAlign: 'right' }}>Held in TCC</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600, textAlign: 'right' }}>Available Balance</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600, textAlign: 'center' }}>Status</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600, textAlign: 'right' }}>Statement</th>
              </tr>
            </thead>
            <tbody style={{ color: '#CBD5E1' }}>
              {filteredAccounts.map((acct) => (
                <tr
                  key={acct.account_id}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    transition: 'background-color 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.03)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <td style={{ padding: '0.875rem 1.25rem', fontWeight: 600, color: '#F8FAFC' }}>
                    <Link
                      href={`/console/accounts/${acct.account_id}`}
                      style={{ color: 'inherit', textDecoration: 'none', display: 'inline-block', minHeight: '24px', lineHeight: '24px' }}
                    >
                      {acct.account_id}
                    </Link>
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem', color: '#94A3B8', fontSize: '0.75rem' }}>
                    {acct.customer_id.slice(0, 8)}...
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem' }}>
                    <span
                      style={{
                        padding: '0.2rem 0.6rem',
                        background: 'rgba(11, 15, 23, 0.8)',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: 'var(--radius-pill, 9999px)',
                        fontSize: '0.6875rem',
                        color: '#38BDF8',
                        fontWeight: 600,
                      }}
                    >
                      {acct.ledger_id}
                    </span>
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem', textAlign: 'right', fontWeight: 700, color: '#FFFFFF' }}>
                    {formatINR(acct.posted_balance_minor)}
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem', textAlign: 'right' }}>
                    <span style={{ color: acct.held_amount_minor > 0 ? '#F59E0B' : '#64748B', fontWeight: acct.held_amount_minor > 0 ? 700 : 400 }}>
                      {formatINR(acct.held_amount_minor)}
                    </span>
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem', textAlign: 'right', fontWeight: 700, color: '#34D399' }}>
                    {formatINR(acct.available_balance_minor)}
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem', textAlign: 'center' }}>
                    <span
                      style={{
                        padding: '0.25rem 0.625rem',
                        fontSize: '0.625rem',
                        borderRadius: 'var(--radius-pill, 9999px)',
                        fontWeight: 700,
                        backgroundColor:
                          acct.status === 'ACTIVE'
                            ? 'rgba(5, 150, 105, 0.15)'
                            : acct.status === 'FROZEN'
                            ? 'rgba(245, 158, 11, 0.15)'
                            : 'rgba(220, 38, 38, 0.15)',
                        color:
                          acct.status === 'ACTIVE'
                            ? '#34D399'
                            : acct.status === 'FROZEN'
                            ? '#F59E0B'
                            : '#EF4444',
                      }}
                    >
                      {acct.status}
                    </span>
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem', textAlign: 'right' }}>
                    <Link
                      href={`/console/accounts/${acct.account_id}`}
                      style={{
                        color: '#38BDF8',
                        textDecoration: 'none',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        display: 'inline-block',
                        minHeight: '24px',
                        lineHeight: '24px',
                      }}
                    >
                      Statement →
                    </Link>
                  </td>
                </tr>
              ))}
              {filteredAccounts.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} style={{ padding: '3rem', textAlign: 'center', color: '#64748B' }}>
                    No accounts match the specified criteria or query.
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
