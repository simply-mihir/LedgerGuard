import React from 'react';
import Link from 'next/link';

export function ConsolePreviewSection() {
  return (
    <section
      id="console-preview"
      style={{
        padding: '5rem 1.5rem',
        backgroundColor: 'var(--bg-stone-subtle)',
        borderTop: '1px solid var(--border-stone)',
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
            Operator Workspace Preview
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
            Institutional control plane for distributed state inspection.
          </h2>
          <p
            style={{
              fontSize: '1.0625rem',
              color: 'var(--text-ink-secondary)',
              lineHeight: 1.65,
            }}
          >
            The operator console allows authenticated engineers to inspect account journal statements,
            track real Try-Confirm-Cancel transfer timelines, execute stopped-and-drained reconciliation audits,
            and trigger controlled crash scenarios in non-production environments.
          </p>
        </div>

        {/* Live-Feel Preview Frame (Editorial Hybrid Option C) */}
        <div
          className="dark-operational-workspace"
          style={{
            padding: '2rem',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-operational)',
            marginBottom: '2.5rem',
          }}
        >
          {/* Top Bar of Console Mock */}
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '1.125rem',
                  fontWeight: 700,
                  color: '#FFFFFF',
                }}
              >
                LedgerGuard
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-operational-muted)' }}>/</span>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent-cobalt-light)' }}>
                System Overview
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <span
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
                ● 3/3 NODES REACHABLE
              </span>
            </div>
          </div>

          {/* 3 Metric Summary Panels */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '1rem',
              marginBottom: '1.5rem',
            }}
          >
            <div className="dark-operational-panel" style={{ padding: '1.25rem' }}>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)', marginBottom: '0.25rem' }}>
                CLEARING CONSERVATION INVARIANT
              </div>
              <div className="font-mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#FFFFFF' }}>
                Σ ΔL = ₹0.00
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--status-success-dark)', marginTop: '0.25rem' }}>
                Balanced Inter-Ledger Clearing
              </div>
            </div>

            <div className="dark-operational-panel" style={{ padding: '1.25rem' }}>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)', marginBottom: '0.25rem' }}>
                TCC SETTLED TRANSFERS
              </div>
              <div className="font-mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#FFFFFF' }}>
                45 Settled
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-operational-secondary)', marginTop: '0.25rem' }}>
                0 Failed • 0 Unsettled Residuals
              </div>
            </div>

            <div className="dark-operational-panel" style={{ padding: '1.25rem' }}>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)', marginBottom: '0.25rem' }}>
                PENDING RECOVERY WORK
              </div>
              <div className="font-mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#FFFFFF' }}>
                0 Pending
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-operational-muted)', marginTop: '0.25rem' }}>
                Autonomous Worker Idle
              </div>
            </div>
          </div>

          {/* In-Frame CTA Strip */}
          <div
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid var(--border-operational)',
              borderRadius: 'var(--radius-xs)',
              padding: '1rem 1.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '1rem',
            }}
          >
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-operational-secondary)' }}>
              Operator access is protected via Argon2id authentication and time-based one-time passwords (TOTP).
            </div>
            <Link
              href="/console"
              className="btn-editorial btn-primary"
              style={{ fontSize: '0.8125rem', padding: '0.5rem 1rem' }}
            >
              Enter Console Workspace →
            </Link>
          </div>
        </div>

        {/* Action Button Bar */}
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <Link href="/console" className="btn-editorial btn-primary">
            Launch Operator Console
          </Link>
          <a
            href="https://github.com/simply-mihir/LedgerGuard"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-editorial btn-secondary"
          >
            Inspect Repository Source ↗
          </a>
        </div>
      </div>
    </section>
  );
}
