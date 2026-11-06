import React from 'react';

export function ReconciliationSection() {
  return (
    <section
      id="reconciliation"
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
          <span>Post-Settlement Audit</span>
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
          Stopped-and-drained multi-database reconciliation.
        </h2>
        <p
          style={{
            fontSize: '1.125rem',
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
          className="glass-supporting"
          style={{
            borderRadius: 'var(--radius-primary, 28px)',
            padding: '2.5rem',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            background: 'rgba(255, 255, 255, 0.80)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.75)',
            boxShadow: '0 20px 48px -12px rgba(15, 23, 42, 0.06), 0 0 0 1px rgba(255, 255, 255, 0.8) inset',
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
                fontSize: 'clamp(2rem, 3.5vw, 2.75rem)',
                fontWeight: 700,
                color: 'var(--text-ink)',
                marginBottom: '1rem',
                letterSpacing: '-0.03em',
              }}
            >
              Σ ΔL = ₹0.00
            </div>
            <p style={{ fontSize: '0.9375rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65, marginBottom: '2rem' }}>
              For every rupee that departs Ledger 1, exactly one rupee must arrive on Ledger 2. The clearing accounts
              on both participant databases serve as mirror offsets that must sum to zero at all drained states.
            </p>
          </div>

          <div
            style={{
              backgroundColor: 'rgba(15, 23, 42, 0.04)',
              border: '1px solid rgba(226, 232, 240, 0.9)',
              borderRadius: 'var(--radius-secondary, 20px)',
              padding: '1.25rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: '0.8125rem',
            }}
          >
            <span style={{ color: 'var(--text-ink-secondary)' }}>Clearing Balance Equivalence</span>
            <span
              className="font-mono"
              style={{
                fontWeight: 700,
                color: 'var(--status-success)',
                background: 'rgba(5, 150, 105, 0.12)',
                padding: '0.2rem 0.55rem',
                borderRadius: 'var(--radius-pill, 9999px)',
              }}
            >
              Exact Zero Equivalence
            </span>
          </div>
        </div>

        {/* Card 2: Drained Audit Execution */}
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
                Multi-Database Audit Invariant Check
              </span>
              <span
                className="font-mono"
                style={{
                  fontSize: '0.6875rem',
                  color: '#34D399',
                  backgroundColor: 'rgba(16, 185, 129, 0.15)',
                  padding: '0.25rem 0.65rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  border: '1px solid rgba(16, 185, 129, 0.35)',
                  fontWeight: 700,
                }}
              >
                AUDIT: PASS
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <span style={{ fontSize: '0.8125rem', color: '#94A3B8' }}>Accounts Examined</span>
                <span className="font-mono" style={{ fontSize: '0.8125rem', color: '#F8FAFC', fontWeight: 600 }}>755 Active Accounts</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <span style={{ fontSize: '0.8125rem', color: '#94A3B8' }}>Journals Examined</span>
                <span className="font-mono" style={{ fontSize: '0.8125rem', color: '#F8FAFC', fontWeight: 600 }}>1,708 Postings (3,416 Lines)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <span style={{ fontSize: '0.8125rem', color: '#94A3B8' }}>Trial Balance Verification</span>
                <span className="font-mono" style={{ fontSize: '0.8125rem', color: '#34D399', fontWeight: 600 }}>100% Balanced (Σ Dr = Σ Cr)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0' }}>
                <span style={{ fontSize: '0.8125rem', color: '#94A3B8' }}>Discrepancies Observed</span>
                <span className="font-mono" style={{ fontSize: '0.8125rem', color: '#34D399', fontWeight: 600 }}>0 Integrity Violations</span>
              </div>
            </div>
          </div>

          <div
            style={{
              marginTop: '1.75rem',
              paddingTop: '1.25rem',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)',
              fontSize: '0.75rem',
              color: '#94A3B8',
              lineHeight: 1.5,
            }}
          >
            Audits are executed via <code className="font-mono" style={{ color: '#E2E8F0' }}>POST /v1/admin/reconciliation-runs</code> against isolated
            PostgreSQL instances. Discrepancies immediately raise an alert with itemized resource references.
          </div>
        </div>
      </div>
    </section>
  );
}
