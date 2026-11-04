import React from 'react';
import Link from 'next/link';
import { SiteHeader } from '../components/web/site-header';
import { SiteFooter } from '../components/web/site-footer';
import { ArchitectureNarrative } from '../components/web/architecture-narrative';
import { AccountingGuaranteeSection } from '../components/web/accounting-guarantee-section';
import { FailureRecoverySection } from '../components/web/failure-recovery-section';
import { ReconciliationSection } from '../components/web/reconciliation-section';
import { VerificationSection } from '../components/web/verification-section';
import { ConsolePreviewSection } from '../components/web/console-preview-section';

export default function HomePage() {
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {/* Section 1: Editorial Navigation */}
      <SiteHeader currentPath="/" />

      <main id="main-content">
        {/* Section 2: Hero Narrative */}
        <section
          style={{
            padding: '5rem 1.5rem 6rem',
            maxWidth: '1280px',
            margin: '0 auto',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: '4rem',
              alignItems: 'center',
            }}
          >
            {/* Left Column: Editorial Headline & Actions */}
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: 'var(--accent-cobalt)',
                  marginBottom: '1.25rem',
                }}
              >
                <span>●</span>
                <span>Distributed Ledger Architecture</span>
              </div>

              <h1
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: 'clamp(2.5rem, 5vw, 4rem)',
                  fontWeight: 700,
                  lineHeight: 1.08,
                  letterSpacing: '-0.03em',
                  color: 'var(--text-ink)',
                  marginBottom: '1.5rem',
                }}
              >
                Financial state, without ambiguity.
              </h1>

              <p
                style={{
                  fontSize: '1.1875rem',
                  color: 'var(--text-ink-secondary)',
                  lineHeight: 1.6,
                  marginBottom: '2.5rem',
                  maxWidth: '540px',
                }}
              >
                Application-level Try-Confirm-Cancel (TCC) coordination, immutable double-entry accounting kernels,
                and post-settlement clearing reconciliation across independent PostgreSQL 17 failure domains.
              </p>

              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <Link href="/console" className="btn-editorial btn-primary" style={{ padding: '0.75rem 1.25rem' }}>
                  <span>Open Operator Console</span>
                  <span>→</span>
                </Link>
                <Link href="/architecture" className="btn-editorial btn-secondary" style={{ padding: '0.75rem 1.25rem' }}>
                  <span>Explore Architecture</span>
                </Link>
              </div>
            </div>

            {/* Right Column: Bespoke 3-Database Triad Topology Visual */}
            <div
              className="dark-operational-workspace"
              style={{
                padding: '2.25rem',
                borderRadius: 'var(--radius-md)',
                boxShadow: 'var(--shadow-operational)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderBottom: '1px solid var(--border-operational)',
                  paddingBottom: '1rem',
                  marginBottom: '1.5rem',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)', letterSpacing: '0.06em' }}>
                    DISTRIBUTED POSTGRESQL 17 MESH
                  </div>
                  <div style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#FFFFFF' }}>
                    Independent Isolation Domains
                  </div>
                </div>
                <div
                  className="font-mono"
                  style={{
                    fontSize: '0.6875rem',
                    color: 'var(--status-success-dark)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    padding: '0.2rem 0.5rem',
                    borderRadius: 'var(--radius-xs)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                  }}
                >
                  3/3 REACHABLE
                </div>
              </div>

              {/* Coordinator Visual Box */}
              <div
                className="dark-operational-panel"
                style={{
                  padding: '1.25rem',
                  marginBottom: '1.25rem',
                  borderLeft: '3px solid var(--accent-cobalt-light)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                  <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#FFFFFF' }}>
                    Coordinator Service & Directory
                  </span>
                  <span className="font-mono" style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)' }}>
                    Port :5442
                  </span>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-operational-secondary)' }}>
                  State machine transitions, idempotent requests, durable COMMIT/CANCEL logging.
                </div>
              </div>

              {/* Inter-Ledger Connection Indicator */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-around',
                  padding: '0.5rem 0',
                  color: 'var(--text-operational-muted)',
                  fontSize: '0.75rem',
                }}
              >
                <span>↙ Outbox Event</span>
                <span className="font-mono" style={{ color: 'var(--accent-cobalt-light)', fontSize: '0.6875rem' }}>
                  No Distributed XA / 2PC Locks
                </span>
                <span>↘ Outbox Event</span>
              </div>

              {/* 2 Participant Ledgers Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '1rem',
                  marginTop: '0.5rem',
                }}
              >
                <div
                  className="dark-operational-panel"
                  style={{
                    padding: '1.25rem',
                    borderTop: '2px solid var(--status-success-dark)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#FFFFFF' }}>
                      Ledger 1
                    </span>
                    <span className="font-mono" style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)' }}>
                      :5443
                    </span>
                  </div>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-operational-secondary)', lineHeight: 1.4 }}>
                    Participant DB: Alice Wallets & Clearing A/C
                  </div>
                </div>

                <div
                  className="dark-operational-panel"
                  style={{
                    padding: '1.25rem',
                    borderTop: '2px solid var(--status-success-dark)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#FFFFFF' }}>
                      Ledger 2
                    </span>
                    <span className="font-mono" style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)' }}>
                      :5444
                    </span>
                  </div>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-operational-secondary)', lineHeight: 1.4 }}>
                    Participant DB: Bob Wallets & Clearing A/C
                  </div>
                </div>
              </div>

              {/* Bottom Invariant Banner */}
              <div
                style={{
                  marginTop: '1.25rem',
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-xs)',
                  backgroundColor: 'rgba(29, 78, 216, 0.1)',
                  border: '1px solid rgba(29, 78, 216, 0.3)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#FFFFFF' }}>
                  Conservation Invariant
                </span>
                <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cobalt-light)', fontWeight: 700 }}>
                  Σ ΔL = ₹0.00
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Section 3: Scroll-Led Architecture Narrative */}
        <ArchitectureNarrative />

        {/* Section 4: Accounting Guarantees */}
        <AccountingGuaranteeSection />

        {/* Section 5: Signature Failure Recovery */}
        <FailureRecoverySection />

        {/* Section 6: Post-Settlement Reconciliation */}
        <ReconciliationSection />

        {/* Section 7: Engineering Verification Evidence */}
        <VerificationSection />

        {/* Section 8: Operator Console Preview */}
        <ConsolePreviewSection />

        {/* Section 9: Final Call to Action Strip */}
        <section
          style={{
            padding: '5rem 1.5rem',
            textAlign: 'center',
            maxWidth: '800px',
            margin: '0 auto',
          }}
        >
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: 'clamp(2rem, 3.5vw, 2.75rem)',
              fontWeight: 700,
              color: 'var(--text-ink)',
              marginBottom: '1rem',
            }}
          >
            Ready to inspect the distributed ledger?
          </h2>
          <p
            style={{
              fontSize: '1.0625rem',
              color: 'var(--text-ink-secondary)',
              lineHeight: 1.6,
              marginBottom: '2rem',
            }}
          >
            Access the authenticated operator control plane to observe active journals, review TCC transfer audit trails,
            and execute non-blocking multi-database audits.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <Link href="/console" className="btn-editorial btn-primary" style={{ padding: '0.75rem 1.5rem' }}>
              <span>Enter Operator Console</span>
              <span>→</span>
            </Link>
            <a
              href="https://github.com/simply-mihir/LedgerGuard"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-editorial btn-secondary"
              style={{ padding: '0.75rem 1.5rem' }}
            >
              <span>GitHub Repository</span>
              <span>↗</span>
            </a>
          </div>
        </section>
      </main>

      {/* Section 10: Editorial Footer */}
      <SiteFooter />
    </>
  );
}
