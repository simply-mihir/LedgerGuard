import React from 'react';

export function ReconciliationSection() {
  return (
    <section
      id="reconciliation"
      style={{
        padding: '5rem 1.5rem',
        backgroundColor: 'var(--bg-stone-subtle)',
        borderTop: '1px solid var(--border-stone)',
        borderBottom: '1px solid var(--border-stone)',
      }}
    >
      <div
        style={{
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
            Post-Settlement Audit
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
            Stopped-and-drained multi-database reconciliation.
          </h2>
          <p
            style={{
              fontSize: '1.0625rem',
              color: 'var(--text-ink-secondary)',
              lineHeight: 1.65,
            }}
          >
            Rather than relying on continuous distributed locks during payment processing, LedgerGuard
            verifies mathematical conservation across participant databases through an explicit reconciliation engine.
          </p>
        </div>

        {/* 2-Card Asymmetric Audit Display */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '2rem',
            alignItems: 'stretch',
          }}
        >
          {/* Card 1: Core Mathematical Law */}
          <div
            style={{
              backgroundColor: 'var(--bg-paper)',
              border: '1px solid var(--border-stone)',
              borderRadius: 'var(--radius-sm)',
              padding: '2.5rem 2rem',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: 'var(--text-ink-muted)',
                  marginBottom: '1rem',
                }}
              >
                Fundamental Conservation Theorem
              </div>
              <div
                className="font-mono"
                style={{
                  fontSize: 'clamp(1.75rem, 3vw, 2.5rem)',
                  fontWeight: 700,
                  color: 'var(--text-ink)',
                  marginBottom: '1rem',
                  letterSpacing: '-0.03em',
                }}
              >
                Σ ΔL = ₹0.00
              </div>
              <p style={{ fontSize: '0.9375rem', color: 'var(--text-ink-secondary)', lineHeight: 1.6, marginBottom: '1.5rem' }}>
                For every rupee that departs Ledger 1, exactly one rupee must arrive on Ledger 2. The clearing accounts
                on both participant databases serve as mirror offsets that must sum to zero at all drained states.
              </p>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-stone)',
                border: '1px solid var(--border-stone)',
                borderRadius: 'var(--radius-xs)',
                padding: '1rem',
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '0.8125rem',
              }}
            >
              <span style={{ color: 'var(--text-ink-secondary)' }}>Clearing Balance Equivalence</span>
              <span className="font-mono" style={{ fontWeight: 600, color: 'var(--status-success)' }}>
                Exact Zero Equivalence
              </span>
            </div>
          </div>

          {/* Card 2: Drained Audit Execution */}
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
                  Multi-Database Audit Invariant Check
                </span>
                <span
                  className="font-mono"
                  style={{
                    fontSize: '0.6875rem',
                    color: 'var(--status-success-dark)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    padding: '0.2rem 0.5rem',
                    borderRadius: 'var(--radius-xs)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                  }}
                >
                  AUDIT: PASS
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--border-operational)' }}>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-operational-secondary)' }}>Accounts Examined</span>
                  <span className="font-mono" style={{ fontSize: '0.8125rem', color: '#FFFFFF', fontWeight: 600 }}>755 Active Accounts</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--border-operational)' }}>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-operational-secondary)' }}>Journals Examined</span>
                  <span className="font-mono" style={{ fontSize: '0.8125rem', color: '#FFFFFF', fontWeight: 600 }}>1,708 Postings (3,416 Lines)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--border-operational)' }}>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-operational-secondary)' }}>Trial Balance Verification</span>
                  <span className="font-mono" style={{ fontSize: '0.8125rem', color: 'var(--status-success-dark)', fontWeight: 600 }}>100% Balanced (Σ Dr = Σ Cr)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0' }}>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-operational-secondary)' }}>Discrepancies Observed</span>
                  <span className="font-mono" style={{ fontSize: '0.8125rem', color: 'var(--status-success-dark)', fontWeight: 600 }}>0 Integrity Violations</span>
                </div>
              </div>
            </div>

            <div
              style={{
                marginTop: '1.5rem',
                paddingTop: '1rem',
                borderTop: '1px solid var(--border-operational)',
                fontSize: '0.75rem',
                color: 'var(--text-operational-muted)',
                lineHeight: 1.5,
              }}
            >
              Audits are executed via <code className="font-mono">POST /v1/admin/reconciliation-runs</code> against isolated
              PostgreSQL instances. Discrepancies immediately raise an alert with itemized resource references.
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
