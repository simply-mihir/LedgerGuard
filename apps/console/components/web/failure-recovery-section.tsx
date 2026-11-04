import React from 'react';

export function FailureRecoverySection() {
  return (
    <section
      id="failure-recovery"
      style={{
        padding: '5rem 1.5rem',
        maxWidth: '1280px',
        margin: '0 auto',
      }}
    >
      <div style={{ maxWidth: '780px', marginBottom: '3.5rem' }}>
        <div
          style={{
            fontSize: '0.75rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            color: 'var(--accent-cobalt)',
            marginBottom: '0.75rem',
          }}
        >
          Signature Failure Scenario
        </div>
        <h2
          style={{
            fontFamily: 'var(--font-serif)',
            fontSize: 'clamp(2rem, 3.5vw, 2.75rem)',
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: '-0.025em',
            color: 'var(--text-ink)',
            marginBottom: '1rem',
          }}
        >
          Crash after COMMIT: Forward recovery without premature refund.
        </h2>
        <p
          style={{
            fontSize: '1.0625rem',
            color: 'var(--text-ink-secondary)',
            lineHeight: 1.65,
          }}
        >
          In distributed finance, the most dangerous failure occurs when the coordinator commits a transaction
          and crashes before delivering confirmations. In a naive system, an unprincipled timeout might refund the sender,
          causing irreversible duplicate credit. LedgerGuard proves deterministic forward resolution.
        </p>
      </div>

      {/* Signature Walkthrough Layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '2rem',
          alignItems: 'stretch',
        }}
      >
        {/* Left Column: The Protocol Sequence */}
        <div
          style={{
            backgroundColor: 'var(--bg-paper)',
            border: '1px solid var(--border-stone)',
            borderRadius: 'var(--radius-sm)',
            padding: '2rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="font-mono" style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-ink)' }}>
              FAILPOINT: FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM
            </span>
            <span
              style={{
                fontSize: '0.6875rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                padding: '0.2rem 0.5rem',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: 'rgba(220, 38, 38, 0.08)',
                color: 'var(--status-critical)',
                border: '1px solid var(--status-critical-border)',
              }}
            >
              Injected Crash
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Step 1 */}
            <div style={{ display: 'flex', gap: '1rem' }}>
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--bg-stone-subtle)',
                  border: '1px solid var(--border-stone-strong)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                1
              </div>
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-ink)', marginBottom: '0.2rem' }}>
                  Try Phase Succeeded
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
                  Alice reserves ₹400.00 on Ledger 1. Bob validates account readiness on Ledger 2.
                </div>
              </div>
            </div>

            {/* Step 2 */}
            <div style={{ display: 'flex', gap: '1rem' }}>
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--bg-stone-subtle)',
                  border: '1px solid var(--border-stone-strong)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                2
              </div>
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-ink)', marginBottom: '0.2rem' }}>
                  Atomic COMMIT Decision Persisted
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
                  Coordinator logs <code className="font-mono">COMMIT</code> into <code className="font-mono">transfer_decisions</code> under row lock.
                </div>
              </div>
            </div>

            {/* Step 3 - Crash */}
            <div style={{ display: 'flex', gap: '1rem' }}>
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(220, 38, 38, 0.15)',
                  border: '1px solid var(--status-critical)',
                  color: 'var(--status-critical)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                ⚡
              </div>
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--status-critical)', marginBottom: '0.2rem' }}>
                  Coordinator Hard Crash
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
                  Process terminates before dispatching confirmation messages to Ledger 1 or Ledger 2.
                </div>
              </div>
            </div>

            {/* Step 4 - Recovery */}
            <div style={{ display: 'flex', gap: '1rem' }}>
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(5, 150, 105, 0.15)',
                  border: '1px solid var(--status-success)',
                  color: 'var(--status-success)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                ✓
              </div>
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--status-success)', marginBottom: '0.2rem' }}>
                  Autonomous Worker Forward Recovery
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
                  Worker inspects durable decision: discovers <code className="font-mono">COMMIT</code>, executes forward resolution, releases hold, and credits Bob. Zero funds lost.
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Invariant Audit Inspection */}
        <div
          className="dark-operational-workspace"
          style={{
            padding: '2rem',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <span style={{ fontSize: '0.6875rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-operational-muted)' }}>
                Crash Inspection Evidence
              </span>
              <span
                className="font-mono"
                style={{
                  fontSize: '0.6875rem',
                  backgroundColor: 'rgba(5, 150, 105, 0.15)',
                  color: 'var(--status-success-dark)',
                  padding: '0.25rem 0.5rem',
                  borderRadius: 'var(--radius-xs)',
                  border: '1px solid var(--status-success-dark)',
                }}
              >
                PASS: 100% FORWARD RECOVERY
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div
                className="dark-operational-panel"
                style={{ padding: '1rem', borderLeft: '3px solid var(--status-success-dark)' }}
              >
                <div style={{ fontSize: '0.75rem', color: 'var(--text-operational-muted)', marginBottom: '0.25rem' }}>
                  Source Balance (Alice on Ledger 1)
                </div>
                <div className="font-mono" style={{ fontSize: '1rem', fontWeight: 700, color: '#FFFFFF' }}>
                  ₹600.00 <span style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--text-operational-secondary)' }}>(Hold Released • 0 Residual Leak)</span>
                </div>
              </div>

              <div
                className="dark-operational-panel"
                style={{ padding: '1rem', borderLeft: '3px solid var(--status-success-dark)' }}
              >
                <div style={{ fontSize: '0.75rem', color: 'var(--text-operational-muted)', marginBottom: '0.25rem' }}>
                  Destination Balance (Bob on Ledger 2)
                </div>
                <div className="font-mono" style={{ fontSize: '1rem', fontWeight: 700, color: '#FFFFFF' }}>
                  ₹400.00 <span style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--text-operational-secondary)' }}>(Exact Single Credit • 0 Duplicate)</span>
                </div>
              </div>

              <div
                className="dark-operational-panel"
                style={{ padding: '1rem', borderLeft: '3px solid var(--accent-cobalt-light)' }}
              >
                <div style={{ fontSize: '0.75rem', color: 'var(--text-operational-muted)', marginBottom: '0.25rem' }}>
                  Inter-Ledger Net Clearing Delta
                </div>
                <div className="font-mono" style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--accent-cobalt-light)' }}>
                  Σ ΔL = -₹400.00 + ₹400.00 = ₹0.00
                </div>
              </div>
            </div>
          </div>

          <div
            style={{
              marginTop: '2rem',
              paddingTop: '1rem',
              borderTop: '1px solid var(--border-operational)',
              fontSize: '0.75rem',
              color: 'var(--text-operational-muted)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>Reproduced via <code className="font-mono">./scripts/demo_signature_recovery.sh</code></span>
            <span style={{ color: 'var(--status-success-dark)', fontWeight: 600 }}>8/8 Checks Passed</span>
          </div>
        </div>
      </div>
    </section>
  );
}
