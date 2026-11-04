'use client';

import React, { useState } from 'react';
import Link from 'next/link';

interface SiteHeaderProps {
  currentPath?: string;
}

export function SiteHeader({ currentPath = '/' }: SiteHeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        backgroundColor: 'rgba(249, 248, 246, 0.94)',
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid var(--border-stone)',
      }}
    >
      <div
        style={{
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '1rem 1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        {/* Brand Wordmark */}
        <Link
          href="/"
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: '0.5rem',
            textDecoration: 'none',
            color: 'var(--text-ink)',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.35rem',
              fontWeight: 700,
              letterSpacing: '-0.02em',
            }}
          >
            LedgerGuard
          </span>
          <span
            style={{
              fontSize: '0.6875rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: 'var(--accent-cobalt)',
            }}
          >
            TCC Engine
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav
          className="hidden md:flex"
          style={{
            alignItems: 'center',
            gap: '2rem',
          }}
        >
          <Link
            href="/architecture"
            style={{
              fontSize: '0.875rem',
              fontWeight: currentPath === '/architecture' ? 600 : 500,
              color: currentPath === '/architecture' ? 'var(--accent-cobalt)' : 'var(--text-ink-secondary)',
              textDecoration: 'none',
              transition: 'color 0.15s ease',
            }}
          >
            Architecture
          </Link>
          <Link
            href="/#guarantees"
            style={{
              fontSize: '0.875rem',
              fontWeight: 500,
              color: 'var(--text-ink-secondary)',
              textDecoration: 'none',
              transition: 'color 0.15s ease',
            }}
          >
            Guarantees
          </Link>
          <Link
            href="/#failure-recovery"
            style={{
              fontSize: '0.875rem',
              fontWeight: 500,
              color: 'var(--text-ink-secondary)',
              textDecoration: 'none',
              transition: 'color 0.15s ease',
            }}
          >
            Failure Recovery
          </Link>
          <Link
            href="/security"
            style={{
              fontSize: '0.875rem',
              fontWeight: currentPath === '/security' ? 600 : 500,
              color: currentPath === '/security' ? 'var(--accent-cobalt)' : 'var(--text-ink-secondary)',
              textDecoration: 'none',
              transition: 'color 0.15s ease',
            }}
          >
            Security
          </Link>
          <a
            href="https://github.com/simply-mihir/LedgerGuard"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontSize: '0.875rem',
              fontWeight: 500,
              color: 'var(--text-ink-secondary)',
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
          >
            GitHub
            <span style={{ fontSize: '0.75rem', opacity: 0.6 }}>↗</span>
          </a>
        </nav>

        {/* Header Action */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Link
            href="/console"
            className="btn-editorial btn-primary"
            style={{
              fontSize: '0.8125rem',
              padding: '0.5rem 0.875rem',
            }}
          >
            <span>Operator Console</span>
            <span style={{ fontSize: '0.75rem' }}>→</span>
          </Link>

          {/* Mobile hamburger button */}
          <button
            type="button"
            className="md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
            aria-expanded={mobileMenuOpen}
            style={{
              background: 'none',
              border: '1px solid var(--border-stone)',
              borderRadius: 'var(--radius-sm)',
              padding: '0.45rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-ink)',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div
          className="md:hidden"
          style={{
            borderTop: '1px solid var(--border-stone)',
            backgroundColor: 'var(--bg-stone)',
            padding: '1.25rem 1.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
          }}
        >
          <Link
            href="/architecture"
            onClick={() => setMobileMenuOpen(false)}
            style={{
              fontSize: '1rem',
              fontWeight: 500,
              color: 'var(--text-ink)',
              textDecoration: 'none',
              padding: '0.5rem 0',
              borderBottom: '1px solid var(--border-stone-subtle)',
            }}
          >
            Architecture
          </Link>
          <Link
            href="/#guarantees"
            onClick={() => setMobileMenuOpen(false)}
            style={{
              fontSize: '1rem',
              fontWeight: 500,
              color: 'var(--text-ink)',
              textDecoration: 'none',
              padding: '0.5rem 0',
              borderBottom: '1px solid var(--border-stone-subtle)',
            }}
          >
            Accounting Guarantees
          </Link>
          <Link
            href="/#failure-recovery"
            onClick={() => setMobileMenuOpen(false)}
            style={{
              fontSize: '1rem',
              fontWeight: 500,
              color: 'var(--text-ink)',
              textDecoration: 'none',
              padding: '0.5rem 0',
              borderBottom: '1px solid var(--border-stone-subtle)',
            }}
          >
            Failure Recovery
          </Link>
          <Link
            href="/security"
            onClick={() => setMobileMenuOpen(false)}
            style={{
              fontSize: '1rem',
              fontWeight: 500,
              color: 'var(--text-ink)',
              textDecoration: 'none',
              padding: '0.5rem 0',
              borderBottom: '1px solid var(--border-stone-subtle)',
            }}
          >
            Security Model
          </Link>
          <a
            href="https://github.com/simply-mihir/LedgerGuard"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontSize: '1rem',
              fontWeight: 500,
              color: 'var(--text-ink-secondary)',
              textDecoration: 'none',
              padding: '0.5rem 0',
            }}
          >
            View on GitHub ↗
          </a>
        </div>
      )}
    </header>
  );
}
