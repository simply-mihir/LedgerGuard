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
    <div className="ambient-gradient-field" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', overflowX: 'hidden', width: '100%' }}>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {/* Floating Rounded Glass Navigation */}
      <SiteHeader currentPath="/" />

      <main id="main-content" style={{ flex: 1 }}>
        {/* Section 1: Hero Experience */}
        <section
          style={{
            padding: '4.5rem 1.5rem 5.5rem',
            maxWidth: '1240px',
            margin: '0 auto',
            position: 'relative',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: '3.5rem',
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
                  background: 'rgba(29, 78, 216, 0.08)',
                  padding: '0.35rem 0.85rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  border: '1px solid rgba(29, 78, 216, 0.18)',
                  marginBottom: '1.5rem',
                }}
              >
                <span>●</span>
                <span>Autonomous 3-Database Triad Architecture</span>
              </div>

              <h1
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: 'clamp(2.75rem, 5.5vw, 4.25rem)',
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
                  lineHeight: 1.65,
                  marginBottom: '2.5rem',
                  maxWidth: '540px',
                }}
              >
                Application-level Try-Confirm-Cancel (TCC) coordination, immutable double-entry accounting kernels,
                and post-settlement clearing reconciliation across independent PostgreSQL 17 failure domains.
              </p>

              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <Link
                  href="/console"
                  className="btn-editorial btn-primary"
                  style={{
                    padding: '0.85rem 1.6rem',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    fontSize: '0.9375rem',
                  }}
                >
                  <span>Open Operator Console</span>
                  <span style={{ fontSize: '1rem' }}>→</span>
                </Link>
                <Link
                  href="/architecture"
                  className="btn-editorial btn-secondary"
                  style={{
                    padding: '0.85rem 1.6rem',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    fontSize: '0.9375rem',
                  }}
                >
                  <span>Explore Architecture</span>
                </Link>
              </div>
            </div>

            {/* Right Column: Layered Glass Architecture Visual */}
            <div
              className="glass-hero-dark"
              style={{
                borderRadius: 'var(--radius-primary, 28px)',
                padding: '2.25rem',
                position: 'relative',
                overflow: 'hidden',
                background: 'rgba(14, 20, 34, 0.76)',
                backdropFilter: 'blur(28px)',
                WebkitBackdropFilter: 'blur(28px)',
                border: '1px solid rgba(56, 189, 248, 0.20)',
                boxShadow: '0 24px 60px -12px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255, 255, 255, 0.12) inset',
              }}
            >
              {/* Header Telemetry */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                  paddingBottom: '1.25rem',
                  marginBottom: '1.5rem',
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: '0.6875rem',
                      fontFamily: 'var(--font-mono)',
                      color: '#94A3B8',
                      letterSpacing: '0.06em',
                      textTransform: 'uppercase',
                    }}
                  >
                    PostgreSQL 17 Triad Architecture
                  </div>
                  <div style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#F8FAFC', marginTop: '0.15rem' }}>
                    Zero Distributed 2PC Locks
                  </div>
                </div>
                <div
                  style={{
                    fontSize: '0.6875rem',
                    fontFamily: 'var(--font-mono)',
                    color: '#34D399',
                    backgroundColor: 'rgba(16, 185, 129, 0.15)',
                    padding: '0.25rem 0.65rem',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    border: '1px solid rgba(16, 185, 129, 0.35)',
                    fontWeight: 700,
                  }}
                >
                  3/3 REACHABLE
                </div>
              </div>

              {/* Coordinator Visual Panel */}
              <div
                style={{
                  background: 'rgba(20, 28, 48, 0.75)',
                  border: '1px solid rgba(59, 130, 246, 0.35)',
                  borderRadius: 'var(--radius-secondary, 20px)',
                  padding: '1.25rem 1.5rem',
                  marginBottom: '1.25rem',
                  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.3)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                  <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#F8FAFC' }}>
                    Coordinator Service & Directory
                  </span>
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.6875rem',
                      color: '#93C5FD',
                      background: 'rgba(59, 130, 246, 0.15)',
                      padding: '0.15rem 0.5rem',
                      borderRadius: 'var(--radius-pill, 9999px)',
                      border: '1px solid rgba(59, 130, 246, 0.3)',
                    }}
                  >
                    Port :5442
                  </span>
                </div>
                <div style={{ fontSize: '0.75rem', color: '#94A3B8', lineHeight: 1.45 }}>
                  State machine transitions, idempotent request deduplication, durable COMMIT decision log.
                </div>
              </div>

              {/* TCC Messaging Pulse Bar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-around',
                  padding: '0.5rem 0',
                  color: '#94A3B8',
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <span style={{ color: '#60A5FA' }}>↙ Try / Confirm</span>
                <span style={{ color: '#38BDF8', fontSize: '0.6875rem', background: 'rgba(255, 255, 255, 0.05)', padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-pill, 9999px)' }}>
                  Asynchronous Forward Recovery
                </span>
                <span style={{ color: '#60A5FA' }}>↘ Try / Confirm</span>
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
                {/* Ledger 1 */}
                <div
                  style={{
                    background: 'rgba(20, 28, 48, 0.75)',
                    border: '1px solid rgba(56, 189, 248, 0.25)',
                    borderRadius: 'var(--radius-secondary, 20px)',
                    padding: '1.25rem',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#F8FAFC' }}>
                      Ledger 1
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.6875rem',
                        color: '#38BDF8',
                      }}
                    >
                      :5443
                    </span>
                  </div>
                  <div style={{ fontSize: '0.6875rem', color: '#94A3B8', lineHeight: 1.4 }}>
                    Alice Wallets, Account Holds & Inter-Ledger Clearing A/C
                  </div>
                </div>

                {/* Ledger 2 */}
                <div
                  style={{
                    background: 'rgba(20, 28, 48, 0.75)',
                    border: '1px solid rgba(56, 189, 248, 0.25)',
                    borderRadius: 'var(--radius-secondary, 20px)',
                    padding: '1.25rem',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#F8FAFC' }}>
                      Ledger 2
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.6875rem',
                        color: '#38BDF8',
                      }}
                    >
                      :5444
                    </span>
                  </div>
                  <div style={{ fontSize: '0.6875rem', color: '#94A3B8', lineHeight: 1.4 }}>
                    Bob Wallets, Command Inbox & Inter-Ledger Clearing A/C
                  </div>
                </div>
              </div>

              {/* Bottom Invariant Banner */}
              <div
                style={{
                  marginTop: '1.25rem',
                  padding: '0.875rem 1.25rem',
                  borderRadius: 'var(--radius-control, 14px)',
                  background: 'rgba(29, 78, 216, 0.15)',
                  border: '1px solid rgba(59, 130, 246, 0.35)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#F1F5F9' }}>
                  Clearing Conservation Invariant
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.8125rem',
                    color: '#34D399',
                    fontWeight: 700,
                  }}
                >
                  Σ ΔL = ₹0.00
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Section 2: Apple-Style Scroll Narrative */}
        <ArchitectureNarrative />

        {/* Section 3: Accounting Guarantees */}
        <AccountingGuaranteeSection />

        {/* Section 4: Signature Failure Recovery */}
        <FailureRecoverySection />

        {/* Section 5: Post-Settlement Reconciliation */}
        <ReconciliationSection />

        {/* Section 6: Engineering Verification Evidence */}
        <VerificationSection />

        {/* Section 7: Operator Console Preview */}
        <ConsolePreviewSection />

        {/* Section 8: Final Call to Action Strip */}
        <section
          style={{
            padding: '6rem 1.5rem',
            textAlign: 'center',
            maxWidth: '860px',
            margin: '0 auto',
          }}
        >
          <div
            className="glass-supporting"
            style={{
              borderRadius: 'var(--radius-primary, 28px)',
              padding: '3.5rem 2.5rem',
              background: 'rgba(255, 255, 255, 0.85)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.8)',
              boxShadow: '0 24px 60px -12px rgba(15, 23, 42, 0.08)',
            }}
          >
            <h2
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: 'clamp(2rem, 3.5vw, 2.75rem)',
                fontWeight: 700,
                color: 'var(--text-ink)',
                marginBottom: '1rem',
                lineHeight: 1.2,
              }}
            >
              Ready to inspect the distributed ledger?
            </h2>
            <p
              style={{
                fontSize: '1.0625rem',
                color: 'var(--text-ink-secondary)',
                lineHeight: 1.65,
                marginBottom: '2.25rem',
                maxWidth: '620px',
                margin: '0 auto 2.25rem',
              }}
            >
              Access the authenticated operator control plane to observe active journals, review TCC transfer audit trails,
              and execute non-blocking multi-database audits.
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap' }}>
              <Link
                href="/console"
                className="btn-editorial btn-primary"
                style={{ padding: '0.85rem 1.75rem', borderRadius: 'var(--radius-pill, 9999px)' }}
              >
                <span>Enter Operator Console</span>
                <span>→</span>
              </Link>
              <a
                href="https://github.com/simply-mihir/LedgerGuard"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-editorial btn-secondary"
                style={{ padding: '0.85rem 1.75rem', borderRadius: 'var(--radius-pill, 9999px)' }}
              >
                <span>GitHub Repository</span>
                <span>↗</span>
              </a>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <SiteFooter />
    </div>
  );
}
