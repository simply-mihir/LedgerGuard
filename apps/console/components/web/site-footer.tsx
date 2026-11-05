import React from 'react';
import Link from 'next/link';

export function SiteFooter() {
  return (
    <footer
      style={{
        borderTop: '1px solid rgba(226, 232, 240, 0.8)',
        background: 'rgba(255, 255, 255, 0.75)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        padding: '4rem 1.5rem 3rem',
        marginTop: 'auto',
      }}
    >
      <div
        style={{
          maxWidth: '1240px',
          margin: '0 auto',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '2.5rem',
            marginBottom: '3rem',
          }}
        >
          {/* Brand & Purpose */}
          <div>
            <div
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.35rem',
                fontWeight: 700,
                color: 'var(--text-ink)',
                marginBottom: '0.85rem',
              }}
            >
              LedgerGuard
            </div>
            <p
              style={{
                fontSize: '0.9375rem',
                color: 'var(--text-ink-secondary)',
                lineHeight: 1.6,
                maxWidth: '360px',
              }}
            >
              Auditable distributed financial engine built with application-level Try-Confirm-Cancel
              coordination, transactional outbox messaging, and post-settlement clearing reconciliation
              across independent PostgreSQL 17 databases.
            </p>
          </div>

          {/* Navigation Links */}
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
              System Documentation
            </div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
              <li>
                <Link
                  href="/architecture"
                  style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', textDecoration: 'none' }}
                >
                  Architecture Overview
                </Link>
              </li>
              <li>
                <Link
                  href="/#guarantees"
                  style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', textDecoration: 'none' }}
                >
                  Accounting Invariants
                </Link>
              </li>
              <li>
                <Link
                  href="/#failure-recovery"
                  style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', textDecoration: 'none' }}
                >
                  Signature Failure Scenarios
                </Link>
              </li>
              <li>
                <Link
                  href="/security"
                  style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', textDecoration: 'none' }}
                >
                  Security & Isolation Model
                </Link>
              </li>
            </ul>
          </div>

          {/* Operator Operations */}
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
              Control Plane
            </div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
              <li>
                <Link
                  href="/login"
                  style={{ fontSize: '0.875rem', color: 'var(--accent-cobalt)', textDecoration: 'none', fontWeight: 600 }}
                >
                  Operator Authentication →
                </Link>
              </li>
              <li>
                <Link
                  href="/console"
                  style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', textDecoration: 'none' }}
                >
                  Operator Console Shell
                </Link>
              </li>
              <li>
                <a
                  href="https://github.com/simply-mihir/LedgerGuard"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', textDecoration: 'none' }}
                >
                  GitHub Repository ↗
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Disclaimer */}
        <div
          style={{
            borderTop: '1px solid rgba(226, 232, 240, 0.8)',
            paddingTop: '1.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
            fontSize: '0.75rem',
            color: 'var(--text-ink-muted)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <span>© 2026 LedgerGuard. Open-source distributed financial systems engineering.</span>
            <span>Designed and tested against WCAG 2.2 AA criteria • Release v1.0.0</span>
          </div>
          <p style={{ lineHeight: 1.5 }}>
            LedgerGuard is an educational financial ledger implementation and portfolio artifact demonstrating
            crash-resilient TCC protocols and multi-database clearing reconciliation without distributed database locks.
          </p>
        </div>
      </div>
    </footer>
  );
}
