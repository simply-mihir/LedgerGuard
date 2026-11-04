'use client';

import React, { useState } from 'react';

interface StageInfo {
  step: number;
  badge: string;
  title: string;
  description: string;
  coordinatorState: string;
  ledger1State: string;
  ledger2State: string;
  clearingDelta: string;
  activeEvent: string;
}

const STAGES: StageInfo[] = [
  {
    step: 1,
    badge: 'Stage 1 — Local ACID Posting',
    title: 'Atomic Double-Entry Isolation',
    description:
      'Each participant ledger operates as an independent PostgreSQL 17 failure domain. Journals enforce immutable double-entry constraints where Total Debits equal Total Credits in integer paise. No distributed locks cross database boundaries.',
    coordinatorState: 'IDLE (Awaiting Transfer Request)',
    ledger1State: 'ACTIVE: Wallet Alice posted balance ₹1,000.00',
    ledger2State: 'ACTIVE: Wallet Bob posted balance ₹0.00',
    clearingDelta: 'Σ ΔL = ₹0.00 (Zero Inter-Ledger Movement)',
    activeEvent: 'LOCAL_JOURNAL_POSTED',
  },
  {
    step: 2,
    badge: 'Stage 2 — TCC Try Phase (Prepare)',
    title: 'Reservation & Viability Invariant',
    description:
      'The coordinator dispatches Try commands. Ledger 1 reserves ₹300.00 into an isolated balance hold, preventing double-spend without freezing the entire account. Ledger 2 validates destination eligibility and accepts incoming intent.',
    coordinatorState: 'STATE: PREPARING (Transfer 7a609dcb...)',
    ledger1State: 'HELD: ₹300.00 reserved in account_holds; Available: ₹700.00',
    ledger2State: 'INTENT_ACCEPTED: Destination account verified viable',
    clearingDelta: 'Σ ΔL = ₹0.00 (Funds not yet transferred)',
    activeEvent: 'PHASE_PREPARE_STARTED',
  },
  {
    step: 3,
    badge: 'Stage 3 — Durable Decision Boundary',
    title: 'The Point of No Return',
    description:
      'When both participants accept, coordinator atomically records a COMMIT decision in transfer_decisions under row lock. Once logged to disk, the transfer CANNOT be cancelled or rolled back. Even if the coordinator crashes immediately, recovery must drive forward.',
    coordinatorState: 'DECISION: COMMIT (Durably committed to disk)',
    ledger1State: 'HELD: Balance hold maintained across outage',
    ledger2State: 'PENDING: Awaiting confirmation command',
    clearingDelta: 'Σ ΔL = ₹0.00 (Committed pending settlement)',
    activeEvent: 'DECISION_MADE & DECISION_COMMITTED',
  },
  {
    step: 4,
    badge: 'Stage 4 — Forward Confirmation Recovery',
    title: 'Asynchronous Settlement Dispatch',
    description:
      'Autonomous worker discovers committed transfer through the transactional outbox. It applies Phase 2 confirmations: Ledger 1 releases the hold and debits Alice; Ledger 2 posts a credit to Bob. Crashes trigger forward replay with idempotent inbox deduplication.',
    coordinatorState: 'STATE: COMMITTING → SETTLED',
    ledger1State: 'SETTLED: Hold released; permanent debit ₹300.00 posted',
    ledger2State: 'SETTLED: Permanent credit ₹300.00 posted to Bob',
    clearingDelta: 'L1: -₹300.00 • L2: +₹300.00 • Net: ₹0.00',
    activeEvent: 'SOURCE_CONFIRMED & DESTINATION_CONFIRMED',
  },
  {
    step: 5,
    badge: 'Stage 5 — Clearing Conservation Audit',
    title: 'Cross-Ledger Invariant Equivalence',
    description:
      'Post-settlement clearing reconciliation verifies that inter-ledger clearing balances sum to exactly zero paise across databases. The engine verifies conservation after settlement rather than locking distributed tables synchronously.',
    coordinatorState: 'AUDIT: PASS (0 discrepancies observed)',
    ledger1State: 'POSTED: ₹700.00 • Clearing A/C: -₹300.00',
    ledger2State: 'POSTED: ₹300.00 • Clearing A/C: +₹300.00',
    clearingDelta: 'Σ ΔL = (-30000 + 30000) = ₹0.00 PAIRWISE CONSERVED',
    activeEvent: 'TRANSFER_SETTLED',
  },
];

export function ArchitectureNarrative() {
  const [activeStep, setActiveStep] = useState(1);
  const currentStage = STAGES[activeStep - 1];

  return (
    <section
      id="architecture-narrative"
      style={{
        padding: '5rem 1.5rem',
        maxWidth: '1280px',
        margin: '0 auto',
      }}
    >
      {/* Section Eyebrow & Heading */}
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
          Operational Architecture
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
          Five-stage Try-Confirm-Cancel lifecycle across independent databases.
        </h2>
        <p
          style={{
            fontSize: '1.0625rem',
            color: 'var(--text-ink-secondary)',
            lineHeight: 1.65,
          }}
        >
          LedgerGuard eliminates classical two-phase commit (2PC) distributed locks. Instead, it coordinates
          balance reservations through durable local transactions, an immutable decision boundary, and
          autonomous forward recovery.
        </p>
      </div>

      {/* Interactive Two-Column Narrative Layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '3rem',
          alignItems: 'start',
        }}
      >
        {/* Left Column: Stage Selector Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {STAGES.map((s) => {
            const isSelected = s.step === activeStep;
            return (
              <button
                key={s.step}
                type="button"
                onClick={() => setActiveStep(s.step)}
                style={{
                  textAlign: 'left',
                  padding: '1.5rem',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: isSelected ? 'var(--bg-paper)' : 'transparent',
                  border: `1px solid ${isSelected ? 'var(--accent-cobalt)' : 'var(--border-stone)'}`,
                  boxShadow: isSelected ? 'var(--shadow-card)' : 'none',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  position: 'relative',
                }}
              >
                {isSelected && (
                  <div
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: 0,
                      bottom: 0,
                      width: '4px',
                      backgroundColor: 'var(--accent-cobalt)',
                      borderRadius: 'var(--radius-sm) 0 0 var(--radius-sm)',
                    }}
                  />
                )}
                <div
                  style={{
                    fontSize: '0.6875rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    color: isSelected ? 'var(--accent-cobalt)' : 'var(--text-ink-muted)',
                    marginBottom: '0.35rem',
                  }}
                >
                  {s.badge}
                </div>
                <div
                  style={{
                    fontFamily: 'var(--font-serif)',
                    fontSize: '1.25rem',
                    fontWeight: 700,
                    color: 'var(--text-ink)',
                    marginBottom: '0.5rem',
                  }}
                >
                  {s.title}
                </div>
                <p
                  style={{
                    fontSize: '0.875rem',
                    color: 'var(--text-ink-secondary)',
                    lineHeight: 1.55,
                  }}
                >
                  {s.description}
                </p>
              </button>
            );
          })}
        </div>

        {/* Right Column: Sticky Dark Operational Topology Stage */}
        <div
          className="sticky-stage-panel dark-operational-workspace"
          style={{
            padding: '2rem',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-operational)',
          }}
        >
          {/* Header Bar */}
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
            <div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)', letterSpacing: '0.06em' }}>
                LIVE RUNTIME TOPOLOGY (STAGE {currentStage.step}/5)
              </div>
              <div style={{ fontSize: '0.9375rem', fontWeight: 600, color: 'var(--text-operational)' }}>
                Three Independently Reachable PostgreSQL Instances
              </div>
            </div>
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.6875rem',
                padding: '0.25rem 0.5rem',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: 'rgba(29, 78, 216, 0.2)',
                color: 'var(--accent-cobalt-light)',
                border: '1px solid rgba(29, 78, 216, 0.4)',
              }}
            >
              {currentStage.activeEvent}
            </div>
          </div>

          {/* Triad Nodes Visualization */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Coordinator Node */}
            <div
              className="dark-operational-panel"
              style={{
                padding: '1.25rem',
                borderLeft: '3px solid var(--accent-cobalt-light)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#FFFFFF' }}>
                  Coordinator Database
                </span>
                <span className="font-mono" style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)' }}>
                  PORT :5442
                </span>
              </div>
              <div
                className="font-mono"
                style={{
                  fontSize: '0.75rem',
                  color: 'var(--text-operational-secondary)',
                  backgroundColor: 'rgba(0, 0, 0, 0.35)',
                  padding: '0.5rem 0.75rem',
                  borderRadius: 'var(--radius-xs)',
                  border: '1px solid var(--border-operational)',
                }}
              >
                {currentStage.coordinatorState}
              </div>
            </div>

            {/* Invariant Transmission Vectors */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '1rem',
                fontSize: '0.75rem',
                color: 'var(--text-operational-muted)',
              }}
            >
              <span>↓ TCC Dispatch</span>
              <span className="font-mono" style={{ color: 'var(--accent-cobalt-light)' }}>
                Transactional Outbox / Inbox
              </span>
              <span>↓ Durable Replay</span>
            </div>

            {/* Participant Ledgers Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '1rem',
              }}
            >
              {/* Participant Ledger 1 */}
              <div
                className="dark-operational-panel"
                style={{
                  padding: '1.25rem',
                  borderTop: '2px solid var(--status-success-dark)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#FFFFFF' }}>
                    Ledger 1 (Source)
                  </span>
                  <span className="font-mono" style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)' }}>
                    :5443
                  </span>
                </div>
                <div
                  className="font-mono"
                  style={{
                    fontSize: '0.6875rem',
                    color: 'var(--text-operational-secondary)',
                    backgroundColor: 'rgba(0, 0, 0, 0.35)',
                    padding: '0.5rem',
                    borderRadius: 'var(--radius-xs)',
                    minHeight: '4.5rem',
                  }}
                >
                  {currentStage.ledger1State}
                </div>
              </div>

              {/* Participant Ledger 2 */}
              <div
                className="dark-operational-panel"
                style={{
                  padding: '1.25rem',
                  borderTop: '2px solid var(--status-success-dark)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#FFFFFF' }}>
                    Ledger 2 (Dest)
                  </span>
                  <span className="font-mono" style={{ fontSize: '0.6875rem', color: 'var(--text-operational-muted)' }}>
                    :5444
                  </span>
                </div>
                <div
                  className="font-mono"
                  style={{
                    fontSize: '0.6875rem',
                    color: 'var(--text-operational-secondary)',
                    backgroundColor: 'rgba(0, 0, 0, 0.35)',
                    padding: '0.5rem',
                    borderRadius: 'var(--radius-xs)',
                    minHeight: '4.5rem',
                  }}
                >
                  {currentStage.ledger2State}
                </div>
              </div>
            </div>

            {/* Clearing Equivalence Monitor */}
            <div
              style={{
                backgroundColor: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                borderRadius: 'var(--radius-xs)',
                padding: '0.75rem 1rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ color: 'var(--status-success-dark)', fontSize: '0.875rem' }}>●</span>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#FFFFFF' }}>
                  Clearing Invariant
                </span>
              </div>
              <div className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--status-success-dark)', fontWeight: 600 }}>
                {currentStage.clearingDelta}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
