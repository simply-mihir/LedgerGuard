import React from 'react';

export function AccountingGuaranteeSection() {
  const invariants = [
    {
      rule: 'RULE 01',
      badge: 'Append-Only',
      title: 'Immutable Double-Entry Postings',
      description:
        'The journal_entries table rejects direct UPDATE and DELETE commands via PostgreSQL mutation triggers. Financial corrections require explicit reversing journals with distinct correlation identifiers.',
      code: 'REVOKE UPDATE, DELETE ON journal_entries FROM PUBLIC;',
    },
    {
      rule: 'RULE 02',
      badge: 'Exact Arithmetic',
      title: 'Integer Minor Units (Paise)',
      description:
        'Zero floating-point numbers in financial code paths. All balances and transaction movements are stored as 64-bit integers (BIGINT paise), eliminating IEEE 754 precision leakage.',
      code: 'amount_minor BIGINT NOT NULL CHECK (amount_minor > 0)',
    },
    {
      rule: 'RULE 03',
      badge: 'Trial Balance',
      title: 'Total Debits = Total Credits',
      description:
        'Every posting consists of paired debit and credit lines that balance to zero net change per currency. Single-sided postings or unverified account updates are rejected atomically.',
      code: 'SUM(debit_paise) - SUM(credit_paise) = 0',
    },
  ];

  return (
    <section
      id="guarantees"
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
          <span>Accounting Invariants</span>
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
          Mathematical guarantees enforced at the PostgreSQL engine level.
        </h2>
        <p
          style={{
            fontSize: '1.125rem',
            color: 'var(--text-ink-secondary)',
            lineHeight: 1.65,
          }}
        >
          Financial ledgers cannot rely on application-level discipline alone. LedgerGuard enforces double-entry
          conservation, integer arithmetic, and immutability directly through database schemas and transactional boundaries.
        </p>
      </div>

      {/* 3 Core Invariants Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '2rem',
        }}
      >
        {invariants.map((item, index) => (
          <div
            key={index}
            className="glass-supporting"
            style={{
              borderRadius: 'var(--radius-primary, 28px)',
              padding: '2.25rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1.25rem',
              background: 'rgba(255, 255, 255, 0.78)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.75)',
              boxShadow: '0 20px 48px -12px rgba(15, 23, 42, 0.06), 0 0 0 1px rgba(255, 255, 255, 0.8) inset',
              transition: 'transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.22s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  color: 'var(--accent-cobalt)',
                }}
              >
                {item.rule}
              </span>
              <span
                style={{
                  fontSize: '0.6875rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  padding: '0.25rem 0.65rem',
                  borderRadius: 'var(--radius-pill, 9999px)',
                  backgroundColor: 'rgba(5, 150, 105, 0.12)',
                  color: 'var(--status-success)',
                  border: '1px solid rgba(5, 150, 105, 0.25)',
                }}
              >
                {item.badge}
              </span>
            </div>

            <h3
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.4rem',
                fontWeight: 700,
                color: 'var(--text-ink)',
                lineHeight: 1.25,
              }}
            >
              {item.title}
            </h3>

            <p style={{ fontSize: '0.9375rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65 }}>
              {item.description}
            </p>

            <div
              className="font-mono"
              style={{
                fontSize: '0.75rem',
                backgroundColor: 'rgba(15, 23, 42, 0.04)',
                border: '1px solid rgba(226, 232, 240, 0.9)',
                padding: '0.875rem 1rem',
                borderRadius: 'var(--radius-control, 14px)',
                color: 'var(--text-ink)',
                marginTop: 'auto',
              }}
            >
              {item.code}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
