/**
 * Centralized API client for LedgerGuard operator console.
 * Strictly preserves all backend paths, HTTP methods, headers, and payloads.
 */

import {
  AccountItem,
  ExperimentResult,
  OverviewData,
  ReconciliationReport,
  StatementEntry,
  TransferItem,
  WorkflowEvent,
} from './types';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

/**
 * Build headers for state-changing requests. Authentication is the HttpOnly
 * session cookie; the backend requires the session's CSRF token on mutations.
 * No static credential is ever bundled into the client.
 */
export function csrfHeaders(
  csrfToken: string | null,
  extra: Record<string, string> = {}
): Record<string, string> {
  return csrfToken ? { ...extra, 'X-CSRF-Token': csrfToken } : { ...extra };
}

/**
 * Fetch consolidated platform metrics and node reachability.
 */
export async function getOverview(): Promise<OverviewData> {
  const res = await fetch('/api/operator/overview', { cache: 'no-store' });
  if (!res.ok) {
    throw new ApiError('Failed to fetch platform overview', res.status);
  }
  return res.json();
}

/**
 * Fetch list of provisioned customer accounts with current balances.
 */
export async function getAccounts(): Promise<AccountItem[]> {
  const res = await fetch('/api/operator/accounts', { cache: 'no-store' });
  if (!res.ok) {
    throw new ApiError('Failed to fetch accounts list', res.status);
  }
  return res.json();
}

/**
 * Fetch list of recent distributed transfers.
 */
export async function getTransfers(limit: number = 50): Promise<TransferItem[]> {
  const res = await fetch(`/api/operator/transfers?limit=${limit}`, { cache: 'no-store' });
  if (!res.ok) {
    throw new ApiError('Failed to fetch transfers list', res.status);
  }
  return res.json();
}

/**
 * Fetch immutable journal statement for a specific customer account.
 */
export async function getAccountStatement(
  accountId: string,
  limit: number = 20,
  cursor?: number
): Promise<{ account_id: string; entries: StatementEntry[]; next_cursor: number | null }> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor !== undefined && cursor !== null) {
    query.set('cursor', String(cursor));
  }
  const res = await fetch(`/api/accounts/${accountId}/statement?${query.toString()}`, {
    cache: 'no-store',
  });
  if (!res.ok) {
    throw new ApiError(`Failed to fetch statement for account ${accountId}`, res.status);
  }
  const data = await res.json();
  return {
    account_id: data.account_id,
    entries: data.entries || [],
    next_cursor: data.next_cursor ?? null,
  };
}

/**
 * Fetch granular chronological workflow events for a transfer.
 */
export async function getTransferTimeline(transferId: string): Promise<WorkflowEvent[]> {
  const res = await fetch(`/api/operator/transfers/${transferId}/timeline`, {
    cache: 'no-store',
  });
  if (!res.ok) {
    throw new ApiError(`Failed to fetch timeline for transfer ${transferId}`, res.status);
  }
  return res.json();
}

/**
 * Execute an on-demand double-entry reconciliation audit.
 * Returns exact fields from ReconciliationRunResponse without synthetic fields.
 */
export async function executeReconciliation(
  csrfToken: string | null
): Promise<ReconciliationReport> {
  const res = await fetch('/api/admin/reconciliation-runs', {
    method: 'POST',
    headers: csrfHeaders(csrfToken),
    cache: 'no-store',
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(
      errBody?.detail || 'Reconciliation audit execution failed',
      res.status
    );
  }

  const data = await res.json();
  return {
    run_id: data.run_id,
    run_at: data.run_at,
    status: data.status,
    accounts_examined: data.accounts_examined,
    journals_examined: data.journals_examined,
    lines_examined: data.lines_examined,
    trial_balance_debit: data.trial_balance_debit,
    trial_balance_credit: data.trial_balance_credit,
    findings: (data.findings || []).map((f: any) => ({
      check_name: f.check_name,
      severity: f.severity,
      resource_id: f.resource_id,
      details: f.details,
    })),
  };
}

/**
 * Execute a named deterministic fault injection and recovery scenario.
 */
export async function executeExperiment(
  scenario: string,
  csrfToken: string | null
): Promise<ExperimentResult> {
  const res = await fetch('/api/operator/experiments/run', {
    method: 'POST',
    headers: csrfHeaders(csrfToken, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ scenario }),
    cache: 'no-store',
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(
      errBody?.detail || `Experiment ${scenario} failed to execute`,
      res.status
    );
  }

  return res.json();
}
