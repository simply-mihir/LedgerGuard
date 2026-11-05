import React from 'react';
import Link from 'next/link';
import { SiteHeader } from '../../components/web/site-header';
import { SiteFooter } from '../../components/web/site-footer';

export const metadata = {
  title: 'Security & Isolation Model — LedgerGuard',
  description: 'Security architecture, isolation domains, integer arithmetic, and educational disclosures for LedgerGuard.',
};

export default function SecurityPage() {
  return (
    <div className="ambient-gradient-field" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <SiteHeader currentPath="/security" />

      <main id="main-content" style={{ padding: '4rem 1.5rem 6rem', maxWidth: '1080px', margin: '0 auto', flex: 1, width: '100%' }}>
        {/* Header */}
        <div style={{ marginBottom: '3.5rem' }}>
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
              marginBottom: '1rem',
            }}
          >
            <span>●</span>
            <span>Trust & Invariant Boundaries</span>
          </div>
          <h1
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: 'clamp(2.25rem, 4.5vw, 3.5rem)',
              fontWeight: 700,
              lineHeight: 1.1,
              letterSpacing: '-0.03em',
              color: 'var(--text-ink)',
              marginBottom: '1.25rem',
            }}
          >
            Security Architecture & Invariant Enforcement
          </h1>
          <p
            style={{
              fontSize: '1.1875rem',
              color: 'var(--text-ink-secondary)',
              lineHeight: 1.6,
            }}
          >
            How LedgerGuard enforces financial integrity, protects database isolation domains, and safeguards operator access.
          </p>
        </div>

        {/* Section 1: Isolation Domains */}
        <section style={{ marginBottom: '4rem' }}>
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.75rem',
              fontWeight: 700,
              color: 'var(--text-ink)',
              marginBottom: '1rem',
            }}
          >
            1. Autonomous Database Isolation Domains
          </h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65, marginBottom: '1.5rem' }}>
            LedgerGuard treats every database as an independent failure domain. Participant databases (Ledger 1 and Ledger 2)
            possess their own local PostgreSQL write-ahead logs, transaction managers, and connection pools:
          </p>
          <ul style={{ paddingLeft: '1.5rem', color: 'var(--text-ink-secondary)', fontSize: '0.9375rem', lineHeight: 1.75 }}>
            <li><strong>No cross-database foreign keys:</strong> Account balances on Ledger 1 are completely decoupled from Ledger 2.</li>
            <li><strong>No distributed locks:</strong> A network outage between coordinator and participants never leaves open XA transaction locks hanging in participant databases.</li>
            <li><strong>Durable local state:</strong> Balance holds reside directly in local participant tables (<code className="font-mono">account_holds</code>), ensuring that a coordinator crash does not cause funds to leak or unlock.</li>
          </ul>
        </section>

        {/* Section 2: PostgreSQL Role Separation */}
        <section style={{ marginBottom: '4rem' }}>
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.75rem',
              fontWeight: 700,
              color: 'var(--text-ink)',
              marginBottom: '1rem',
            }}
          >
            2. Database Role Separation
          </h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65, marginBottom: '1.75rem' }}>
            Access to database schemas is segmented across least-privilege PostgreSQL roles:
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
            <div
              className="glass-supporting"
              style={{
                padding: '1.75rem',
                background: 'rgba(255, 255, 255, 0.80)',
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                border: '1px solid rgba(255, 255, 255, 0.75)',
                borderRadius: 'var(--radius-secondary, 20px)',
                boxShadow: '0 12px 32px -8px rgba(15, 23, 42, 0.05)',
              }}
            >
              <div className="font-mono" style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--accent-cobalt)', marginBottom: '0.5rem' }}>
                ledgerguard_app
              </div>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.55 }}>
                Runtime service role. Permitted SELECT, INSERT, and UPDATE on application tables. Explicitly denied DDL modifications or TRUNCATE operations.
              </p>
            </div>

            <div
              className="glass-supporting"
              style={{
                padding: '1.75rem',
                background: 'rgba(255, 255, 255, 0.80)',
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                border: '1px solid rgba(255, 255, 255, 0.75)',
                borderRadius: 'var(--radius-secondary, 20px)',
                boxShadow: '0 12px 32px -8px rgba(15, 23, 42, 0.05)',
              }}
            >
              <div className="font-mono" style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--accent-cobalt)', marginBottom: '0.5rem' }}>
                ledgerguard_admin
              </div>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.55 }}>
                Migration and provisioning role. Strictly isolated to administrative migration CLI runners (<code className="font-mono">ledgerguard.cli migrate</code>).
              </p>
            </div>

            <div
              className="glass-supporting"
              style={{
                padding: '1.75rem',
                background: 'rgba(255, 255, 255, 0.80)',
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                border: '1px solid rgba(255, 255, 255, 0.75)',
                borderRadius: 'var(--radius-secondary, 20px)',
                boxShadow: '0 12px 32px -8px rgba(15, 23, 42, 0.05)',
              }}
            >
              <div className="font-mono" style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--accent-cobalt)', marginBottom: '0.5rem' }}>
                ledgerguard_reporter
              </div>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.55 }}>
                Read-only audit role. Permitted SELECT only on journal lines, account directory entries, and workflow audit events.
              </p>
            </div>
          </div>
        </section>

        {/* Section 3: Operator Authentication & Session Security */}
        <section style={{ marginBottom: '4rem' }}>
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.75rem',
              fontWeight: 700,
              color: 'var(--text-ink)',
              marginBottom: '1rem',
            }}
          >
            3. Operator Authentication & Session Hardening
          </h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65, marginBottom: '1.5rem' }}>
            The operator console requires verified session credentials:
          </p>
          <ul style={{ paddingLeft: '1.5rem', color: 'var(--text-ink-secondary)', fontSize: '0.9375rem', lineHeight: 1.75 }}>
            <li><strong>Argon2id password hashing:</strong> Passwords are never stored in plaintext or reversible formats; hashes use memory-hard Argon2id.</li>
            <li><strong>Time-Based One-Time Password (TOTP):</strong> Two-factor authentication complies with RFC 6238 using a 30-second time step.</li>
            <li><strong>HttpOnly, SameSite Session Cookies:</strong> Tokens are never exposed to browser localStorage or client-side JavaScript.</li>
            <li><strong>Brute-force protection:</strong> Repeated failed attempts trigger escalating delays and automated account lockout.</li>
            <li><strong>Safe relative redirects:</strong> The authentication router validates return URLs, strictly rejecting external redirect targets.</li>
          </ul>
        </section>

        {/* Section 4: Educational Portfolio Disclosure */}
        <section
          className="glass-supporting"
          style={{
            background: 'rgba(255, 255, 255, 0.85)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.80)',
            borderRadius: 'var(--radius-primary, 28px)',
            padding: '2.5rem',
            marginBottom: '4rem',
            boxShadow: '0 16px 40px -12px rgba(15, 23, 42, 0.06)',
          }}
        >
          <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-cobalt)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
            Portfolio & Educational Disclosure
          </div>
          <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-ink)', marginBottom: '0.75rem' }}>
            Educational Research Artifact
          </h3>
          <p style={{ fontSize: '0.9375rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65 }}>
            LedgerGuard is an open-source educational systems implementation created to demonstrate real-world financial ledger
            guarantees: application-level TCC coordination, transactional outboxes, forward crash recovery, and multi-database
            clearing reconciliation. It is not an FDIC-insured institution, payment gateway, or commercial banking service.
          </p>
        </section>

        {/* Back Link CTA */}
        <div style={{ borderTop: '1px solid rgba(226, 232, 240, 0.8)', paddingTop: '2.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <Link href="/" className="btn-editorial btn-secondary" style={{ borderRadius: 'var(--radius-pill, 9999px)' }}>
            ← Return to Overview
          </Link>
          <Link href="/login" className="btn-editorial btn-primary" style={{ borderRadius: 'var(--radius-pill, 9999px)' }}>
            Operator Login →
          </Link>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
