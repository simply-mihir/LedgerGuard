import React from 'react';
import Link from 'next/link';
import { SiteHeader } from '../../components/web/site-header';
import { SiteFooter } from '../../components/web/site-footer';

export const metadata = {
  title: 'Architecture Deep Dive — LedgerGuard',
  description: 'Detailed technical specification of LedgerGuard Try-Confirm-Cancel protocol, outbox processing, and multi-database topology.',
};

export default function ArchitecturePage() {
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <SiteHeader currentPath="/architecture" />

      <main id="main-content" style={{ padding: '4rem 1.5rem 6rem', maxWidth: '1000px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '3.5rem' }}>
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
            System Specification
          </div>
          <h1
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: 'clamp(2.25rem, 4.5vw, 3.5rem)',
              fontWeight: 700,
              lineHeight: 1.1,
              letterSpacing: '-0.03em',
              color: 'var(--text-ink)',
              marginBottom: '1.25rem',
            }}
          >
            Distributed Ledger Architecture & TCC Coordination
          </h1>
          <p
            style={{
              fontSize: '1.1875rem',
              color: 'var(--text-ink-secondary)',
              lineHeight: 1.6,
            }}
          >
            An in-depth examination of LedgerGuard’s multi-database topology, reservation lifecycles, transactional outbox
            guarantees, and clearing conservation theorems.
          </p>
        </div>

        {/* Section 1: The Three Database Failure Domains */}
        <section style={{ marginBottom: '4rem' }}>
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.75rem',
              fontWeight: 700,
              color: 'var(--text-ink)',
              marginBottom: '1rem',
            }}
          >
            1. Three Autonomous PostgreSQL 17 Databases
          </h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65, marginBottom: '1.5rem' }}>
            LedgerGuard avoids the fragility of shared distributed tables. The system architecture consists of three
            independently reachable PostgreSQL instances running on distinct network ports:
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1.25rem', marginBottom: '2rem' }}>
            <div style={{ padding: '1.5rem', backgroundColor: 'var(--bg-paper)', border: '1px solid var(--border-stone)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--accent-cobalt)', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                COORDINATOR DB (:5442)
              </div>
              <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-ink)', marginBottom: '0.5rem' }}>
                Orchestration & State
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
                Customer registry, account directory routing, idempotency store, transfer state machine, durable decisions, and workflow audit log.
              </div>
            </div>

            <div style={{ padding: '1.5rem', backgroundColor: 'var(--bg-paper)', border: '1px solid var(--border-stone)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--status-success)', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                LEDGER 1 DB (:5443)
              </div>
              <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-ink)', marginBottom: '0.5rem' }}>
                Participant Partition 1
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
                Alice accounts, local immutable double-entry journal lines, balance hold reservations, inbox command deduplication, and Ledger 1 clearing account.
              </div>
            </div>

            <div style={{ padding: '1.5rem', backgroundColor: 'var(--bg-paper)', border: '1px solid var(--border-stone)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--status-success)', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                LEDGER 2 DB (:5444)
              </div>
              <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-ink)', marginBottom: '0.5rem' }}>
                Participant Partition 2
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-ink-secondary)', lineHeight: 1.5 }}>
                Bob accounts, local immutable double-entry journal lines, intent verification, inbox command deduplication, and Ledger 2 clearing account.
              </div>
            </div>
          </div>
        </section>

        {/* Section 2: Why TCC Instead of Classical 2PC/XA */}
        <section style={{ marginBottom: '4rem' }}>
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.75rem',
              fontWeight: 700,
              color: 'var(--text-ink)',
              marginBottom: '1rem',
            }}
          >
            2. Contrast: Application-Level TCC vs Classical Distributed 2PC
          </h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65, marginBottom: '1.5rem' }}>
            Classical distributed two-phase commit (XA/2PC) relies on holding low-level database locks open across network boundaries during <code className="font-mono">PREPARE TRANSACTION</code>.
            If a coordinator crashes while locks are held, participant databases stall and transaction tables lock up entirely.
          </p>

          <div
            style={{
              backgroundColor: 'var(--bg-paper)',
              border: '1px solid var(--border-stone)',
              borderRadius: 'var(--radius-sm)',
              overflow: 'hidden',
              marginBottom: '1.5rem',
            }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--bg-stone-subtle)', borderBottom: '1px solid var(--border-stone)', textAlign: 'left' }}>
                  <th style={{ padding: '0.875rem 1rem', fontWeight: 700, color: 'var(--text-ink)' }}>Dimension</th>
                  <th style={{ padding: '0.875rem 1rem', fontWeight: 700, color: 'var(--status-critical)' }}>Classical Distributed 2PC / XA</th>
                  <th style={{ padding: '0.875rem 1rem', fontWeight: 700, color: 'var(--accent-cobalt)' }}>LedgerGuard TCC Protocol</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid var(--border-stone-subtle)' }}>
                  <td style={{ padding: '0.875rem 1rem', fontWeight: 600 }}>Locking Strategy</td>
                  <td style={{ padding: '0.875rem 1rem', color: 'var(--text-ink-secondary)' }}>Distributed database row/table locks held across the network.</td>
                  <td style={{ padding: '0.875rem 1rem', color: 'var(--text-ink)' }}>Local business holds. Available balance adjusted; no table lock held.</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-stone-subtle)' }}>
                  <td style={{ padding: '0.875rem 1rem', fontWeight: 600 }}>Coordinator Crash Impact</td>
                  <td style={{ padding: '0.875rem 1rem', color: 'var(--text-ink-secondary)' }}>Participants block indefinitely waiting for heuristic recovery.</td>
                  <td style={{ padding: '0.875rem 1rem', color: 'var(--text-ink)' }}>Autonomous worker reads durable decision on restart and drives forward settlement.</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-stone-subtle)' }}>
                  <td style={{ padding: '0.875rem 1rem', fontWeight: 600 }}>Idempotency Handling</td>
                  <td style={{ padding: '0.875rem 1rem', color: 'var(--text-ink-secondary)' }}>Complex session tracking in transaction manager.</td>
                  <td style={{ padding: '0.875rem 1rem', color: 'var(--text-ink)' }}>Natural idempotency key with deterministic inbox deduplication.</td>
                </tr>
                <tr>
                  <td style={{ padding: '0.875rem 1rem', fontWeight: 600 }}>Clearing Invariant</td>
                  <td style={{ padding: '0.875rem 1rem', color: 'var(--text-ink-secondary)' }}>Assumed atomic across instances.</td>
                  <td style={{ padding: '0.875rem 1rem', color: 'var(--text-ink)' }}>Verified mathematically after settlement via Σ ΔL = ₹0.00.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Section 3: Authoritative Workflow Audit Trail */}
        <section style={{ marginBottom: '4rem' }}>
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.75rem',
              fontWeight: 700,
              color: 'var(--text-ink)',
              marginBottom: '1rem',
            }}
          >
            3. Authoritative Workflow Event Types
          </h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-ink-secondary)', lineHeight: 1.65, marginBottom: '1.5rem' }}>
            The coordinator records distinct workflow events into the immutable <code className="font-mono">workflow_events</code> table.
            These exact uppercase event names represent verified database facts:
          </p>

          <div
            className="dark-operational-workspace"
            style={{ padding: '1.5rem', borderRadius: 'var(--radius-sm)' }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.75rem' }}>
              {[
                { name: 'PHASE_PREPARE_STARTED', phase: 'Try' },
                { name: 'SOURCE_PREPARE_REJECTED', phase: 'Try' },
                { name: 'DESTINATION_PREPARE_REJECTED', phase: 'Try' },
                { name: 'DECISION_MADE', phase: 'Decision' },
                { name: 'DECISION_COMMITTED', phase: 'Decision' },
                { name: 'SOURCE_CONFIRMED', phase: 'Confirm' },
                { name: 'DESTINATION_CONFIRMED', phase: 'Confirm' },
                { name: 'TRANSFER_SETTLED', phase: 'Resolution' },
                { name: 'SOURCE_CANCELLED', phase: 'Cancel' },
                { name: 'DESTINATION_CANCELLED', phase: 'Cancel' },
                { name: 'TRANSFER_CANCELLED', phase: 'Resolution' },
              ].map((e, idx) => (
                <div
                  key={idx}
                  style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid var(--border-operational)',
                    borderRadius: 'var(--radius-xs)',
                    padding: '0.75rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-operational)' }}>
                    {e.name}
                  </span>
                  <span
                    style={{
                      fontSize: '0.625rem',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      padding: '0.15rem 0.4rem',
                      borderRadius: 'var(--radius-xs)',
                      backgroundColor: 'rgba(29, 78, 216, 0.15)',
                      color: 'var(--accent-cobalt-light)',
                    }}
                  >
                    {e.phase}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Back Link CTA */}
        <div style={{ borderTop: '1px solid var(--border-stone)', paddingTop: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Link href="/" className="btn-editorial btn-secondary">
            ← Return to Overview
          </Link>
          <Link href="/console" className="btn-editorial btn-primary">
            Enter Operator Console →
          </Link>
        </div>
      </main>

      <SiteFooter />
    </>
  );
}
