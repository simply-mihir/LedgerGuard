import React from 'react';

export function VerificationSection() {
  const checks = [
    { label: 'Pytest Test Suite', value: 'Strict Error Mode', detail: 'Automated test suites with all warnings escalated to errors' },
    { label: 'Mypy Type Checking', value: 'Strict Typing', detail: 'Zero static type violations across all source modules' },
    { label: 'Ruff Linter', value: 'Zero Style Defects', detail: 'Codebase style and syntax invariants enforced' },
    { label: 'Dependency Audits', value: 'Continuous CVE Checks', detail: 'Automated pip-audit and npm audit checks in CI' },
    { label: 'Frontend Test Runner', value: 'Node 20 Compatible', detail: 'Authoritative TCC workflow events mapped and tested' },
    { label: 'Crash Recovery Demo', value: 'Deterministic Replay', detail: 'Forward crash recovery and signature verification' },
  ];

  return (
    <section
      id="verification"
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
          <span>Engineering Rigor</span>
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
          Verified from source code, deterministic tests, and CI automation.
        </h2>
        <p
          style={{
            fontSize: '1.125rem',
            color: 'var(--text-ink-secondary)',
            lineHeight: 1.65,
          }}
        >
          Every technical statement in LedgerGuard is backed by automated CI pipelines executing on
          isolated PostgreSQL 17 databases, Python 3.12 services, and Node.js 20 frontends.
        </p>
      </div>

      {/* Metrics Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '1.5rem',
        }}
      >
        {checks.map((c, i) => (
          <div
            key={i}
            className="glass-supporting"
            style={{
              borderRadius: 'var(--radius-secondary, 20px)',
              padding: '1.75rem',
              background: 'rgba(255, 255, 255, 0.78)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.75)',
              boxShadow: '0 12px 32px -8px rgba(15, 23, 42, 0.05), 0 0 0 1px rgba(255, 255, 255, 0.8) inset',
              transition: 'transform 0.18s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-ink-muted)' }}>
                {c.label}
              </span>
              <span
                style={{
                  color: 'var(--status-success)',
                  backgroundColor: 'rgba(5, 150, 105, 0.10)',
                  fontSize: '0.6875rem',
                  fontWeight: 700,
                  padding: '0.2rem 0.55rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  border: '1px solid rgba(5, 150, 105, 0.25)',
                }}
              >
                ✓ PASS
              </span>
            </div>
            <div
              className="font-mono"
              style={{
                fontSize: '1.25rem',
                fontWeight: 700,
                color: 'var(--text-ink)',
                marginBottom: '0.35rem',
                letterSpacing: '-0.02em',
              }}
            >
              {c.value}
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
              {c.detail}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
