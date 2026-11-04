import React from 'react';

export function VerificationSection() {
  const checks = [
    { label: 'Pytest Test Suite', value: '56 Passed', detail: 'Zero warnings; strict error mode' },
    { label: 'Mypy Type Checking', value: '27 Files Verified', detail: 'Zero static type violations' },
    { label: 'Ruff Linter', value: 'Clean Pass', detail: 'Zero code style or syntax defects' },
    { label: 'Python Dependency Audit', value: '0 Vulnerabilities', detail: 'Verified via pip-audit' },
    { label: 'Frontend Test Runner', value: 'Node 20 Compatible', detail: '11 backend events mapped & tested' },
    { label: 'Crash Recovery Demo', value: '8/8 Stages Pass', detail: '100% forward recovery verified' },
  ];

  return (
    <section
      id="verification"
      style={{
        padding: '5rem 1.5rem',
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
          Engineering Rigor
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
          Verified from source code, deterministic tests, and CI automation.
        </h2>
        <p
          style={{
            fontSize: '1.0625rem',
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
            style={{
              backgroundColor: 'var(--bg-paper)',
              border: '1px solid var(--border-stone)',
              borderRadius: 'var(--radius-sm)',
              padding: '1.5rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-ink-muted)' }}>
                {c.label}
              </span>
              <span style={{ color: 'var(--status-success)', fontSize: '0.75rem', fontWeight: 700 }}>
                ✓ PASS
              </span>
            </div>
            <div
              className="font-mono"
              style={{
                fontSize: '1.25rem',
                fontWeight: 700,
                color: 'var(--text-ink)',
                marginBottom: '0.25rem',
              }}
            >
              {c.value}
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)' }}>
              {c.detail}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
