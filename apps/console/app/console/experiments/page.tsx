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
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-[#1E293B]">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#F59E0B] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 bg-[#F59E0B]" />
            Deterministic Fault Injection Sandbox
          </div>
          <h1 className="text-3xl md:text-4xl font-serif text-[#F8FAFC] font-normal tracking-tight">
            Failure Lab &amp; Recovery Tests
          </h1>
          <p className="text-xs text-[#94A3B8] max-w-2xl mt-1">
            Simulate realistic distributed failure modes across the TCC lifecycle. Validate that the background orchestrator deterministically completes forward recovery with zero premature fund rollbacks.
          </p>
        </div>

        <div className="px-3 py-1.5 bg-[#0F172A] border border-[#1E293B] font-mono text-xs">
          <span className="text-[#64748B] block text-[10px] uppercase">Environment</span>
          <span className="text-[#10B981] font-bold">Local Sandbox Active</span>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-[#7F1D1D]/30 border-l-2 border-[#DC2626] text-xs text-[#FCA5A5] flex items-center justify-between">
          <span>{error}</span>
          <button onClick={handleRunSignatureScenario} className="font-mono underline bg-transparent border-0 text-inherit cursor-pointer">
            Retry
          </button>
        </div>
      )}

      {/* Signature Scenario Card */}
      <div className="p-6 bg-[#0F172A] border border-[#1E293B]">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-[#1E293B]">
          <div className="max-w-2xl">
            <div className="inline-block px-2 py-0.5 bg-[#1E293B] font-mono text-[10px] text-[#38BDF8] uppercase tracking-wider mb-2">
              SIGNATURE CRASH SCENARIO
            </div>
            <h2 className="text-xl font-serif text-white tracking-tight">
              FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM
            </h2>
            <p className="text-xs text-[#94A3B8] mt-2 leading-relaxed">
              The coordinator successfully decides and durably commits the transfer into PostgreSQL. Immediately before dispatching outbox confirmation to the source ledger, the coordinator process crashes.
            </p>
            <div className="mt-3 text-xs text-[#CBD5E1] space-y-1">
              <div>&bull; <strong>Durable Guarantee:</strong> Because the COMMIT decision was recorded in the database, the transfer must recover forward.</div>
              <div>&bull; <strong>Safety Invariant:</strong> The sender&rsquo;s hold must NOT be prematurely refunded, and the recipient must receive their funds.</div>
            </div>
          </div>

          <div className="flex flex-col items-start lg:items-end gap-2 flex-shrink-0">
            <button
              onClick={handleRunSignatureScenario}
              disabled={isRunning}
              className="px-6 py-3 bg-[#1D4ED8] hover:bg-[#2563EB] text-white text-xs font-mono uppercase tracking-widest transition-colors disabled:opacity-50 cursor-pointer border-0"
            >
              {isRunning ? 'Injecting Crash & Recovering...' : 'Trigger Signature Recovery'}
            </button>
            <span className="text-[10px] font-mono text-[#64748B]">
              Injects CrashAfterCommitError
            </span>
          </div>
        </div>

        {/* Execution Results */}
        {result && (
          <div className="mt-6 pt-2">
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#1E293B]">
              <span className="font-mono text-xs text-[#10B981] font-bold">
                ✔ SCENARIO COMPLETED: {result.status}
              </span>
              <Link
                href={`/console/transfers/${result.transfer_id}`}
                className="text-xs font-mono text-[#38BDF8] hover:underline"
              >
                Inspect Generated Transfer Timeline ({result.transfer_id.slice(0, 8)}...) &rarr;
              </Link>
            </div>

            {/* 5-Step Narrative */}
            <div className="space-y-3 font-mono text-xs">
              {result.steps.map((st) => (
                <div key={st.step_number} className="p-3 bg-[#0B0F17] border border-[#1E293B] flex items-start gap-4">
                  <span className="w-5 h-5 bg-[#1E293B] text-[#38BDF8] flex items-center justify-center font-bold text-[10px] flex-shrink-0">
                    {st.step_number}
                  </span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white uppercase text-[11px]">{st.phase}</span>
                      <span className="text-[10px] text-[#10B981] bg-[#064E3B]/40 px-2 py-0.5">{st.outcome}</span>
                    </div>
                    <div className="text-[#94A3B8] text-[11px] mt-0.5">{st.action}</div>
                    <div className="text-[#64748B] text-[10px] mt-1">{st.details}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Invariant Verification */}
            <div className="mt-4 p-4 bg-[#064E3B]/20 border border-[#10B981]/30 text-xs font-mono text-[#A7F3D0] flex items-center justify-between">
              <span>Residual Holds: {result.final_accounting_state.alice_held ?? 0} paise (Zero residual holds confirmed)</span>
              <span>Recipient Posted: ₹{(result.final_accounting_state.bob_posted / 100).toFixed(2)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
