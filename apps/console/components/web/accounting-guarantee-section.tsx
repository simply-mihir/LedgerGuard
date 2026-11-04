import React from 'react';

export function AccountingGuaranteeSection() {
  return (
    <section
      id="guarantees"
      style={{
        padding: '5rem 1.5rem',
        backgroundColor: 'var(--bg-stone-subtle)',
        borderTop: '1px solid var(--border-stone)',
        borderBottom: '1px solid var(--border-stone)',
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
            Accounting Invariants
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
            Mathematical guarantees enforced at the PostgreSQL engine level.
          </h2>
          <p
            style={{
              fontSize: '1.0625rem',
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
          {/* Invariant 1: Immutable Postings */}
          <div
            style={{
              backgroundColor: 'var(--bg-paper)',
              border: '1px solid var(--border-stone)',
              borderRadius: 'var(--radius-sm)',
              padding: '2rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
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
                RULE 01
              </span>
              <span
                style={{
                  fontSize: '0.6875rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  padding: '0.2rem 0.5rem',
                  borderRadius: 'var(--radius-xs)',
                  backgroundColor: 'var(--status-success-bg)',
                  color: 'var(--status-success)',
                  border: '1px solid var(--status-success-border)',
                }}
              >
                Append-Only
              </span>
            </div>
            <h3
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.35rem',
                fontWeight: 700,
                color: 'var(--text-ink)',
              }}
            >
              Immutable Double-Entry Postings
            </h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.6 }}>
              The <code className="font-mono">journal_entries</code> table rejects direct <code className="font-mono">UPDATE</code> and <code className="font-mono">DELETE</code> commands.
              Financial corrections require explicit reversing journals with distinct correlation identifiers.
            </p>
            <div
              className="font-mono"
              style={{
                fontSize: '0.75rem',
                backgroundColor: 'var(--bg-stone)',
                border: '1px solid var(--border-stone-subtle)',
                padding: '0.875rem',
                borderRadius: 'var(--radius-xs)',
                color: 'var(--text-ink)',
                marginTop: 'auto',
              }}
            >
              REVOKE UPDATE, DELETE ON journal_entries FROM PUBLIC;
            </div>
          </div>

          {/* Invariant 2: Integer Paise Representation */}
          <div
            style={{
              backgroundColor: 'var(--bg-paper)',
              border: '1px solid var(--border-stone)',
              borderRadius: 'var(--radius-sm)',
              padding: '2rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
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
                RULE 02
              </span>
              <span
                style={{
                  fontSize: '0.6875rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  padding: '0.2rem 0.5rem',
                  borderRadius: 'var(--radius-xs)',
                  backgroundColor: 'var(--status-success-bg)',
                  color: 'var(--status-success)',
                  border: '1px solid var(--status-success-border)',
                }}
              >
                Exact Arithmetic
              </span>
            </div>
            <h3
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.35rem',
                fontWeight: 700,
                color: 'var(--text-ink)',
              }}
            >
              Integer Minor Units (Paise)
            </h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.6 }}>
              Zero floating-point numbers in financial code paths. All balances and transaction movements are stored as 64-bit integers (<code className="font-mono">BIGINT</code> paise), eliminating IEEE 754 precision leakage.
            </p>
            <div
              className="font-mono"
              style={{
                fontSize: '0.75rem',
                backgroundColor: 'var(--bg-stone)',
                border: '1px solid var(--border-stone-subtle)',
                padding: '0.875rem',
                borderRadius: 'var(--radius-xs)',
                color: 'var(--text-ink)',
                marginTop: 'auto',
              }}
            >
              amount_minor BIGINT NOT NULL CHECK (amount_minor &gt; 0)
            </div>
          </div>

          {/* Invariant 3: Balanced Postings */}
          <div
            style={{
              backgroundColor: 'var(--bg-paper)',
              border: '1px solid var(--border-stone)',
              borderRadius: 'var(--radius-sm)',
              padding: '2rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
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
                RULE 03
              </span>
              <span
                style={{
                  fontSize: '0.6875rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  padding: '0.2rem 0.5rem',
                  borderRadius: 'var(--radius-xs)',
                  backgroundColor: 'var(--status-success-bg)',
                  color: 'var(--status-success)',
                  border: '1px solid var(--status-success-border)',
                }}
              >
                Trial Balance
              </span>
            </div>
            <h3
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.35rem',
                fontWeight: 700,
                color: 'var(--text-ink)',
              }}
            >
              Total Debits = Total Credits
            </h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-ink-secondary)', lineHeight: 1.6 }}>
              Every posting consists of paired debit and credit lines that balance to zero net change per currency. Single-sided postings or unverified account updates are rejected atomically.
            </p>
            <div
              className="font-mono"
              style={{
                fontSize: '0.75rem',
                backgroundColor: 'var(--bg-stone)',
                border: '1px solid var(--border-stone-subtle)',
                padding: '0.875rem',
                borderRadius: 'var(--radius-xs)',
                color: 'var(--text-ink)',
                marginTop: 'auto',
              }}
            >
              SUM(debit_paise) - SUM(credit_paise) = 0
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
