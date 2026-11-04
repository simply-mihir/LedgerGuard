import React from 'react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';

interface ExperimentReviewDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isRunning: boolean;
}

export function ExperimentReviewDialog({
  isOpen,
  onClose,
  onConfirm,
  isRunning,
}: ExperimentReviewDialogProps) {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 250,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
      }}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(5, 7, 9, 0.85)',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          animation: 'fade-in 0.2s ease',
        }}
      />

      {/* Modal Dialog */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: '540px',
          background: '#12151b',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: '16px',
          boxShadow: '0 16px 48px rgba(0, 0, 0, 0.75)',
          padding: '1.75rem',
          zIndex: 251,
          animation: 'fade-in 0.22s ease-out',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' }}>
          <Badge variant="amber" size="md">
            CONTROLLED FAILURE INJECTION
          </Badge>
          <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Pre-Flight Review</span>
        </div>

        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.5rem' }}>
          Review Scenario: Crash After COMMIT
        </h3>

        <p style={{ fontSize: '0.8125rem', color: '#94a3b8', lineHeight: 1.5, marginBottom: '1.25rem' }}>
          This deterministic test exercises LedgerGuard&apos;s recovery boundary by killing the coordinator process immediately
          after recording the durable `COMMIT` decision to `transfer_decisions`, before Phase 2 dispatch.
        </p>

        {/* Verification Expectations Checklist */}
        <div
          style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '10px',
            padding: '1rem',
            marginBottom: '1.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.65rem',
            fontSize: '0.8125rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
            <span style={{ color: '#0df2a6', fontWeight: 700 }}>✓</span>
            <div>
              <strong style={{ color: '#f8fafc' }}>Forward Recovery Guarantee:</strong>
              <div style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                Transfer must recover forward to full settlement; automatic refunds or rollbacks are strictly forbidden.
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
            <span style={{ color: '#0df2a6', fontWeight: 700 }}>✓</span>
            <div>
              <strong style={{ color: '#f8fafc' }}>Zero Residual Holds:</strong>
              <div style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                Alice&apos;s reservation hold on Ledger 1 must be cleanly finalized with 0 paise remaining held.
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
            <span style={{ color: '#0df2a6', fontWeight: 700 }}>✓</span>
            <div>
              <strong style={{ color: '#f8fafc' }}>Single Credit Invariant:</strong>
              <div style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                Bob on Ledger 2 must receive exactly one ₹300.00 credit with zero duplicate journal receipts.
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <Button variant="secondary" size="md" onClick={onClose} disabled={isRunning}>
            Cancel
          </Button>
          <Button variant="primary" size="md" onClick={onConfirm} isLoading={isRunning}>
            {isRunning ? 'Injecting Fault...' : 'Confirm & Execute'}
          </Button>
        </div>
      </div>
    </div>
  );
}
