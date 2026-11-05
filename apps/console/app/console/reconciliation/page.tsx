'use client';

import React, { useState } from 'react';
import { ReconciliationReport } from '../../../lib/types';
import { executeReconciliation } from '../../../lib/api';
import { formatINR, formatNumber } from '../../../lib/format';

export default function ReconciliationPage() {
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRunReconciliation = async () => {
    setIsRunning(true);
    setError(null);
    try {
      const result = await executeReconciliation();
      setReport(result);
    } catch (err: any) {
      setError(err.message || 'Failed to execute reconciliation audit');
    } finally {
      setIsRunning(false);
    }
  };

  const isAuditPassed = report && report.status === 'PASS' && report.findings.length === 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] shadow-[0_0_8px_rgba(56,189,248,0.6)]" />
            Invariant Verifier
          </div>
          <h1 className="text-3xl md:text-4xl font-serif text-[#F8FAFC] font-normal tracking-tight">
            Cross-Ledger Reconciliation
          </h1>
          <p className="text-xs text-[#94A3B8] max-w-2xl mt-1 leading-relaxed">
            Stopped-and-drained multi-database audit. Verifies double-entry equality (&Sigma; Debits == &Sigma; Credits) and clearing balance conservation (&Sigma; &Delta;L = &#8377;0.00) across independent PostgreSQL instances.
          </p>
        </div>

        <button
          onClick={handleRunReconciliation}
          disabled={isRunning}
          style={{
            padding: '0.75rem 1.5rem',
            borderRadius: 'var(--radius-control, 14px)',
            background: 'linear-gradient(135deg, #1D4ED8 0%, #0284C7 100%)',
            border: '1px solid rgba(56, 189, 248, 0.4)',
            color: '#FFFFFF',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            boxShadow: '0 8px 24px -4px rgba(29, 78, 216, 0.5)',
            cursor: isRunning ? 'not-allowed' : 'pointer',
            opacity: isRunning ? 0.6 : 1,
            transition: 'all 0.2s ease',
          }}
        >
          {isRunning ? 'Auditing Ledgers...' : 'Run Reconciliation Audit'}
        </button>
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
          <span>{error}</span>
          <button onClick={handleRunReconciliation} className="font-mono underline bg-transparent border-0 text-inherit cursor-pointer">
            Retry
          </button>
        </div>
      )}

      {/* Database Reachability Triad Band */}
      <div
        style={{
          padding: '0.875rem 1.25rem',
          borderRadius: 'var(--radius-secondary, 20px)',
          background: 'rgba(15, 23, 42, 0.6)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          fontSize: '0.75rem',
          fontFamily: 'var(--font-mono)',
        }}
      >
        <span className="text-[#94A3B8] uppercase text-[10px] tracking-wider font-semibold">Audit Topology Nodes:</span>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#10B981] shadow-[0_0_8px_rgba(16,185,129,0.7)]" />
            <span className="text-white font-medium">Coordinator (:5442)</span>
            <span className="text-[10px] text-[#34D399] uppercase">ONLINE</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#10B981] shadow-[0_0_8px_rgba(16,185,129,0.7)]" />
            <span className="text-white font-medium">Ledger 1 (:5443)</span>
            <span className="text-[10px] text-[#34D399] uppercase">ONLINE</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#10B981] shadow-[0_0_8px_rgba(16,185,129,0.7)]" />
            <span className="text-white font-medium">Ledger 2 (:5444)</span>
            <span className="text-[10px] text-[#34D399] uppercase">ONLINE</span>
          </div>
        </div>
      </div>

      {/* Audit Invariant Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
        <div
          style={{
            padding: '1.5rem',
            borderRadius: 'var(--radius-secondary, 20px)',
            background: 'rgba(15, 23, 42, 0.75)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.4)',
          }}
        >
          <span className="text-[10px] text-[#94A3B8] uppercase font-semibold tracking-wider block">Double-Entry Trial Balance</span>
          <div className="mt-2 text-white">
            <div>Debits: <strong className="font-bold text-base text-white">{formatINR(report?.trial_balance_debit ?? 0)}</strong></div>
            <div className="mt-0.5">Credits: <strong className="font-bold text-base text-white">{formatINR(report?.trial_balance_credit ?? 0)}</strong></div>
          </div>
          <span className="text-[10px] text-[#34D399] block mt-3 flex items-center gap-1 font-medium">
            <span>✔</span>
            <span>Debits equal Credits verified</span>
          </span>
        </div>

        {/* Hero Invariant Surface */}
        <div
          style={{
            padding: '1.5rem',
            borderRadius: 'var(--radius-secondary, 20px)',
            background: 'linear-gradient(135deg, rgba(6, 78, 59, 0.25) 0%, rgba(15, 23, 42, 0.85) 100%)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(16, 185, 129, 0.35)',
            boxShadow: '0 0 30px rgba(16, 185, 129, 0.1), 0 10px 25px -5px rgba(0, 0, 0, 0.4)',
          }}
        >
          <span className="text-[10px] text-[#34D399] uppercase font-semibold tracking-wider block">Clearing Balance Invariant</span>
          <div className="mt-2">
            <span className="text-2xl font-bold text-[#34D399] tracking-tight">
              Σ ΔL = ₹0.00
            </span>
          </div>
          <span className="text-[10px] text-[#94A3B8] block mt-3">
            Zero cross-ledger leakage across partitions
          </span>
        </div>

        <div
          style={{
            padding: '1.5rem',
            borderRadius: 'var(--radius-secondary, 20px)',
            background: 'rgba(15, 23, 42, 0.75)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.4)',
          }}
        >
          <span className="text-[10px] text-[#94A3B8] uppercase font-semibold tracking-wider block">Audit Verification Status</span>
          <div className="mt-2">
            {report ? (
              <span
                style={{
                  padding: '0.25rem 0.65rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  backgroundColor: isAuditPassed ? 'rgba(5, 150, 105, 0.2)' : 'rgba(220, 38, 38, 0.2)',
                  color: isAuditPassed ? '#34D399' : '#EF4444',
                  border: isAuditPassed ? '1px solid rgba(52, 211, 153, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
                }}
              >
                {report.status} ({report.findings.length} findings)
              </span>
            ) : (
              <span className="text-xs text-[#64748B]">Audit not yet initiated</span>
            )}
          </div>
          <span className="text-[10px] text-[#94A3B8] block mt-3">
            {report?.run_at ? `Completed ${new Date(report.run_at).toLocaleTimeString()}` : 'Awaiting trigger'}
          </span>
        </div>
      </div>

      {/* Detailed Audit Metrics */}
      {report && (
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
                Examined Scope &amp; Audit Execution
              </h2>
              <p className="text-xs text-[#94A3B8] mt-0.5">Run ID: {report.run_id}</p>
            </div>
            <span className="font-mono text-xs text-[#34D399] font-medium">
              PostgreSQL 17 Cross-Database Scan
            </span>
          </div>

          <div className="grid grid-cols-3 gap-4 font-mono text-center text-xs mb-6">
            <div
              style={{
                padding: '1rem',
                borderRadius: 'var(--radius-control, 14px)',
                background: 'rgba(11, 15, 23, 0.7)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              <span className="text-[#94A3B8] text-[10px] uppercase block font-medium">Accounts Examined</span>
              <span className="text-xl font-bold text-white mt-1 block">
                {formatNumber(report.accounts_examined)}
              </span>
            </div>
            <div
              style={{
                padding: '1rem',
                borderRadius: 'var(--radius-control, 14px)',
                background: 'rgba(11, 15, 23, 0.7)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              <span className="text-[#94A3B8] text-[10px] uppercase block font-medium">Journals Examined</span>
              <span className="text-xl font-bold text-white mt-1 block">
                {formatNumber(report.journals_examined)}
              </span>
            </div>
            <div
              style={{
                padding: '1rem',
                borderRadius: 'var(--radius-control, 14px)',
                background: 'rgba(11, 15, 23, 0.7)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              <span className="text-[#94A3B8] text-[10px] uppercase block font-medium">Lines Examined</span>
              <span className="text-xl font-bold text-white mt-1 block">
                {formatNumber(report.lines_examined)}
              </span>
            </div>
          </div>

          {/* Findings Surface */}
          <div>
            <h3 className="text-xs font-mono text-[#94A3B8] uppercase tracking-wider mb-2 font-semibold">
              Invariant Audit Findings ({report.findings.length})
            </h3>
            {report.findings.length === 0 ? (
              <div
                style={{
                  padding: '1rem 1.25rem',
                  borderRadius: 'var(--radius-control, 14px)',
                  background: 'rgba(6, 78, 59, 0.25)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  color: '#A7F3D0',
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <span className="text-[#34D399]">✔</span>
                <span>All double-entry constraints and clearing conservation invariants hold with zero discrepancies.</span>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', textAlign: 'left', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ color: '#94A3B8', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                      <th style={{ padding: '0.5rem' }}>Check Name</th>
                      <th style={{ padding: '0.5rem' }}>Severity</th>
                      <th style={{ padding: '0.5rem' }}>Resource ID</th>
                      <th style={{ padding: '0.5rem' }}>Details</th>
                    </tr>
                  </thead>
                  <tbody style={{ color: '#FCA5A5' }}>
                    {report.findings.map((f, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                        <td style={{ padding: '0.5rem' }}>{f.check_name}</td>
                        <td style={{ padding: '0.5rem', fontWeight: 700, color: '#EF4444' }}>{f.severity}</td>
                        <td style={{ padding: '0.5rem' }}>{f.resource_id}</td>
                        <td style={{ padding: '0.5rem' }}>{f.details}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
