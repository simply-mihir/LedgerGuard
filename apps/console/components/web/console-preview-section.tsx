import React from 'react';
import Link from 'next/link';

export function ConsolePreviewSection() {
  return (
    <section
      id="console-preview"
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
          <span>Operator Workspace Preview</span>
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
          Institutional control plane for distributed state inspection.
        </h2>
        <p
          style={{
            fontSize: '1.125rem',
            color: 'var(--text-ink-secondary)',
            lineHeight: 1.65,
          }}
        >
          The operator console allows authenticated engineers to inspect account journal statements,
          track real Try-Confirm-Cancel transfer timelines, execute stopped-and-drained reconciliation audits,
          and trigger controlled crash scenarios in non-production environments.
        </p>
      </div>

      {/* Live-Feel Preview Frame (Rounded Operational Glass) */}
      <div
        className="glass-hero-dark"
        style={{
          padding: '2.5rem',
          borderRadius: 'var(--radius-primary, 28px)',
          background: 'rgba(14, 20, 34, 0.78)',
          backdropFilter: 'blur(28px)',
          WebkitBackdropFilter: 'blur(28px)',
          border: '1px solid rgba(56, 189, 248, 0.20)',
          boxShadow: '0 24px 60px -12px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255, 255, 255, 0.12) inset',
          marginBottom: '2.5rem',
        }}
      >
        {/* Top Bar of Console Mock */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            paddingBottom: '1.25rem',
            marginBottom: '1.75rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.1875rem',
                fontWeight: 700,
                color: '#F8FAFC',
              }}
            >
              LedgerGuard
            </span>
            <span style={{ fontSize: '0.75rem', color: '#64748B' }}>/</span>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#60A5FA' }}>
              System Overview
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
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
              ● 3/3 NODES REACHABLE
            </span>
          </div>
        </div>

        {/* 3 Metric Summary Panels */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '1.25rem',
            marginBottom: '1.75rem',
          }}
        >
          <div
            style={{
              background: 'rgba(20, 28, 48, 0.75)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 'var(--radius-secondary, 20px)',
              padding: '1.5rem',
            }}
          >
            <div style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: '#94A3B8', marginBottom: '0.35rem' }}>
              CLEARING CONSERVATION INVARIANT
            </div>
            <div className="font-mono" style={{ fontSize: '1.35rem', fontWeight: 700, color: '#34D399' }}>
              Σ ΔL = ₹0.00
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '0.35rem' }}>
              Balanced Inter-Ledger Clearing
            </div>
          </div>

          <div
            style={{
              background: 'rgba(20, 28, 48, 0.75)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 'var(--radius-secondary, 20px)',
              padding: '1.5rem',
            }}
          >
            <div style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: '#94A3B8', marginBottom: '0.35rem' }}>
              TCC SETTLED TRANSFERS
            </div>
            <div className="font-mono" style={{ fontSize: '1.35rem', fontWeight: 700, color: '#F8FAFC' }}>
              45 Settled
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '0.35rem' }}>
              0 Failed • 0 Unsettled Residuals
            </div>
          </div>

          <div
            style={{
              background: 'rgba(20, 28, 48, 0.75)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 'var(--radius-secondary, 20px)',
              padding: '1.5rem',
            }}
          >
            <div style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: '#94A3B8', marginBottom: '0.35rem' }}>
              PENDING RECOVERY WORK
            </div>
            <div className="font-mono" style={{ fontSize: '1.35rem', fontWeight: 700, color: '#F8FAFC' }}>
              0 Pending
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '0.35rem' }}>
              Autonomous Worker Idle
            </div>
          </div>
        </div>

        {/* In-Frame CTA Strip */}
        <div
          style={{
            backgroundColor: 'rgba(20, 28, 48, 0.60)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 'var(--radius-control, 14px)',
            padding: '1.25rem 1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div style={{ fontSize: '0.8125rem', color: '#94A3B8' }}>
            Operator access is protected via Argon2id authentication and time-based one-time passwords (TOTP).
          </div>
          <Link
            href="/console"
            className="btn-editorial btn-primary"
            style={{ fontSize: '0.8125rem', padding: '0.55rem 1.15rem', borderRadius: 'var(--radius-pill, 9999px)' }}
          >
            Enter Console Workspace →
          </Link>
        </div>
      </div>

      {/* Action Button Bar */}
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <Link href="/console" className="btn-editorial btn-primary" style={{ borderRadius: 'var(--radius-pill, 9999px)' }}>
          Launch Operator Console
        </Link>
        <a
          href="https://github.com/simply-mihir/LedgerGuard"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-editorial btn-secondary"
          style={{ borderRadius: 'var(--radius-pill, 9999px)' }}
        >
          Inspect Repository Source ↗
        </a>
      </div>
    </section>
  );
}
