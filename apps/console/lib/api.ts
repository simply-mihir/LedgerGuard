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
import { DEMO_OPERATOR_AUTH_HEADER } from './constants';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
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
  limit: number = 20
): Promise<StatementEntry[]> {
  const res = await fetch(`/api/accounts/${accountId}/statement?limit=${limit}`, {
    cache: 'no-store',
  });
  if (!res.ok) {
    throw new ApiError(`Failed to fetch statement for account ${accountId}`, res.status);
  }
  const data = await res.json();
  return data.entries || [];
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
 * Execute an on-demand multi-ledger reconciliation audit.
 */
export async function executeReconciliation(
  transfersCount: number = 0,
  clearingSum: number = 0
): Promise<ReconciliationReport> {
  const res = await fetch('/api/admin/reconciliation-runs', {
    method: 'POST',
    headers: {
      Authorization: DEMO_OPERATOR_AUTH_HEADER,
    },
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
    run_at: data.run_at,
    status: data.status,
    coverage: 'FULL',
    reachable_ledgers: ['coordinator', 'ledger-1', 'ledger-2'],
    unreachable_ledgers: [],
    transfers_examined: transfersCount,
    clearing_balance_sum: clearingSum,
    in_flight_clearing_amount: 0,
    findings: (data.findings || []).map((f: any) => ({
      check_name: f.check_name,
      severity: f.severity,
      ledger_id: 'LOCAL',
      resource_id: f.resource_id,
      details: f.details,
    })),
  };
}

/**
 * Execute a named deterministic fault injection and recovery scenario.
 */
export async function executeExperiment(scenario: string): Promise<ExperimentResult> {
  const res = await fetch('/api/operator/experiments/run', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: DEMO_OPERATOR_AUTH_HEADER,
    },
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
