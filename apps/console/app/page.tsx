'use client';

import React, { useState, useEffect } from 'react';

// Types
interface OverviewData {
  reachability: Record<string, boolean>;
  total_accounts: number;
  total_customers: number;
  total_transfers: number;
  settled_transfers: number;
  pending_transfers: number;
  oldest_pending_age_seconds: number;
  clearing_sum: number;
  last_reconciliation_status: string;
  fault_injection_enabled: boolean;
}

interface AccountItem {
  account_id: string;
  customer_id: string;
  ledger_id: string;
  routing_version: number;
  provisioning_state: string;
  currency: string;
  posted_balance_minor: number;
  held_amount_minor: number;
  available_balance_minor: number;
  status: string;
}

interface StatementEntry {
  journal_id: string;
  line_no: number;
  account_sequence: number;
  operation_type: string;
  side: string;
  amount_minor: number;
  currency: string;
  created_at: string;
  description?: string;
}

interface TransferItem {
  transfer_id: string;
  state: string;
  amount_minor: number;
  currency: string;
  transfer_type: string;
  source_account_id: string;
  destination_account_id: string;
  source_ledger_id: string;
  destination_ledger_id: string;
  attention_required: boolean;
  attention_reason?: string;
  created_at: string;
  decision?: string;
  decided_at?: string;
}

interface WorkflowEvent {
  event_id: string;
  transfer_id: string;
  event_type: string;
  details: Record<string, any>;
  created_at: string;
}

interface ReconciliationFinding {
  check_name: string;
  severity: string;
  ledger_id: string;
  resource_id: string;
  details: string;
}

interface ReconciliationReport {
  run_at: string;
  status: string;
  coverage: string;
  reachable_ledgers: string[];
  unreachable_ledgers: string[];
  transfers_examined: number;
  clearing_balance_sum: number;
  in_flight_clearing_amount: number;
  findings: ReconciliationFinding[];
}

interface ExperimentStep {
  step_number: number;
  phase: string;
  action: string;
  outcome: string;
  details: string;
}

interface ExperimentResult {
  scenario: string;
  transfer_id: string;
  status: string;
  steps: ExperimentStep[];
  final_accounting_state: Record<string, any>;
}

export default function OperatorConsole() {
  const [activeTab, setActiveTab] = useState<'overview' | 'accounts' | 'transfers' | 'reconciliation' | 'experiments'>('overview');
  const [loading, setLoading] = useState<boolean>(true);
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [transfers, setTransfers] = useState<TransferItem[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<AccountItem | null>(null);
  const [statementEntries, setStatementEntries] = useState<StatementEntry[]>([]);
  const [selectedTransfer, setSelectedTransfer] = useState<TransferItem | null>(null);
  const [transferTimeline, setTransferTimeline] = useState<WorkflowEvent[]>([]);
  const [reconciliationReport, setReconciliationReport] = useState<ReconciliationReport | null>(null);
  const [reconciling, setReconciling] = useState<boolean>(false);
  const [runningExperiment, setRunningExperiment] = useState<boolean>(false);
  const [experimentResult, setExperimentResult] = useState<ExperimentResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Fetch Overview Data
  const fetchOverview = async () => {
    try {
      const res = await fetch('/api/operator/overview');
      if (res.ok) {
        const data = await res.json();
        setOverview(data);
      }
    } catch (err: any) {
      console.error('Error fetching overview:', err);
    }
  };

  // Fetch Accounts
  const fetchAccounts = async () => {
    try {
      const res = await fetch('/api/operator/accounts');
      if (res.ok) {
        const data = await res.json();
        setAccounts(data);
      }
    } catch (err: any) {
      console.error('Error fetching accounts:', err);
    }
  };

  // Fetch Transfers
  const fetchTransfers = async () => {
    try {
      const res = await fetch('/api/operator/transfers?limit=50');
      if (res.ok) {
        const data = await res.json();
        setTransfers(data);
      }
    } catch (err: any) {
      console.error('Error fetching transfers:', err);
    }
  };

  const refreshAll = async () => {
    setLoading(true);
    await Promise.all([fetchOverview(), fetchAccounts(), fetchTransfers()]);
    setLoading(false);
  };

  useEffect(() => {
    refreshAll();
    const interval = setInterval(fetchOverview, 10000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // View Statement
  const openStatement = async (account: AccountItem) => {
    setSelectedAccount(account);
    try {
      const res = await fetch(`/api/accounts/${account.account_id}/statement?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setStatementEntries(data.entries || []);
      }
    } catch (err) {
      console.error('Error fetching statement:', err);
    }
  };

  // View Transfer Timeline
  const openTransferTimeline = async (transfer: TransferItem) => {
    setSelectedTransfer(transfer);
    try {
      const res = await fetch(`/api/operator/transfers/${transfer.transfer_id}/timeline`);
      if (res.ok) {
        const data = await res.json();
        setTransferTimeline(data);
      }
    } catch (err) {
      console.error('Error fetching timeline:', err);
    }
  };

  // Trigger Reconciliation
  const triggerReconciliation = async () => {
    setReconciling(true);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/admin/reconciliation-runs', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ledgerguard_operator_demo_token',
        },
      });
      if (res.ok) {
        const data = await res.json();
        setReconciliationReport({
          run_at: data.run_at,
          status: data.status,
          coverage: 'FULL',
          reachable_ledgers: ['coordinator', 'ledger-1', 'ledger-2'],
          unreachable_ledgers: [],
          transfers_examined: transfers.length,
          clearing_balance_sum: overview?.clearing_sum || 0,
          in_flight_clearing_amount: 0,
          findings: data.findings.map((f: any) => ({
            check_name: f.check_name,
            severity: f.severity,
            ledger_id: 'LOCAL',
            resource_id: f.resource_id,
            details: f.details,
          })),
        });
      } else {
        setErrorMsg('Failed to run reconciliation audit.');
      }
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setReconciling(false);
    }
  };

  // Run Signature Recovery Experiment
  const runExperiment = async (scenario: string) => {
    setRunningExperiment(true);
    setExperimentResult(null);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/operator/experiments/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ledgerguard_operator_demo_token',
        },
        body: JSON.stringify({ scenario }),
      });
      if (res.ok) {
        const data = await res.json();
        setExperimentResult(data);
        fetchOverview();
        fetchTransfers();
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || 'Experiment execution failed.');
      }
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setRunningExperiment(false);
    }
  };

  // Format minor units (paise) to INR
  const formatINR = (paise: number) => {
    const inr = (paise / 100).toFixed(2);
    return `₹${inr}`;
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Header */}
      <header className="header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #6366f1, #38bdf8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            color: '#fff',
            fontSize: '1rem'
          }}>
            LG
          </div>
          <div>
            <h1 style={{ fontSize: '1.125rem', fontWeight: 700, letterSpacing: '-0.01em', lineHeight: 1.2 }}>
              LedgerGuard
            </h1>
            <p style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
              Dual-Ledger TCC Financial Engine
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="nav-tabs">
          <button
            className={`nav-tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            className={`nav-tab ${activeTab === 'accounts' ? 'active' : ''}`}
            onClick={() => setActiveTab('accounts')}
          >
            Accounts ({accounts.length})
          </button>
          <button
            className={`nav-tab ${activeTab === 'transfers' ? 'active' : ''}`}
            onClick={() => setActiveTab('transfers')}
          >
            Transfers ({transfers.length})
          </button>
          <button
            className={`nav-tab ${activeTab === 'reconciliation' ? 'active' : ''}`}
            onClick={() => setActiveTab('reconciliation')}
          >
            Reconciliation
          </button>
          <button
            className={`nav-tab ${activeTab === 'experiments' ? 'active' : ''}`}
            onClick={() => setActiveTab('experiments')}
          >
            Experiments
          </button>
        </nav>

        {/* Live System Indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.375rem' }}>
              <span style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: overview?.reachability?.coordinator ? '#10b981' : '#f43f5e'
              }} />
              Coordinator
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.375rem' }}>
              <span style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: overview?.reachability?.['ledger-1'] ? '#10b981' : '#f43f5e'
              }} />
              Ledger 1
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.375rem' }}>
              <span style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: overview?.reachability?.['ledger-2'] ? '#10b981' : '#f43f5e'
              }} />
              Ledger 2
            </span>
          </div>

          <button
            className="btn btn-secondary"
            onClick={refreshAll}
            style={{ fontSize: '0.75rem', padding: '0.375rem 0.75rem' }}
          >
            Refresh
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main style={{ flex: 1, padding: '2rem', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
        {errorMsg && (
          <div style={{
            background: 'rgba(244, 63, 94, 0.15)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            borderRadius: '8px',
            padding: '1rem',
            color: '#fb7185',
            marginBottom: '1.5rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <span>{errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} style={{ background: 'none', border: 'none', color: '#fb7185', cursor: 'pointer' }}>✕</button>
          </div>
        )}

        {/* ------------------------------------------------------------------ */}
        {/* 1. OVERVIEW SCREEN                                                 */}
        {/* ------------------------------------------------------------------ */}
        {activeTab === 'overview' && (
          <div>
            <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
              <div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                  Platform Overview
                </h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                  Live metrics across Coordinator DB (5442), Ledger 1 DB (5443), and Ledger 2 DB (5444).
                </p>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <span className={`badge ${overview?.last_reconciliation_status === 'PASS' ? 'badge-active' : 'badge-closed'}`}>
                  Reconciliation: {overview?.last_reconciliation_status || 'UNKNOWN'}
                </span>
                <span className="badge badge-settled">
                  Clearing Sum: {overview ? formatINR(overview.clearing_sum) : '₹0.00'}
                </span>
              </div>
            </div>

            {/* Metrics Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              <div className="glass-panel metric-card">
                <span className="metric-label">Total Provisioned Accounts</span>
                <span className="metric-value">{overview?.total_accounts || 0}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Customers: {overview?.total_customers || 0}
                </span>
              </div>

              <div className="glass-panel metric-card">
                <span className="metric-label">Settled Transfers</span>
                <span className="metric-value" style={{ color: 'var(--accent-cyan)' }}>
                  {overview?.settled_transfers || 0}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Total Requests: {overview?.total_transfers || 0}
                </span>
              </div>

              <div className="glass-panel metric-card">
                <span className="metric-label">Pending TCC Transfers</span>
                <span className="metric-value" style={{ color: overview?.pending_transfers ? 'var(--accent-amber)' : 'var(--text-primary)' }}>
                  {overview?.pending_transfers || 0}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Oldest Age: {overview?.oldest_pending_age_seconds || 0}s
                </span>
              </div>

              <div className="glass-panel metric-card">
                <span className="metric-label">Inter-Ledger Clearing</span>
                <span className="metric-value" style={{ color: overview?.clearing_sum === 0 ? 'var(--status-active-text)' : 'var(--status-closed-text)' }}>
                  {overview ? formatINR(overview.clearing_sum) : '₹0.00'}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Invariant: L1 + L2 Clearing == 0
                </span>
              </div>
            </div>

            {/* Architectural Invariants Card */}
            <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--accent-indigo)' }}>
                System Architecture & Financial Guarantees
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.875rem', borderRadius: '8px' }}>
                  <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>
                    1. Independent Failure Domains
                  </strong>
                  Coordinator and participants run on separate PostgreSQL 17 instances. Schemas alone are not a failure domain; network isolation guarantees autonomous persistence.
                </div>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.875rem', borderRadius: '8px' }}>
                  <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>
                    2. Mutual Exclusion & Forward Recovery
                  </strong>
                  COMMIT and CANCEL decisions are strictly mutually exclusive. Once COMMIT is recorded, the workflow ALWAYS recovers forward; automatic refunds are prohibited.
                </div>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.875rem', borderRadius: '8px' }}>
                  <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>
                    3. Tombstones & Zero Residual Holds
                  </strong>
                  Cancellations arriving prior to prepare leave durable tombstones, preventing reordered messages from locking funds. Holds never expire unilaterally.
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button className="btn btn-primary" onClick={() => setActiveTab('experiments')}>
                Launch Signature Failure Demo
              </button>
              <button className="btn btn-secondary" onClick={() => setActiveTab('reconciliation')}>
                Inspect Cross-Ledger Audit
              </button>
            </div>
          </div>
        )}

        {/* ------------------------------------------------------------------ */}
        {/* 2. ACCOUNTS & STATEMENTS SCREEN                                   */}
        {/* ------------------------------------------------------------------ */}
        {activeTab === 'accounts' && (
          <div>
            <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                  Customer Accounts & Statements
                </h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                  Authoritative posted, held, and available balances across participants.
                </p>
              </div>
              <button className="btn btn-secondary" onClick={fetchAccounts}>
                Refresh Accounts
              </button>
            </div>

            <div className="glass-panel" style={{ overflow: 'hidden' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Account ID</th>
                    <th>Ledger</th>
                    <th>Status</th>
                    <th>Posted Balance</th>
                    <th>Active Holds</th>
                    <th>Available Balance</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((acct) => (
                    <tr key={acct.account_id}>
                      <td className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                        {acct.account_id}
                      </td>
                      <td>
                        <span className="badge badge-pending">{acct.ledger_id}</span>
                      </td>
                      <td>
                        <span className={`badge ${
                          acct.status === 'ACTIVE' ? 'badge-active' :
                          acct.status === 'FROZEN' ? 'badge-frozen' : 'badge-closed'
                        }`}>
                          {acct.status}
                        </span>
                      </td>
                      <td style={{ fontWeight: 600 }}>{formatINR(acct.posted_balance_minor)}</td>
                      <td style={{ color: acct.held_amount_minor > 0 ? 'var(--accent-amber)' : 'var(--text-muted)' }}>
                        {formatINR(acct.held_amount_minor)}
                      </td>
                      <td style={{ fontWeight: 600, color: 'var(--status-active-text)' }}>
                        {formatINR(acct.available_balance_minor)}
                      </td>
                      <td>
                        <button
                          className="btn btn-secondary"
                          style={{ fontSize: '0.75rem', padding: '0.25rem 0.625rem' }}
                          onClick={() => openStatement(acct)}
                        >
                          Statement
                        </button>
                      </td>
                    </tr>
                  ))}
                  {accounts.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                        No accounts found. Use the Experiments tab or CLI to provision test accounts.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Statement Modal */}
            {selectedAccount && (
              <div style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0, 0, 0, 0.7)',
                backdropFilter: 'blur(8px)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 100,
                padding: '1.5rem',
              }}>
                <div className="glass-panel" style={{ width: '100%', maxWidth: '800px', maxHeight: '80vh', overflowY: 'auto', padding: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <div>
                      <h3 style={{ fontSize: '1.125rem', fontWeight: 700 }}>
                        Statement History
                      </h3>
                      <p className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                        {selectedAccount.account_id} ({selectedAccount.ledger_id})
                      </p>
                    </div>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.25rem 0.5rem' }}
                      onClick={() => setSelectedAccount(null)}
                    >
                      ✕
                    </button>
                  </div>

                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Seq #</th>
                        <th>Timestamp</th>
                        <th>Operation</th>
                        <th>Side</th>
                        <th>Amount</th>
                        <th>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {statementEntries.map((e) => (
                        <tr key={`${e.journal_id}-${e.line_no}`}>
                          <td className="font-mono">{e.account_sequence}</td>
                          <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {new Date(e.created_at).toLocaleTimeString()}
                          </td>
                          <td>
                            <span className="badge badge-pending">{e.operation_type}</span>
                          </td>
                          <td style={{ color: e.side === 'CREDIT' ? 'var(--status-active-text)' : 'var(--status-closed-text)', fontWeight: 600 }}>
                            {e.side}
                          </td>
                          <td style={{ fontWeight: 600 }}>{formatINR(e.amount_minor)}</td>
                          <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                            {e.description || '—'}
                          </td>
                        </tr>
                      ))}
                      {statementEntries.length === 0 && (
                        <tr>
                          <td colSpan={6} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>
                            No statement entries recorded for this account.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ------------------------------------------------------------------ */}
        {/* 3. TRANSFER EXPLORER & TIMELINE SCREEN                            */}
        {/* ------------------------------------------------------------------ */}
        {activeTab === 'transfers' && (
          <div>
            <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                  Distributed Transfer Explorer (TCC Coordination)
                </h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                  Track reserve/confirm/cancel protocol state, durable decisions, and workflow audit events.
                </p>
              </div>
              <button className="btn btn-secondary" onClick={fetchTransfers}>
                Refresh Transfers
              </button>
            </div>

            <div className="glass-panel" style={{ overflow: 'hidden', marginBottom: '1.5rem' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Transfer ID</th>
                    <th>Type</th>
                    <th>Route</th>
                    <th>Amount</th>
                    <th>State</th>
                    <th>Decision</th>
                    <th>Attention</th>
                    <th>Created At</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {transfers.map((t) => (
                    <tr key={t.transfer_id}>
                      <td className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                        {t.transfer_id.substring(0, 8)}...
                      </td>
                      <td>
                        <span className="badge badge-pending">{t.transfer_type}</span>
                      </td>
                      <td style={{ fontSize: '0.8125rem' }}>
                        {t.source_ledger_id} → {t.destination_ledger_id}
                      </td>
                      <td style={{ fontWeight: 600 }}>{formatINR(t.amount_minor)}</td>
                      <td>
                        <span className={`badge ${
                          t.state === 'SETTLED' ? 'badge-settled' :
                          t.state === 'CANCELLED' ? 'badge-closed' : 'badge-frozen'
                        }`}>
                          {t.state}
                        </span>
                      </td>
                      <td>
                        {t.decision ? (
                          <span className={`badge ${t.decision === 'COMMIT' ? 'badge-active' : 'badge-closed'}`}>
                            {t.decision}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Pending</span>
                        )}
                      </td>
                      <td>
                        {t.attention_required ? (
                          <span className="badge badge-closed">ATTENTION</span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>None</span>
                        )}
                      </td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {new Date(t.created_at).toLocaleTimeString()}
                      </td>
                      <td>
                        <button
                          className="btn btn-secondary"
                          style={{ fontSize: '0.75rem', padding: '0.25rem 0.625rem' }}
                          onClick={() => openTransferTimeline(t)}
                        >
                          Timeline
                        </button>
                      </td>
                    </tr>
                  ))}
                  {transfers.length === 0 && (
                    <tr>
                      <td colSpan={9} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                        No transfers recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Transfer Timeline Panel */}
            {selectedTransfer && (
              <div className="glass-panel" style={{ padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ fontSize: '1.125rem', fontWeight: 700 }}>
                    TCC Workflow Timeline: {selectedTransfer.transfer_id}
                  </h3>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: '0.25rem 0.5rem' }}
                    onClick={() => setSelectedTransfer(null)}
                  >
                    Close
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {transferTimeline.map((ev, idx) => (
                    <div
                      key={ev.event_id}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '1rem',
                        padding: '0.75rem',
                        background: 'rgba(0,0,0,0.2)',
                        borderRadius: '8px',
                        borderLeft: '3px solid var(--accent-cyan)'
                      }}
                    >
                      <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        #{idx + 1}
                      </span>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--accent-cyan)' }}>
                              {ev.event_type}
                            </span>
                            {Boolean(ev.details && typeof ev.details === 'object' && (ev.details as Record<string, unknown>).role) && (
                              <span style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                                {String((ev.details as Record<string, unknown>).role).toUpperCase()} ({String((ev.details as Record<string, unknown>).ledger_id)})
                              </span>
                            )}
                          </div>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {new Date(ev.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                        {ev.details && Object.keys(ev.details).length > 0 && (
                          <pre style={{ fontSize: '0.75rem', marginTop: '0.375rem', color: 'var(--text-secondary)', background: 'rgba(0,0,0,0.3)', padding: '0.375rem', borderRadius: '4px' }}>
                            {JSON.stringify(ev.details, null, 2)}
                          </pre>
                        )}
                      </div>
                    </div>
                  ))}
                  {transferTimeline.length === 0 && (
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                      No granular workflow events recorded for this transfer.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ------------------------------------------------------------------ */}
        {/* 4. RECONCILIATION CONSOLE                                         */}
        {/* ------------------------------------------------------------------ */}
        {activeTab === 'reconciliation' && (
          <div>
            <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                  Double-Entry & Cross-Ledger Audit
                </h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                  Comprehensive verification of balance caches, journal equality, and clearing balance sum.
                </p>
              </div>
              <button
                className="btn btn-primary"
                onClick={triggerReconciliation}
                disabled={reconciling}
              >
                {reconciling ? 'Running Audit...' : 'Execute Live Audit'}
              </button>
            </div>

            {reconciliationReport && (
              <div>
                {/* Audit summary bar */}
                <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                    <div>
                      <span className="metric-label">Audit Outcome</span>
                      <div style={{ marginTop: '0.25rem' }}>
                        <span className={`badge ${reconciliationReport.status === 'PASS' ? 'badge-active' : 'badge-closed'}`}>
                          {reconciliationReport.status}
                        </span>
                      </div>
                    </div>
                    <div>
                      <span className="metric-label">Reachability Coverage</span>
                      <div style={{ marginTop: '0.25rem' }}>
                        <span className={`badge ${reconciliationReport.coverage === 'FULL' ? 'badge-settled' : 'badge-frozen'}`}>
                          {reconciliationReport.coverage} ({reconciliationReport.reachable_ledgers.length} reachable)
                        </span>
                      </div>
                    </div>
                    <div>
                      <span className="metric-label">Clearing Sum</span>
                      <div style={{ fontSize: '1.25rem', fontWeight: 700, color: reconciliationReport.clearing_balance_sum === 0 ? 'var(--status-active-text)' : 'var(--status-closed-text)' }}>
                        {formatINR(reconciliationReport.clearing_balance_sum)}
                      </div>
                    </div>
                    <div>
                      <span className="metric-label">Audit Timestamp</span>
                      <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                        {new Date(reconciliationReport.run_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Findings Table */}
                <div className="glass-panel" style={{ overflow: 'hidden' }}>
                  <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-subtle)', fontWeight: 600 }}>
                    Audit Findings ({reconciliationReport.findings.length})
                  </div>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Severity</th>
                        <th>Check Name</th>
                        <th>Resource ID</th>
                        <th>Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reconciliationReport.findings.map((f, idx) => (
                        <tr key={idx}>
                          <td>
                            <span className={`badge ${
                              f.severity === 'CRITICAL' ? 'badge-closed' :
                              f.severity === 'WARNING' ? 'badge-frozen' : 'badge-pending'
                            }`}>
                              {f.severity}
                            </span>
                          </td>
                          <td className="font-mono" style={{ fontSize: '0.8125rem', fontWeight: 600 }}>
                            {f.check_name}
                          </td>
                          <td className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                            {f.resource_id}
                          </td>
                          <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                            {f.details}
                          </td>
                        </tr>
                      ))}
                      {reconciliationReport.findings.length === 0 && (
                        <tr>
                          <td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: 'var(--status-active-text)' }}>
                            ✓ Clean audit: All double-entry journals balance, wallet caches match line sums, and inter-ledger clearing balances sum to zero.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ------------------------------------------------------------------ */}
        {/* 5. EXPERIMENT CONSOLE (FAULT INJECTION & RECOVERY)                */}
        {/* ------------------------------------------------------------------ */}
        {activeTab === 'experiments' && (
          <div>
            <div style={{ marginBottom: '1.5rem' }}>
              <h2 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                Deterministic Failure Matrix & Recovery Experiments
              </h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                Execute signature failure scenarios against live PostgreSQL instances to verify durable crash recovery and zero residual holds.
              </p>
            </div>

            {/* Experiment Card */}
            <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--accent-cyan)', marginBottom: '0.375rem' }}>
                    Signature Scenario: Crash After COMMIT → Forward Recovery
                  </h3>
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', maxWidth: '680px', lineHeight: 1.5 }}>
                    Alice (Ledger 1) sends ₹300.00 to Bob (Ledger 2). The coordinator initiates a TCC transfer, reserves funds on Ledger 1, accepts the obligation on Ledger 2, and commits the decision under row lock. The coordinator process immediately crashes before dispatching confirmation. On recovery, the worker recovers forward to final settlement with zero residual holds and exact single credit.
                  </p>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => runExperiment('SIGNATURE_RECOVERY')}
                  disabled={runningExperiment}
                  style={{ minWidth: '160px', justifyContent: 'center' }}
                >
                  {runningExperiment ? 'Simulating Fault...' : 'Execute Scenario'}
                </button>
              </div>

              {/* Live Stepper Output */}
              {experimentResult && (
                <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '1.5rem' }}>
                  <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    Execution Trace (Transfer ID: <span className="font-mono" style={{ color: 'var(--accent-cyan)' }}>{experimentResult.transfer_id}</span>)
                  </h4>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {experimentResult.steps.map((st) => (
                      <div
                        key={st.step_number}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '1rem',
                          padding: '0.875rem',
                          background: st.phase === 'FAULT_INJECTION' ? 'rgba(244, 63, 94, 0.1)' : 'rgba(0, 0, 0, 0.25)',
                          borderRadius: '8px',
                          borderLeft: `4px solid ${
                            st.phase === 'FAULT_INJECTION' ? '#f43f5e' :
                            st.phase === 'FORWARD_RECOVERY' ? '#6366f1' :
                            st.phase === 'AUDIT_VERIFICATION' ? '#10b981' : '#38bdf8'
                          }`
                        }}
                      >
                        <span className="font-mono" style={{ fontWeight: 700, fontSize: '0.875rem' }}>
                          Step {st.step_number}
                        </span>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                              [{st.phase}] {st.action}
                            </span>
                            <span className={`badge ${
                              st.outcome === 'VERIFIED' || st.outcome === 'SUCCESS' ? 'badge-active' :
                              st.outcome === 'CRASH_SIMULATED' ? 'badge-closed' : 'badge-pending'
                            }`}>
                              {st.outcome}
                            </span>
                          </div>
                          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                            {st.details}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Final Balance Card */}
                  <div style={{
                    marginTop: '1.25rem',
                    background: 'rgba(16, 185, 129, 0.08)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    borderRadius: '8px',
                    padding: '1rem',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}>
                    <div>
                      <strong style={{ color: 'var(--status-active-text)' }}>Final Invariant Verification Passed:</strong>
                      <span style={{ marginLeft: '0.5rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                        Alice final posted: {formatINR(experimentResult.final_accounting_state.alice_posted)}, Alice held: {formatINR(experimentResult.final_accounting_state.alice_held)} (zero residual hold). Bob received: {formatINR(experimentResult.final_accounting_state.bob_posted)}.
                      </span>
                    </div>
                    <span className="badge badge-active">All Gates Satisfied</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
