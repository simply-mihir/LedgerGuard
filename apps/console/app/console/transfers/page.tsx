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
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] shadow-[0_0_8px_rgba(56,189,248,0.6)]" />
            Distributed Coordination Engine
          </div>
          <h1 className="text-3xl md:text-4xl font-serif text-[#F8FAFC] font-normal tracking-tight">
            Try-Confirm-Cancel Transfers
          </h1>
          <p className="text-xs text-[#94A3B8] max-w-2xl mt-1 leading-relaxed">
            Application-level 3-phase TCC lifecycle. Source funds are reserved via temporary holds, destination accounts are prepared, a durable COMMIT decision is logged, and outbox workers asynchronously confirm or recover.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/console/experiments"
            style={{
              padding: '0.625rem 1.25rem',
              borderRadius: 'var(--radius-control, 14px)',
              background: 'rgba(29, 78, 216, 0.8)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              color: '#FFFFFF',
              fontSize: '0.75rem',
              fontFamily: 'var(--font-mono)',
              textDecoration: 'none',
              fontWeight: 600,
              boxShadow: '0 4px 16px rgba(29, 78, 216, 0.3)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              transition: 'all 0.2s ease',
            }}
          >
            <span>Inject Failure Scenario</span>
            <span>→</span>
          </Link>
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
          <span>Failed to load transfers: {error}</span>
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
            placeholder="Search by Transfer ID or Account ID..."
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
          {/* Attention toggle */}
          <button
            onClick={() => setAttentionOnly(!attentionOnly)}
            style={{
              padding: '0.35rem 0.75rem',
              fontSize: '0.6875rem',
              borderRadius: 'var(--radius-pill, 9999px)',
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              border: attentionOnly ? '1px solid rgba(245, 158, 11, 0.5)' : '1px solid rgba(255, 255, 255, 0.06)',
              backgroundColor: attentionOnly ? 'rgba(245, 158, 11, 0.2)' : 'rgba(11, 15, 23, 0.6)',
              color: attentionOnly ? '#F59E0B' : '#94A3B8',
              fontWeight: attentionOnly ? 700 : 400,
              transition: 'all 0.18s ease',
            }}
          >
            {attentionOnly ? '⚠ Attention Required Only' : 'Show All'}
          </button>

          {/* Route filter */}
          <div className="flex items-center gap-1 font-mono text-xs">
            <span className="text-[#94A3B8] text-[11px] uppercase mr-1">Route:</span>
            {(['ALL', 'L1_TO_L2', 'L2_TO_L1'] as const).map((r) => (
              <button
                key={r}
                onClick={() => setSelectedRoute(r)}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.6875rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'pointer',
                  border: selectedRoute === r ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.06)',
                  backgroundColor: selectedRoute === r ? 'rgba(29, 78, 216, 0.8)' : 'rgba(11, 15, 23, 0.6)',
                  color: selectedRoute === r ? '#FFFFFF' : '#94A3B8',
                  fontWeight: selectedRoute === r ? 600 : 400,
                  transition: 'all 0.18s ease',
                }}
              >
                {r === 'ALL' ? 'All Routes' : r === 'L1_TO_L2' ? 'L1 → L2' : 'L2 → L1'}
              </button>
            ))}
          </div>

          {/* State filter */}
          <div className="flex items-center gap-1 font-mono text-xs">
            <span className="text-[#94A3B8] text-[11px] uppercase mr-1">State:</span>
            {(['ALL', 'SETTLED', 'CANCELLED', 'COMMITTED', 'PREPARING'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setSelectedState(st)}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.6875rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'pointer',
                  border: selectedState === st ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.06)',
                  backgroundColor: selectedState === st ? 'rgba(29, 78, 216, 0.8)' : 'rgba(11, 15, 23, 0.6)',
                  color: selectedState === st ? '#FFFFFF' : '#94A3B8',
                  fontWeight: selectedState === st ? 600 : 400,
                  transition: 'all 0.18s ease',
                }}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Dense Transfers Table Container */}
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
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600 }}>Transfer ID</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600 }}>Amount</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600 }}>Route</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600 }}>Durable Decision</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600 }}>Workflow State</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600 }}>Created Timestamp</th>
                <th style={{ padding: '0.875rem 1.25rem', fontWeight: 600, textAlign: 'right' }}>TCC Lifecycle</th>
              </tr>
            </thead>
            <tbody style={{ color: '#CBD5E1' }}>
              {filteredTransfers.map((tx) => (
                <tr
                  key={tx.transfer_id}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    transition: 'background-color 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.03)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <td style={{ padding: '0.875rem 1.25rem', fontWeight: 600, color: '#F8FAFC' }}>
                    <Link
                      href={`/console/transfers/${tx.transfer_id}`}
                      style={{ color: 'inherit', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.5rem', minHeight: '24px', lineHeight: '24px' }}
                    >
                      {tx.attention_required && (
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#F59E0B', boxShadow: '0 0 6px rgba(245, 158, 11, 0.6)' }} title="Requires recovery attention" />
                      )}
                      <span>{tx.transfer_id.slice(0, 12)}...</span>
                    </Link>
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem', fontWeight: 700, color: '#FFFFFF' }}>
                    {formatINR(tx.amount_minor)}
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem', color: '#94A3B8', fontSize: '0.75rem' }}>
                    {tx.source_ledger_id} → {tx.destination_ledger_id}
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem' }}>
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
                  <td style={{ padding: '0.875rem 1.25rem' }}>
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
                  <td style={{ padding: '0.875rem 1.25rem', fontSize: '0.75rem', color: '#94A3B8' }}>
                    {new Date(tx.created_at).toLocaleTimeString()}
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem', textAlign: 'right' }}>
                    <Link
                      href={`/console/transfers/${tx.transfer_id}`}
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
                      Inspect Timeline →
                    </Link>
                  </td>
                </tr>
              ))}
              {filteredTransfers.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} style={{ padding: '3rem', textAlign: 'center', color: '#64748B' }}>
                    No transfers found matching filter criteria.
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
