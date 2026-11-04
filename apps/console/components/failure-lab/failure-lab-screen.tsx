import React, { useState } from 'react';
import { ExperimentResult } from '../../lib/types';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { ExperimentCard } from './experiment-card';
import { ExperimentReviewDialog } from './experiment-review-dialog';
import { ExperimentStepper } from './experiment-stepper';

interface FailureLabScreenProps {
  onRunExperiment: (scenario: string) => Promise<void>;
  isRunning: boolean;
  result: ExperimentResult | null;
  faultInjectionEnabled: boolean;
}

export function FailureLabScreen({
  onRunExperiment,
  isRunning,
  result,
  faultInjectionEnabled,
}: FailureLabScreenProps) {
  const [isReviewOpen, setIsReviewOpen] = useState(false);

  const handleConfirmRun = async () => {
    setIsReviewOpen(false);
    await onRunExperiment('SIGNATURE_RECOVERY');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Engineering Environment Callout */}
      <Card
        style={{
          padding: '1.5rem',
          background: 'linear-gradient(135deg, rgba(30, 36, 46, 0.8) 0%, rgba(17, 20, 26, 0.95) 100%)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
          <Badge variant="blue" size="md">
            CONTROLLED ENGINEERING LAB
          </Badge>
          <Badge variant={faultInjectionEnabled ? 'mint' : 'rose'} size="sm">
            {faultInjectionEnabled ? 'Fault Injection Enabled (Local / Non-Prod)' : 'Fault Controls Blocked (Production)'}
          </Badge>
        </div>

        <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.02em', marginBottom: '0.4rem' }}>
          Deterministic Fault Injection & Recovery Matrix
        </h2>

        <p style={{ fontSize: '0.8125rem', color: '#94a3b8', maxWidth: '780px', lineHeight: 1.5 }}>
          The Failure Lab intentionally injects simulated process crashes, worker delays, and split-brain scenarios against
          live PostgreSQL 17 instances to empirically prove that LedgerGuard&apos;s recovery boundary prevents premature refunds
          and guarantees zero residual holds.
        </p>

        <div
          style={{
            marginTop: '1rem',
            padding: '0.6rem 0.85rem',
            borderRadius: '8px',
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            fontSize: '0.6875rem',
            color: '#64748b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>Production Safeguard: Fault injection endpoints enforce HTTP 403 Forbidden when ENV=production.</span>
          <span className="font-mono" style={{ color: '#0df2a6' }}>Public-Safe Verification Verified</span>
        </div>
      </Card>

      {/* Signature Recovery Scenario Card */}
      <ExperimentCard
        title="Signature Scenario: Crash After COMMIT → Forward Recovery"
        scenario="SIGNATURE_RECOVERY"
        description="Alice (Ledger 1) transfers ₹300.00 to Bob (Ledger 2). Phase 1 reserves funds; the coordinator writes a durable COMMIT decision to transfer_decisions under row lock and immediately crashes before dispatching confirmation. On recovery, the background worker recovers forward to final settlement with zero premature refund."
        failurePoint="Coordinator process terminated immediately after COMMIT record written to disk."
        expectedInvariant="No rollback permitted after durable decision; zero residual holds on Ledger 1; exact single credit to Bob on Ledger 2."
        recoveryExpectation="Background recovery worker inspects unconfirmed transfer in COMMITTING state and completes forward settlement."
        onSelect={() => setIsReviewOpen(true)}
        isRunning={isRunning}
        isDisabled={!faultInjectionEnabled}
        disabledReason="Fault injection is blocked by server configuration (production mode active)."
      />

      {/* Review Dialog Modal */}
      <ExperimentReviewDialog
        isOpen={isReviewOpen}
        onClose={() => setIsReviewOpen(false)}
        onConfirm={handleConfirmRun}
        isRunning={isRunning}
      />

      {/* Returned Execution Trace Stepper */}
      {result && (
        <Card style={{ padding: '1.5rem' }}>
          <ExperimentStepper result={result} />
        </Card>
      )}
    </div>
  );
}
