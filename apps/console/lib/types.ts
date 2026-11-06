/**
 * Core type definitions for LedgerGuard Operator Console.
 * Matches backend API schemas and domain models.
 */

export type NavigationTab = 'overview' | 'accounts' | 'transfers' | 'reconciliation' | 'experiments' | 'security';

export interface OperatorPublicInfo {
  operator_id: string;
  username: string;
  email: string;
  role: 'OPERATOR' | 'ADMIN' | 'AUDITOR';
  totp_enabled: boolean;
}

export interface LoginResponse {
  status: 'SUCCESS' | 'MFA_REQUIRED';
  temp_token?: string;
  csrf_token?: string;
  operator?: OperatorPublicInfo;
  message: string;
}

export interface SessionResponse {
  authenticated: boolean;
  operator?: OperatorPublicInfo;
  csrf_token?: string;
}

export interface OverviewData {
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

export interface AccountItem {
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

export interface StatementEntry {
  journal_id: string;
  line_no: number;
  account_sequence: number;
  operation_type: string;
  side: string;
  amount_minor: number;
  currency: string;
  created_at: string;
  description?: string;
  correlation_id?: string;
  transfer_id?: string;
}

export interface TransferItem {
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

export interface WorkflowEvent {
  event_id: string;
  transfer_id: string;
  event_type: string;
  details: Record<string, any>;
  created_at: string;
}

export interface ReconciliationFinding {
  check_name: string;
  severity: string;
  resource_id: string;
  details: string;
}

export interface ReconciliationReport {
  run_id: string;
  run_at: string;
  status: string;
  accounts_examined: number;
  journals_examined: number;
  lines_examined: number;
  trial_balance_debit: number;
  trial_balance_credit: number;
  findings: ReconciliationFinding[];
}

export interface StatementResponseData {
  account_id: string;
  entries: StatementEntry[];
  next_cursor: number | null;
}

export interface ExperimentStep {
  step_number: number;
  phase: string;
  action: string;
  outcome: string;
  details: string;
}

export interface ExperimentResult {
  scenario: string;
  transfer_id: string;
  status: string;
  steps: ExperimentStep[];
  final_accounting_state: Record<string, any>;
}

export interface ClusterNodeInfo {
  id: string;
  name: string;
  port: number;
  role: 'coordinator' | 'participant';
  isReachable: boolean;
}
