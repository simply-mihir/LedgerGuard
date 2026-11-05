'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';

interface SiteHeaderProps {
  currentPath?: string;
}

export function SiteHeader({ currentPath = '/' }: SiteHeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const mobileDrawerRef = useRef<HTMLDivElement>(null);
  const hamburgerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const handleScroll = () => {
      const scrolled = window.scrollY > 24;
      if (scrolled !== isScrolled) {
        setIsScrolled(scrolled);
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, [isScrolled]);

  // Handle focus trapping and escape key for mobile drawer
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = 'hidden';
      const focusableElements = mobileDrawerRef.current?.querySelectorAll<HTMLElement>(
        'a, button, [tabindex]:not([tabindex="-1"])'
      );
      if (focusableElements && focusableElements.length > 0) {
        focusableElements[0].focus();
      }

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          e.preventDefault();
          setMobileMenuOpen(false);
          hamburgerRef.current?.focus();
        }
      };

      window.addEventListener('keydown', handleKeyDown);
      return () => {
        window.removeEventListener('keydown', handleKeyDown);
        document.body.style.overflow = '';
      };
    }
  }, [mobileMenuOpen]);

  const navLinks = [
    { href: '/architecture', label: 'Architecture', active: currentPath === '/architecture' },
    { href: '/#narrative', label: 'TCC Narrative', active: false },
    { href: '/#guarantees', label: 'Guarantees', active: false },
    { href: '/#failure-recovery', label: 'Failure Recovery', active: false },
    { href: '/security', label: 'Security', active: currentPath === '/security' },
  ];

  return (
    <header
      className="sticky top-3 z-50"
      style={{
        position: 'sticky',
        top: '0.75rem',
        zIndex: 50,
        padding: '0 1rem',
        maxWidth: '1240px',
        margin: '0 auto',
        pointerEvents: 'none',
      }}
    >
      <div
        className={`glass-nav ${isScrolled ? 'nav-compressed' : ''}`}
        style={{
          pointerEvents: 'auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: isScrolled ? '0.625rem 1.25rem' : '0.875rem 1.5rem',
          borderRadius: isScrolled ? 'var(--radius-pill, 9999px)' : 'var(--radius-xl, 28px)',
          background: isScrolled ? 'rgba(255, 255, 255, 0.88)' : 'rgba(255, 255, 255, 0.75)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.65)',
          boxShadow: isScrolled
            ? '0 16px 36px -6px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(255, 255, 255, 0.8) inset'
            : '0 8px 24px -4px rgba(15, 23, 42, 0.04), 0 0 0 1px rgba(255, 255, 255, 0.6) inset',
          transition: 'all 0.28s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Brand Wordmark with Rounded Badge */}
        <Link
          href="/"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.625rem',
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
              lineHeight: 1,
            }}
          >
            LedgerGuard
          </span>
          <span
            style={{
              fontSize: '0.6875rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--accent-cobalt)',
              background: 'rgba(29, 78, 216, 0.08)',
              padding: '0.2rem 0.55rem',
              borderRadius: 'var(--radius-pill, 9999px)',
              border: '1px solid rgba(29, 78, 216, 0.15)',
            }}
          >
            TCC Triad
          </span>
        </Link>

        {/* Desktop Navigation Links */}
        <nav
          className="hidden md:flex"
          aria-label="Main Navigation"
          style={{
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              style={{
                fontSize: '0.8125rem',
                fontWeight: link.active ? 600 : 500,
                color: link.active ? 'var(--accent-cobalt)' : 'var(--text-ink-secondary)',
                textDecoration: 'none',
                padding: '0.4rem 0.75rem',
                borderRadius: 'var(--radius-pill, 9999px)',
                background: link.active ? 'rgba(29, 78, 216, 0.08)' : 'transparent',
                transition: 'all 0.18s ease',
              }}
            >
              {link.label}
            </Link>
          ))}
          <a
            href="https://github.com/simply-mihir/LedgerGuard"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontSize: '0.8125rem',
              fontWeight: 500,
              color: 'var(--text-ink-secondary)',
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              padding: '0.4rem 0.75rem',
              borderRadius: 'var(--radius-pill, 9999px)',
              transition: 'all 0.18s ease',
            }}
          >
            GitHub
            <span style={{ fontSize: '0.75rem', opacity: 0.6 }}>↗</span>
          </a>
        </nav>

        {/* Action Button & Mobile Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <Link
            href="/console"
            className="btn-editorial btn-primary"
            style={{
              fontSize: '0.8125rem',
              padding: '0.45rem 0.95rem',
              borderRadius: 'var(--radius-pill, 9999px)',
              gap: '0.4rem',
            }}
          >
            <span>Operator Console</span>
            <span style={{ fontSize: '0.75rem' }}>→</span>
          </Link>

          {/* Mobile hamburger button */}
          <button
            ref={hamburgerRef}
            type="button"
            className="md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
            aria-expanded={mobileMenuOpen}
            style={{
              background: 'rgba(255, 255, 255, 0.50)',
              border: '1px solid rgba(226, 232, 240, 0.8)',
              borderRadius: 'var(--radius-control, 14px)',
              padding: '0.5rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-ink)',
              transition: 'all 0.18s ease',
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

      {/* Mobile Frosted Drawer Overlay */}
      {mobileMenuOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Mobile Navigation Drawer"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 100,
            pointerEvents: 'auto',
          }}
        >
          {/* Backdrop */}
          <div
            onClick={() => setMobileMenuOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(15, 23, 42, 0.40)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
            }}
          />

          {/* Frosted Rounded Drawer Sheet */}
          <div
            ref={mobileDrawerRef}
            style={{
              position: 'absolute',
              top: '1rem',
              left: '1rem',
              right: '1rem',
              background: 'rgba(255, 255, 255, 0.95)',
              backdropFilter: 'blur(32px)',
              WebkitBackdropFilter: 'blur(32px)',
              border: '1px solid rgba(255, 255, 255, 0.70)',
              borderRadius: 'var(--radius-primary, 28px)',
              boxShadow: '0 24px 60px -12px rgba(15, 23, 42, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.9) inset',
              padding: '1.75rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              animation: 'fade-in 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingBottom: '1rem',
                borderBottom: '1px solid rgba(226, 232, 240, 0.8)',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '1.25rem',
                  fontWeight: 700,
                  color: 'var(--text-ink)',
                }}
              >
                LedgerGuard
              </span>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Close navigation menu"
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  border: '1px solid var(--border-stone)',
                  background: 'rgba(241, 245, 249, 0.8)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  color: 'var(--text-ink-secondary)',
                }}
              >
                ✕
              </button>
            </div>

            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                style={{
                  fontSize: '1rem',
                  fontWeight: link.active ? 600 : 500,
                  color: link.active ? 'var(--accent-cobalt)' : 'var(--text-ink)',
                  textDecoration: 'none',
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-control, 14px)',
                  background: link.active ? 'rgba(29, 78, 216, 0.08)' : 'transparent',
                }}
              >
                {link.label}
              </Link>
            ))}

            <a
              href="https://github.com/simply-mihir/LedgerGuard"
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setMobileMenuOpen(false)}
              style={{
                fontSize: '1rem',
                fontWeight: 500,
                color: 'var(--text-ink-secondary)',
                textDecoration: 'none',
                padding: '0.75rem 1rem',
              }}
            >
              GitHub Repository ↗
            </a>

            <div style={{ marginTop: '0.75rem', paddingTop: '1rem', borderTop: '1px solid rgba(226, 232, 240, 0.8)' }}>
              <Link
                href="/console"
                onClick={() => setMobileMenuOpen(false)}
                className="btn-editorial btn-primary"
                style={{
                  width: '100%',
                  borderRadius: 'var(--radius-control, 14px)',
                  justifyContent: 'center',
                }}
              >
                <span>Open Operator Console</span>
                <span>→</span>
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
