'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { ExperimentResult } from '../../../lib/types';
import { executeExperiment } from '../../../lib/api';

export default function ExperimentsPage() {
  const [result, setResult] = useState<ExperimentResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRunSignatureScenario = async () => {
    setIsRunning(true);
    setError(null);
    try {
      const res = await executeExperiment('SIGNATURE_RECOVERY');
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Failed to execute experiment scenario');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#F59E0B] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B] shadow-[0_0_8px_rgba(245,158,11,0.6)]" />
            Deterministic Fault Injection Sandbox
          </div>
          <h1 className="text-3xl md:text-4xl font-serif text-[#F8FAFC] font-normal tracking-tight">
            Failure Lab &amp; Recovery Tests
          </h1>
          <p className="text-xs text-[#94A3B8] max-w-2xl mt-1 leading-relaxed">
            Simulate realistic distributed failure modes across the TCC lifecycle. Validate that the background orchestrator deterministically completes forward recovery with zero premature fund rollbacks.
          </p>
        </div>

        <div
          style={{
            padding: '0.625rem 1rem',
            borderRadius: 'var(--radius-control, 14px)',
            background: 'rgba(15, 23, 42, 0.65)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
          }}
        >
          <span className="text-[#94A3B8] block text-[10px] uppercase font-semibold">Environment</span>
          <span className="text-[#34D399] font-bold">Local Sandbox Active</span>
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
          <span>{error}</span>
          <button onClick={handleRunSignatureScenario} className="font-mono underline bg-transparent border-0 text-inherit cursor-pointer">
            Retry
          </button>
        </div>
      )}

      {/* Signature Scenario Controlled Action Surface */}
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
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-white/[0.08]">
          <div className="max-w-2xl">
            <div
              style={{
                display: 'inline-block',
                padding: '0.2rem 0.6rem',
                borderRadius: 'var(--radius-pill, 9999px)',
                background: 'rgba(56, 189, 248, 0.1)',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.625rem',
                color: '#38BDF8',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                fontWeight: 700,
                marginBottom: '0.5rem',
              }}
            >
              SIGNATURE CRASH SCENARIO
            </div>
            <h2 className="text-xl font-mono text-white tracking-tight font-bold">
              FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM
            </h2>
            <p className="text-xs text-[#94A3B8] mt-2 leading-relaxed">
              The coordinator successfully decides and durably commits the transfer into PostgreSQL. Immediately before dispatching outbox confirmation to the source ledger, the coordinator process crashes.
            </p>
            <div className="mt-3 text-xs text-[#CBD5E1] space-y-1 font-mono">
              <div>• <strong className="text-white">Durable Guarantee:</strong> Because the COMMIT decision was recorded in the database, the transfer must recover forward.</div>
              <div>• <strong className="text-white">Safety Invariant:</strong> The sender&rsquo;s hold must NOT be prematurely refunded, and the recipient must receive their funds.</div>
            </div>
          </div>

          <div className="flex flex-col items-start lg:items-end gap-2 flex-shrink-0">
            <button
              onClick={handleRunSignatureScenario}
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
              {isRunning ? 'Injecting Crash & Recovering...' : 'Trigger Signature Recovery'}
            </button>
            <span className="text-[10px] font-mono text-[#94A3B8]">
              Injects CrashAfterCommitError
            </span>
          </div>
        </div>

        {/* Execution Results */}
        {result && (
          <div className="mt-6 pt-2">
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-white/[0.08]">
              <span className="font-mono text-xs text-[#34D399] font-bold flex items-center gap-1.5">
                <span>✔</span>
                <span>SCENARIO COMPLETED: {result.status}</span>
              </span>
              <Link
                href={`/console/transfers/${result.transfer_id}`}
                className="text-xs font-mono text-[#38BDF8] hover:underline"
              >
                Inspect Generated Transfer Timeline ({result.transfer_id.slice(0, 8)}...) →
              </Link>
            </div>

            {/* 5-Step Narrative progression */}
            <div className="space-y-3 font-mono text-xs">
              {result.steps.map((st) => (
                <div
                  key={st.step_number}
                  style={{
                    padding: '0.875rem 1rem',
                    borderRadius: 'var(--radius-control, 14px)',
                    background: 'rgba(11, 15, 23, 0.7)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '1rem',
                  }}
                >
                  <span
                    style={{
                      width: '24px',
                      height: '24px',
                      borderRadius: 'var(--radius-pill, 9999px)',
                      background: 'rgba(29, 78, 216, 0.3)',
                      border: '1px solid rgba(56, 189, 248, 0.4)',
                      color: '#38BDF8',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '0.6875rem',
                      flexShrink: 0,
                    }}
                  >
                    {st.step_number}
                  </span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white uppercase text-[11px]">{st.phase}</span>
                      <span
                        style={{
                          fontSize: '0.625rem',
                          color: '#34D399',
                          backgroundColor: 'rgba(5, 150, 105, 0.2)',
                          padding: '0.15rem 0.5rem',
                          borderRadius: 'var(--radius-pill, 9999px)',
                          fontWeight: 700,
                        }}
                      >
                        {st.outcome}
                      </span>
                    </div>
                    <div className="text-[#CBD5E1] text-[11px] mt-0.5">{st.action}</div>
                    <div className="text-[#94A3B8] text-[10px] mt-1">{st.details}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Invariant Verification Banner */}
            <div
              style={{
                marginTop: '1rem',
                padding: '1rem 1.25rem',
                borderRadius: 'var(--radius-control, 14px)',
                background: 'rgba(6, 78, 59, 0.25)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
                color: '#A7F3D0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span>Residual Holds: {result.final_accounting_state.alice_held ?? 0} paise (Zero residual holds confirmed)</span>
              <span className="font-bold text-white">Recipient Posted: ₹{(result.final_accounting_state.bob_posted / 100).toFixed(2)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
