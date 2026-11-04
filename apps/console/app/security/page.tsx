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
    <>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <SiteHeader currentPath="/security" />

      <main id="main-content" style={{ padding: '4rem 1.5rem 6rem', maxWidth: '1000px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '3.5rem' }}>
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
            Trust & Invariant Boundaries
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
        <section style={{ marginBottom: '3.5rem' }}>
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
          <ul style={{ paddingLeft: '1.5rem', color: 'var(--text-ink-secondary)', fontSize: '0.9375rem', lineHeight: 1.7 }}>
            <li><strong>No cross-database foreign keys:</strong> Account balances on Ledger 1 are completely decoupled from Ledger 2.</li>
            <li><strong>No distributed locks:</strong> A network outage between coordinator and participants never leaves open XA transaction locks hanging in participant databases.</li>
            <li><strong>Durable local state:</strong> Balance holds reside directly in local participant tables (<code className="font-mono">account_holds</code>), ensuring that a coordinator crash does not cause funds to leak or unlock.</li>
          </ul>
        </section>

        {/* Section 2: PostgreSQL Role Separation */}
        <section style={{ marginBottom: '3.5rem' }}>
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
          <p style={{ fontSize: '1rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65, marginBottom: '1.5rem' }}>
            Access to database schemas is segmented across least-privilege PostgreSQL roles:
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1.25rem' }}>
            <div style={{ padding: '1.5rem', backgroundColor: 'var(--bg-paper)', border: '1px solid var(--border-stone)', borderRadius: 'var(--radius-sm)' }}>
              <div className="font-mono" style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-ink)', marginBottom: '0.5rem' }}>
                ledgerguard_app
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
                Runtime service role. Permitted SELECT, INSERT, and UPDATE on application tables. Explicitly denied DDL modifications or TRUNCATE operations.
              </p>
            </div>

            <div style={{ padding: '1.5rem', backgroundColor: 'var(--bg-paper)', border: '1px solid var(--border-stone)', borderRadius: 'var(--radius-sm)' }}>
              <div className="font-mono" style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-ink)', marginBottom: '0.5rem' }}>
                ledgerguard_admin
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
                Migration and provisioning role. Strictly isolated to administrative migration CLI runners (<code className="font-mono">ledgerguard.cli migrate</code>).
              </p>
            </div>

            <div style={{ padding: '1.5rem', backgroundColor: 'var(--bg-paper)', border: '1px solid var(--border-stone)', borderRadius: 'var(--radius-sm)' }}>
              <div className="font-mono" style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-ink)', marginBottom: '0.5rem' }}>
                ledgerguard_reporter
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
                Read-only audit role. Permitted SELECT only on journal lines, account directory entries, and workflow audit events.
              </p>
            </div>
          </div>
        </section>

        {/* Section 3: Operator Authentication & Session Security */}
        <section style={{ marginBottom: '3.5rem' }}>
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
          <ul style={{ paddingLeft: '1.5rem', color: 'var(--text-ink-secondary)', fontSize: '0.9375rem', lineHeight: 1.7 }}>
            <li><strong>Argon2id password hashing:</strong> Passwords are never stored in plaintext or reversible formats; hashes use memory-hard Argon2id.</li>
            <li><strong>Time-Based One-Time Password (TOTP):</strong> Two-factor authentication complies with RFC 6238 using a 30-second time step.</li>
            <li><strong>HttpOnly, SameSite Session Cookies:</strong> Tokens are never exposed to browser localStorage or client-side JavaScript.</li>
            <li><strong>Brute-force protection:</strong> Repeated failed attempts trigger escalating delays and automated account lockout.</li>
            <li><strong>Safe relative redirects:</strong> The authentication router validates return URLs, strictly rejecting external redirect targets.</li>
          </ul>
        </section>

        {/* Section 4: Educational Portfolio Disclosure */}
        <section
          style={{
            backgroundColor: 'var(--bg-paper)',
            border: '1px solid var(--border-stone)',
            borderRadius: 'var(--radius-sm)',
            padding: '2rem',
            marginBottom: '3.5rem',
          }}
        >
          <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-cobalt)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
            Portfolio & Educational Disclosure
          </div>
          <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-ink)', marginBottom: '0.75rem' }}>
            Educational Research Artifact
          </h3>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65 }}>
            LedgerGuard is an open-source educational systems implementation created to demonstrate real-world financial ledger
            guarantees: application-level TCC coordination, transactional outboxes, forward crash recovery, and multi-database
            clearing reconciliation. It is not an FDIC-insured institution, payment gateway, or commercial banking service.
          </p>
        </section>

        {/* Back Link CTA */}
        <div style={{ borderTop: '1px solid var(--border-stone)', paddingTop: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Link href="/" className="btn-editorial btn-secondary">
            ← Return to Overview
          </Link>
          <Link href="/login" className="btn-editorial btn-primary">
            Operator Login →
          </Link>
        </div>
      </main>

      <SiteFooter />
    </>
  );
}
