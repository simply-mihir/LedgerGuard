import React from 'react';

export function FailureRecoverySection() {
  return (
    <section
      id="failure-recovery"
      style={{
        padding: '6rem 1.5rem',
        maxWidth: '1240px',
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
            background: 'rgba(29, 78, 216, 0.08)',
            padding: '0.35rem 0.85rem',
            borderRadius: 'var(--radius-pill, 9999px)',
            border: '1px solid rgba(29, 78, 216, 0.18)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            marginBottom: '1.25rem',
          }}
        >
          <span>●</span>
          <span>Signature Failure Scenario</span>
        </div>
        <h2
          style={{
            fontFamily: 'var(--font-serif)',
            fontSize: 'clamp(2rem, 3.5vw, 3rem)',
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
            fontSize: '1.125rem',
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
          className="glass-supporting"
          style={{
            borderRadius: 'var(--radius-primary, 28px)',
            padding: '2.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.75rem',
            background: 'rgba(255, 255, 255, 0.80)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.75)',
            boxShadow: '0 20px 48px -12px rgba(15, 23, 42, 0.06), 0 0 0 1px rgba(255, 255, 255, 0.8) inset',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="font-mono" style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-ink)' }}>
              FAILPOINT: FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM
            </span>
            <span
              style={{
                fontSize: '0.6875rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                padding: '0.25rem 0.65rem',
                borderRadius: 'var(--radius-pill, 9999px)',
                backgroundColor: 'rgba(220, 38, 38, 0.12)',
                color: 'var(--status-critical)',
                border: '1px solid rgba(220, 38, 38, 0.30)',
              }}
            >
              Injected Crash
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Step 1 */}
            <div style={{ display: 'flex', gap: '1.25rem' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  backgroundColor: 'rgba(29, 78, 216, 0.08)',
                  border: '1px solid rgba(29, 78, 216, 0.25)',
                  color: 'var(--accent-cobalt)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.8125rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                1
              </div>
              <div>
                <div style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--text-ink)', marginBottom: '0.25rem' }}>
                  Try Phase Succeeded
                </div>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.55 }}>
                  Alice reserves ₹400.00 on Ledger 1. Bob validates account readiness on Ledger 2.
                </div>
              </div>
            </div>

            {/* Step 2 */}
            <div style={{ display: 'flex', gap: '1.25rem' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  backgroundColor: 'rgba(29, 78, 216, 0.08)',
                  border: '1px solid rgba(29, 78, 216, 0.25)',
                  color: 'var(--accent-cobalt)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.8125rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                2
              </div>
              <div>
                <div style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--text-ink)', marginBottom: '0.25rem' }}>
                  Atomic COMMIT Decision Persisted
                </div>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.55 }}>
                  Coordinator logs <code className="font-mono">COMMIT</code> into <code className="font-mono">transfer_decisions</code> under row lock.
                </div>
              </div>
            </div>

            {/* Step 3 - Crash */}
            <div style={{ display: 'flex', gap: '1.25rem' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  backgroundColor: 'rgba(220, 38, 38, 0.15)',
                  border: '1px solid rgba(220, 38, 38, 0.40)',
                  color: 'var(--status-critical)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.875rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                ⚡
              </div>
              <div>
                <div style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--status-critical)', marginBottom: '0.25rem' }}>
                  Coordinator Hard Crash Outage
                </div>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.55 }}>
                  Process terminates before dispatching confirmation messages to Ledger 1 or Ledger 2.
                </div>
              </div>
            </div>

            {/* Step 4 - Recovery */}
            <div style={{ display: 'flex', gap: '1.25rem' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  backgroundColor: 'rgba(5, 150, 105, 0.15)',
                  border: '1px solid rgba(5, 150, 105, 0.40)',
                  color: 'var(--status-success)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.875rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                ✓
              </div>
              <div>
                <div style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--status-success)', marginBottom: '0.25rem' }}>
                  Autonomous Worker Forward Recovery
                </div>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.55 }}>
                  Worker inspects durable decision: discovers <code className="font-mono">COMMIT</code>, executes forward resolution, releases hold, and credits Bob. Zero funds lost.
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Invariant Audit Inspection */}
        <div
          className="glass-hero-dark"
          style={{
            borderRadius: 'var(--radius-primary, 28px)',
            padding: '2.5rem',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            background: 'rgba(14, 20, 34, 0.78)',
            backdropFilter: 'blur(28px)',
            WebkitBackdropFilter: 'blur(28px)',
            border: '1px solid rgba(56, 189, 248, 0.20)',
            boxShadow: '0 24px 60px -12px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255, 255, 255, 0.12) inset',
          }}
        >
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.75rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94A3B8' }}>
                Crash Inspection Evidence
              </span>
              <span
                className="font-mono"
                style={{
                  fontSize: '0.6875rem',
                  backgroundColor: 'rgba(16, 185, 129, 0.15)',
                  color: '#34D399',
                  padding: '0.25rem 0.65rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  border: '1px solid rgba(16, 185, 129, 0.35)',
                  fontWeight: 700,
                }}
              >
                PASS: 100% FORWARD RECOVERY
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div
                style={{
                  background: 'rgba(20, 28, 48, 0.75)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 'var(--radius-secondary, 20px)',
                  padding: '1.25rem 1.5rem',
                  borderLeft: '4px solid #10B981',
                }}
              >
                <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginBottom: '0.25rem' }}>
                  Source Balance (Alice on Ledger 1)
                </div>
                <div className="font-mono" style={{ fontSize: '1.125rem', fontWeight: 700, color: '#F8FAFC' }}>
                  ₹600.00 <span style={{ fontSize: '0.8125rem', fontWeight: 400, color: '#94A3B8' }}>(Hold Released • 0 Residual Leak)</span>
                </div>
              </div>

              <div
                style={{
                  background: 'rgba(20, 28, 48, 0.75)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 'var(--radius-secondary, 20px)',
                  padding: '1.25rem 1.5rem',
                  borderLeft: '4px solid #10B981',
                }}
              >
                <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginBottom: '0.25rem' }}>
                  Destination Balance (Bob on Ledger 2)
                </div>
                <div className="font-mono" style={{ fontSize: '1.125rem', fontWeight: 700, color: '#F8FAFC' }}>
                  ₹400.00 <span style={{ fontSize: '0.8125rem', fontWeight: 400, color: '#94A3B8' }}>(Exact Single Credit • 0 Duplicate)</span>
                </div>
              </div>

              <div
                style={{
                  background: 'rgba(20, 28, 48, 0.75)',
                  border: '1px solid rgba(59, 130, 246, 0.35)',
                  borderRadius: 'var(--radius-secondary, 20px)',
                  padding: '1.25rem 1.5rem',
                  borderLeft: '4px solid #3B82F6',
                }}
              >
                <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginBottom: '0.25rem' }}>
                  Inter-Ledger Net Clearing Delta
                </div>
                <div className="font-mono" style={{ fontSize: '1.125rem', fontWeight: 700, color: '#60A5FA' }}>
                  Σ ΔL = -₹400.00 + ₹400.00 = ₹0.00
                </div>
              </div>
            </div>
          </div>

          <div
            style={{
              marginTop: '2rem',
              paddingTop: '1.25rem',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)',
              fontSize: '0.75rem',
              color: '#94A3B8',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>Reproduced via <code className="font-mono" style={{ color: '#E2E8F0' }}>./scripts/demo_signature_recovery.sh</code></span>
            <span style={{ color: '#34D399', fontWeight: 700 }}>8/8 Checks Passed</span>
          </div>
        </div>
      </div>
    </section>
  );
}
