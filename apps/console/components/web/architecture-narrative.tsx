'use client';

import React, { useState, useEffect, useRef } from 'react';

interface Stage {
  number: number;
  stageName: string;
  title: string;
  description: string;
  coordinatorStatus: string;
  coordinatorDetail: string;
  ledger1Status: string;
  ledger1Detail: string;
  ledger2Status: string;
  ledger2Detail: string;
  clearingFormula: string;
  activeEvent: string;
  isDurableBoundary?: boolean;
}

const NARRATIVE_STAGES: Stage[] = [
  {
    number: 1,
    stageName: 'Stage 1 — Immutable Local Posting',
    title: 'Atomic Double-Entry Isolation',
    description:
      'Each participant ledger operates as an autonomous PostgreSQL 17 failure domain. Journals enforce immutable double-entry constraints where debits equal credits in integer paise. No distributed locks cross database boundaries.',
    coordinatorStatus: 'STANDBY',
    coordinatorDetail: 'Awaiting client transfer request; zero locks held',
    ledger1Status: 'ACTIVE',
    ledger1Detail: 'Alice posted balance: ₹1,000.00 • Active holds: ₹0.00',
    ledger2Status: 'ACTIVE',
    ledger2Detail: 'Bob posted balance: ₹0.00 • Active holds: ₹0.00',
    clearingFormula: 'Σ ΔL = ₹0.00 (Zero inter-ledger movement)',
    activeEvent: 'LOCAL_JOURNAL_POSTED',
  },
  {
    number: 2,
    stageName: 'Stage 2 — Source Reservation',
    title: 'Balance Hold & Double-Spend Prevention',
    description:
      'The coordinator dispatches Try commands. Ledger 1 reserves ₹300.00 into an isolated account hold under sorted row lock, preventing double-spending without freezing Alice’s entire wallet.',
    coordinatorStatus: 'PREPARING',
    coordinatorDetail: 'Dispatched source_prepare; timeout watchdog set',
    ledger1Status: 'HELD',
    ledger1Detail: '₹300.00 reserved in account_holds; Available: ₹700.00',
    ledger2Status: 'STANDBY',
    ledger2Detail: 'Awaiting destination prepare payload',
    clearingFormula: 'Σ ΔL = ₹0.00 (Funds reserved, not yet moved)',
    activeEvent: 'PHASE_PREPARE_STARTED',
  },
  {
    number: 3,
    stageName: 'Stage 3 — Destination Preparation',
    title: 'Intent Registration & Viability Check',
    description:
      'Ledger 2 validates Bob’s destination account status, registers incoming intent into its command inbox, and confirms viability. If Bob’s account was frozen or closed, cancellation triggers cleanly.',
    coordinatorStatus: 'PREPARING',
    coordinatorDetail: 'Received affirmative prepare responses from both ledgers',
    ledger1Status: 'HELD',
    ledger1Detail: 'Hold maintained; expires in 60s if unconfirmed',
    ledger2Status: 'INTENT_ACCEPTED',
    ledger2Detail: 'Destination account verified active; intent logged',
    clearingFormula: 'Σ ΔL = ₹0.00 (Two-phase reservation intact)',
    activeEvent: 'INTENT_ACCEPTED',
  },
  {
    number: 4,
    stageName: 'Stage 4 — Durable Decision Boundary',
    title: 'The Irreversible Point of No Return',
    description:
      'When both participants accept, coordinator atomically records a COMMIT decision in transfer_decisions under row lock. Once durably committed to disk, the transfer CANNOT be rolled back or cancelled. Even if the coordinator crashes immediately, recovery MUST drive forward.',
    coordinatorStatus: 'DECISION: COMMIT',
    coordinatorDetail: 'Durably committed to disk; forward recovery guaranteed',
    ledger1Status: 'HELD',
    ledger1Detail: 'Hold preserved across coordinator crash outage',
    ledger2Status: 'INTENT_ACCEPTED',
    ledger2Detail: 'Awaiting phase 2 confirmation command',
    clearingFormula: 'Σ ΔL = ₹0.00 (Committed pending settlement)',
    activeEvent: 'DECISION_MADE & DECISION_COMMITTED',
    isDurableBoundary: true,
  },
  {
    number: 5,
    stageName: 'Stage 5 — Confirmation or Forward Recovery',
    title: 'Asynchronous Settlement & Outbox Replay',
    description:
      'Autonomous workers discover committed transfers via the transactional outbox. Ledger 1 converts the hold into a permanent debit; Ledger 2 posts a permanent credit to Bob. Crashes trigger idempotent replay.',
    coordinatorStatus: 'COMMITTING → SETTLED',
    coordinatorDetail: 'Both participant confirmations acknowledged',
    ledger1Status: 'SETTLED',
    ledger1Detail: 'Hold released; permanent debit ₹300.00 posted',
    ledger2Status: 'SETTLED',
    ledger2Detail: 'Permanent credit ₹300.00 posted to Bob',
    clearingFormula: 'L1: -₹300.00 • L2: +₹300.00 • Net: ₹0.00',
    activeEvent: 'SOURCE_CONFIRMED & DESTINATION_CONFIRMED',
  },
  {
    number: 6,
    stageName: 'Stage 6 — Cross-Ledger Reconciliation',
    title: 'Net Clearing Invariant Equivalence',
    description:
      'On-demand reconciliation inspects all three databases. It verifies trial balance equality within each ledger and proves that inter-ledger clearing balances sum to exactly zero paise across the entire cluster.',
    coordinatorStatus: 'AUDIT: PASS',
    coordinatorDetail: '0 discrepancies observed across 3 databases',
    ledger1Status: 'RECONCILED',
    ledger1Detail: 'Alice: ₹700.00 • Clearing A/C: -₹300.00',
    ledger2Status: 'RECONCILED',
    ledger2Detail: 'Bob: ₹300.00 • Clearing A/C: +₹300.00',
    clearingFormula: 'Σ ΔL = (-30000 + 30000) = ₹0.00 PAIRWISE CONSERVED',
    activeEvent: 'TRANSFER_SETTLED',
  },
];

export function ArchitectureNarrative() {
  const [activeStep, setActiveStep] = useState(1);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mediaQuery.matches);

    const handleChange = (e: MediaQueryListEvent) => {
      setPrefersReducedMotion(e.matches);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion) return;

    let ticking = false;
    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          if (!scrollContainerRef.current) {
            ticking = false;
            return;
          }
          const rect = scrollContainerRef.current.getBoundingClientRect();
          const totalScrollable = rect.height - window.innerHeight;
          if (totalScrollable <= 0) {
            ticking = false;
            return;
          }

          // Progress from 0 to 1 through the container
          const rawProgress = -rect.top / totalScrollable;
          const clamped = Math.max(0, Math.min(1, rawProgress));
          const stepIndex = Math.min(
            NARRATIVE_STAGES.length,
            Math.max(1, Math.floor(clamped * NARRATIVE_STAGES.length) + 1)
          );

          setActiveStep(stepIndex);
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, [prefersReducedMotion]);

  const currentStage = NARRATIVE_STAGES[activeStep - 1];

  return (
    <section id="narrative" aria-label="TCC Architecture Scroll Narrative">
      {/* Section Header */}
      <div
        style={{
          maxWidth: '1240px',
          margin: '0 auto',
          padding: '6rem 1.5rem 2.5rem',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.75rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            color: 'var(--accent-cobalt)',
            background: 'rgba(29, 78, 216, 0.08)',
            padding: '0.35rem 0.85rem',
            borderRadius: 'var(--radius-pill, 9999px)',
            border: '1px solid rgba(29, 78, 216, 0.18)',
            marginBottom: '1.25rem',
          }}
        >
          <span>●</span>
          <span>Apple-Style Architectural Narrative</span>
        </div>

        <h2
          style={{
            fontFamily: 'var(--font-serif)',
            fontSize: 'clamp(2rem, 4vw, 3.25rem)',
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: '-0.02em',
            color: 'var(--text-ink)',
            marginBottom: '1rem',
          }}
        >
          The Six-Stage Distributed Transfer Protocol
        </h2>

        <p
          style={{
            fontSize: '1.125rem',
            color: 'var(--text-ink-secondary)',
            maxWidth: '680px',
            margin: '0 auto',
            lineHeight: 1.6,
          }}
        >
          Follow the lifecycle of an autonomous Try-Confirm-Cancel transaction across three isolated PostgreSQL 17
          storage engines, from localized isolation to net clearing conservation.
        </p>
      </div>

      {/* Narrative Stage Container: Desktop Sticky Storytelling vs Reduced Motion / Mobile */}
      {prefersReducedMotion ? (
        // Reduced Motion Mode: Immediate static presentation of all 6 stages
        <div
          style={{
            maxWidth: '1240px',
            margin: '0 auto',
            padding: '2rem 1.5rem 6rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '2.5rem',
          }}
        >
          {NARRATIVE_STAGES.map((stage) => (
            <div
              key={stage.number}
              className="glass-supporting"
              style={{
                borderRadius: 'var(--radius-primary, 28px)',
                padding: '2.5rem',
                border: stage.isDurableBoundary
                  ? '2px solid rgba(217, 119, 6, 0.5)'
                  : '1px solid rgba(226, 232, 240, 0.8)',
                background: stage.isDurableBoundary ? 'rgba(254, 243, 199, 0.4)' : 'rgba(255, 255, 255, 0.8)',
              }}
            >
              <div
                style={{
                  display: 'inline-block',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  color: stage.isDurableBoundary ? 'var(--status-warning)' : 'var(--accent-cobalt)',
                  marginBottom: '0.5rem',
                  textTransform: 'uppercase',
                }}
              >
                {stage.stageName}
              </div>
              <h3
                style={{
                  fontSize: '1.5rem',
                  fontWeight: 700,
                  marginBottom: '1rem',
                  color: 'var(--text-ink)',
                }}
              >
                {stage.title}
              </h3>
              <p
                style={{
                  fontSize: '1.0625rem',
                  color: 'var(--text-ink-secondary)',
                  lineHeight: 1.6,
                  marginBottom: '1.5rem',
                }}
              >
                {stage.description}
              </p>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: '1rem',
                  padding: '1.25rem',
                  borderRadius: 'var(--radius-secondary, 20px)',
                  background: 'rgba(11, 15, 25, 0.9)',
                  color: '#F1F5F9',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Coordinator DB (:5442)</div>
                  <div style={{ fontWeight: 600, marginTop: '0.25rem' }}>{stage.coordinatorStatus}</div>
                  <div style={{ fontSize: '0.8125rem', color: '#CBD5E1' }}>{stage.coordinatorDetail}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Participant Ledger 1 (:5443)</div>
                  <div style={{ fontWeight: 600, marginTop: '0.25rem' }}>{stage.ledger1Status}</div>
                  <div style={{ fontSize: '0.8125rem', color: '#CBD5E1' }}>{stage.ledger1Detail}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Participant Ledger 2 (:5444)</div>
                  <div style={{ fontWeight: 600, marginTop: '0.25rem' }}>{stage.ledger2Status}</div>
                  <div style={{ fontSize: '0.8125rem', color: '#CBD5E1' }}>{stage.ledger2Detail}</div>
                </div>
              </div>
              <div
                style={{
                  marginTop: '1rem',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  color: stage.isDurableBoundary ? '#B45309' : 'var(--accent-cobalt)',
                }}
              >
                Invariant Guarantee: {stage.clearingFormula}
              </div>
            </div>
          ))}
        </div>
      ) : (
        // Cinematic Scroll Narrative Track
        <div
          ref={scrollContainerRef}
          style={{
            position: 'relative',
            height: '380vh',
            maxWidth: '1240px',
            margin: '0 auto',
            padding: '0 1.5rem',
          }}
        >
          {/* Sticky Pinned Presentation Deck */}
          <div
            style={{
              position: 'sticky',
              top: '5.5rem',
              height: 'calc(100vh - 7rem)',
              maxHeight: '740px',
              display: 'grid',
              gridTemplateColumns: 'minmax(320px, 1fr) minmax(360px, 1.25fr)',
              gap: '2.5rem',
              alignItems: 'stretch',
            }}
            className="md:grid hidden"
          >
            {/* Left Narrative Stepper Panel */}
            <div
              className="glass-supporting"
              style={{
                borderRadius: 'var(--radius-primary, 28px)',
                padding: '2.5rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                background: currentStage.isDurableBoundary
                  ? 'rgba(255, 251, 235, 0.85)'
                  : 'rgba(255, 255, 255, 0.78)',
                border: currentStage.isDurableBoundary
                  ? '1.5px solid rgba(245, 158, 11, 0.4)'
                  : '1px solid rgba(255, 255, 255, 0.65)',
                boxShadow: '0 20px 48px -12px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(255, 255, 255, 0.8) inset',
                transition: 'all 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              <div>
                {/* Step indicator bar */}
                <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '2rem' }}>
                  {NARRATIVE_STAGES.map((s) => (
                    <button
                      key={s.number}
                      type="button"
                      onClick={() => setActiveStep(s.number)}
                      aria-label={`Jump to stage ${s.number}: ${s.title}`}
                      style={{
                        flex: 1,
                        height: '5px',
                        borderRadius: 'var(--radius-pill, 9999px)',
                        background:
                          s.number === activeStep
                            ? s.isDurableBoundary
                              ? 'var(--status-warning)'
                              : 'var(--accent-cobalt)'
                            : s.number < activeStep
                            ? 'rgba(29, 78, 216, 0.35)'
                            : 'rgba(226, 232, 240, 0.8)',
                        border: 'none',
                        cursor: 'pointer',
                        transition: 'all 0.25s ease',
                      }}
                    />
                  ))}
                </div>

                {/* Stage Pill */}
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: currentStage.isDurableBoundary ? '#D97706' : 'var(--accent-cobalt)',
                    background: currentStage.isDurableBoundary
                      ? 'rgba(245, 158, 11, 0.12)'
                      : 'rgba(29, 78, 216, 0.08)',
                    padding: '0.35rem 0.85rem',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    border: `1px solid ${
                      currentStage.isDurableBoundary ? 'rgba(245, 158, 11, 0.3)' : 'rgba(29, 78, 216, 0.2)'
                    }`,
                    marginBottom: '1.25rem',
                  }}
                >
                  <span>●</span>
                  <span>{currentStage.stageName}</span>
                </div>

                {/* Stage Title */}
                <h3
                  style={{
                    fontFamily: 'var(--font-serif)',
                    fontSize: '2rem',
                    fontWeight: 700,
                    lineHeight: 1.2,
                    letterSpacing: '-0.02em',
                    color: 'var(--text-ink)',
                    marginBottom: '1.25rem',
                  }}
                >
                  {currentStage.title}
                </h3>

                {/* Stage Description */}
                <p
                  style={{
                    fontSize: '1.0625rem',
                    color: 'var(--text-ink-secondary)',
                    lineHeight: 1.65,
                    marginBottom: '1.75rem',
                  }}
                >
                  {currentStage.description}
                </p>

                {/* Durable Boundary Prominent Callout */}
                {currentStage.isDurableBoundary && (
                  <div
                    style={{
                      background: 'rgba(245, 158, 11, 0.12)',
                      border: '1px solid rgba(245, 158, 11, 0.35)',
                      borderRadius: 'var(--radius-secondary, 20px)',
                      padding: '1rem 1.25rem',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '0.75rem',
                      marginBottom: '1.5rem',
                    }}
                  >
                    <span style={{ fontSize: '1.25rem' }}>⚠️</span>
                    <div>
                      <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#B45309' }}>
                        DURABLE DECISION BOUNDARY: THE POINT OF NO RETURN
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#92400E', marginTop: '0.2rem', lineHeight: 1.4 }}>
                        Once logged to disk under row lock, this decision is irreversible. Outbox workers recover
                        forward across crashes; funds are never refunded to sender.
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Invariant Footer */}
              <div
                style={{
                  padding: '1rem 1.25rem',
                  borderRadius: 'var(--radius-secondary, 20px)',
                  background: 'rgba(241, 245, 249, 0.7)',
                  border: '1px solid rgba(226, 232, 240, 0.8)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--text-ink-muted)', textTransform: 'uppercase' }}>
                    Active Invariant Verification
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-ink)', marginTop: '0.15rem' }}>
                    {currentStage.clearingFormula}
                  </div>
                </div>
                <div
                  style={{
                    fontSize: '0.6875rem',
                    fontWeight: 700,
                    padding: '0.25rem 0.6rem',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    background: 'rgba(5, 150, 105, 0.12)',
                    color: 'var(--status-success)',
                    border: '1px solid rgba(5, 150, 105, 0.25)',
                  }}
                >
                  CONSERVED
                </div>
              </div>
            </div>

            {/* Right Live Operational Simulation Stage */}
            <div
              className="dark-operational-field"
              style={{
                borderRadius: 'var(--radius-primary, 28px)',
                border: '1px solid var(--border-operational-strong)',
                boxShadow: 'var(--shadow-operational)',
                padding: '2.25rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              {/* Header Telemetry */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                  paddingBottom: '1.25rem',
                  zIndex: 2,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div
                    style={{
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      background: currentStage.isDurableBoundary ? '#F59E0B' : '#10B981',
                      boxShadow: currentStage.isDurableBoundary
                        ? '0 0 12px #F59E0B'
                        : '0 0 12px #10B981',
                    }}
                  />
                  <span style={{ fontSize: '0.8125rem', fontWeight: 700, letterSpacing: '0.04em', color: '#F1F5F9' }}>
                    3-NODE POSTGRESQL 17 CLUSTER
                  </span>
                </div>
                <div
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.75rem',
                    color: '#94A3B8',
                    background: 'rgba(255, 255, 255, 0.05)',
                    padding: '0.25rem 0.6rem',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                  }}
                >
                  EVENT: {currentStage.activeEvent}
                </div>
              </div>

              {/* Triad Topology Visualization */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1.25rem',
                  margin: '1.5rem 0',
                  zIndex: 2,
                }}
              >
                {/* Node 1: Coordinator DB */}
                <div
                  style={{
                    background: 'rgba(14, 20, 34, 0.75)',
                    backdropFilter: 'blur(16px)',
                    border: currentStage.number >= 4
                      ? '1px solid rgba(59, 130, 246, 0.45)'
                      : '1px solid rgba(255, 255, 255, 0.10)',
                    borderRadius: 'var(--radius-secondary, 20px)',
                    padding: '1.25rem 1.5rem',
                    boxShadow: currentStage.number >= 4
                      ? '0 8px 24px rgba(29, 78, 216, 0.25)'
                      : 'none',
                    transition: 'all 0.3s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <span style={{ fontSize: '1.1rem' }}>🏛️</span>
                      <div>
                        <div style={{ fontSize: '0.875rem', fontWeight: 700, color: '#F8FAFC' }}>
                          Coordinator Service & Directory
                        </div>
                        <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: '#94A3B8' }}>
                          Port :5442 • coordinator_db
                        </div>
                      </div>
                    </div>
                    <div
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        padding: '0.2rem 0.6rem',
                        borderRadius: 'var(--radius-pill, 9999px)',
                        background: currentStage.isDurableBoundary
                          ? 'rgba(245, 158, 11, 0.2)'
                          : 'rgba(59, 130, 246, 0.2)',
                        color: currentStage.isDurableBoundary ? '#FCD34D' : '#60A5FA',
                        border: `1px solid ${
                          currentStage.isDurableBoundary
                            ? 'rgba(245, 158, 11, 0.4)'
                            : 'rgba(59, 130, 246, 0.4)'
                        }`,
                      }}
                    >
                      {currentStage.coordinatorStatus}
                    </div>
                  </div>
                  <div
                    style={{
                      marginTop: '0.6rem',
                      fontSize: '0.8125rem',
                      color: '#CBD5E1',
                      borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                      paddingTop: '0.6rem',
                    }}
                  >
                    {currentStage.coordinatorDetail}
                  </div>
                </div>

                {/* Animated Flow Connecting Arrows */}
                <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', padding: '0 2rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#60A5FA', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                    <span>↓ TCC Phase 1 / 2</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#38BDF8', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                    <span>↓ TCC Phase 1 / 2</span>
                  </div>
                </div>

                {/* Bottom Row: Participant Ledgers */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
                  {/* Ledger 1 */}
                  <div
                    style={{
                      background: 'rgba(14, 20, 34, 0.75)',
                      backdropFilter: 'blur(16px)',
                      border: currentStage.number >= 2
                        ? '1px solid rgba(56, 189, 248, 0.4)'
                        : '1px solid rgba(255, 255, 255, 0.10)',
                      borderRadius: 'var(--radius-secondary, 20px)',
                      padding: '1.25rem',
                      transition: 'all 0.3s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                      <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#F8FAFC' }}>
                        Participant Ledger 1
                      </div>
                      <span
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 700,
                          padding: '0.15rem 0.5rem',
                          borderRadius: 'var(--radius-pill, 9999px)',
                          background: currentStage.number === 2 ? 'rgba(245, 158, 11, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                          color: currentStage.number === 2 ? '#FCD34D' : '#34D399',
                        }}
                      >
                        {currentStage.ledger1Status}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: '#94A3B8', marginBottom: '0.5rem' }}>
                      Port :5443 • Alice Wallet
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#E2E8F0', borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: '0.5rem' }}>
                      {currentStage.ledger1Detail}
                    </div>
                  </div>

                  {/* Ledger 2 */}
                  <div
                    style={{
                      background: 'rgba(14, 20, 34, 0.75)',
                      backdropFilter: 'blur(16px)',
                      border: currentStage.number >= 3
                        ? '1px solid rgba(56, 189, 248, 0.4)'
                        : '1px solid rgba(255, 255, 255, 0.10)',
                      borderRadius: 'var(--radius-secondary, 20px)',
                      padding: '1.25rem',
                      transition: 'all 0.3s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                      <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#F8FAFC' }}>
                        Participant Ledger 2
                      </div>
                      <span
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 700,
                          padding: '0.15rem 0.5rem',
                          borderRadius: 'var(--radius-pill, 9999px)',
                          background: 'rgba(56, 189, 248, 0.2)',
                          color: '#38BDF8',
                        }}
                      >
                        {currentStage.ledger2Status}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: '#94A3B8', marginBottom: '0.5rem' }}>
                      Port :5444 • Bob Wallet
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#E2E8F0', borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: '0.5rem' }}>
                      {currentStage.ledger2Detail}
                    </div>
                  </div>
                </div>
              </div>

              {/* Bottom Invariant Calculation Pill */}
              <div
                style={{
                  background: 'rgba(0, 0, 0, 0.45)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 'var(--radius-control, 14px)',
                  padding: '0.875rem 1.25rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  zIndex: 2,
                }}
              >
                <span style={{ fontSize: '0.75rem', color: '#94A3B8', fontFamily: 'var(--font-mono)' }}>
                  Clearing Invariant State:
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.8125rem',
                    fontWeight: 700,
                    color: '#34D399',
                  }}
                >
                  {currentStage.clearingFormula}
                </span>
              </div>
            </div>
          </div>

          {/* Mobile Natural Scrolling Stack */}
          <div className="md:hidden flex flex-col gap-6" style={{ marginTop: '2rem' }}>
            {NARRATIVE_STAGES.map((s) => (
              <div
                key={s.number}
                className="glass-supporting"
                style={{
                  borderRadius: 'var(--radius-primary, 28px)',
                  padding: '1.75rem',
                  border: s.isDurableBoundary
                    ? '1.5px solid rgba(245, 158, 11, 0.4)'
                    : '1px solid rgba(226, 232, 240, 0.8)',
                  background: s.isDurableBoundary ? 'rgba(255, 251, 235, 0.8)' : 'rgba(255, 255, 255, 0.85)',
                }}
              >
                <div
                  style={{
                    fontSize: '0.6875rem',
                    fontWeight: 700,
                    color: s.isDurableBoundary ? '#D97706' : 'var(--accent-cobalt)',
                    textTransform: 'uppercase',
                    marginBottom: '0.35rem',
                  }}
                >
                  {s.stageName}
                </div>
                <h4 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-ink)', marginBottom: '0.75rem' }}>
                  {s.title}
                </h4>
                <p style={{ fontSize: '0.9375rem', color: 'var(--text-ink-secondary)', lineHeight: 1.55, marginBottom: '1rem' }}>
                  {s.description}
                </p>
                <div
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: s.isDurableBoundary ? '#B45309' : 'var(--accent-cobalt)',
                    padding: '0.5rem 0.75rem',
                    borderRadius: 'var(--radius-sm, 10px)',
                    background: 'rgba(0, 0, 0, 0.04)',
                  }}
                >
                  {s.clearingFormula}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
