/**
 * Global constants for LedgerGuard operator control plane.
 */

export const REFRESH_INTERVAL_MS = 10000;

export const DEMO_OPERATOR_AUTH_HEADER = 'Bearer ledgerguard_operator_demo_token';

export const CLUSTER_NODES = [
  {
    id: 'coordinator',
    name: 'Coordinator',
    port: 5442,
    role: 'coordinator' as const,
    description: 'Routing directory & durable decision log',
  },
  {
    id: 'ledger-1',
    name: 'Ledger 1',
    port: 5443,
    role: 'participant' as const,
    description: 'Autonomous double-entry participant kernel',
  },
  {
    id: 'ledger-2',
    name: 'Ledger 2',
    port: 5444,
    role: 'participant' as const,
    description: 'Autonomous double-entry participant kernel',
  },
];

export interface WorkflowEventDefinition {
  eventType: string;
  stageTitle: string;
  phase: 'prepare' | 'decision' | 'confirm' | 'settlement' | 'cancel' | 'unknown';
  description: string;
}

/**
 * Authoritative set of real workflow event definitions emitted by LedgerGuard backend.
 * Source: orchestrator.py, coordinator_service.py, and workflow_events audit table.
 */
export const WORKFLOW_EVENT_DEFINITIONS: Record<string, WorkflowEventDefinition> = {
  PHASE_PREPARE_STARTED: {
    eventType: 'PHASE_PREPARE_STARTED',
    stageTitle: 'Phase 1: Prepare Phase Initiated',
    phase: 'prepare',
    description: 'Coordinator begins Try phase: reserves balance on source ledger and verifies destination account viability.',
  },
  SOURCE_PREPARE_REJECTED: {
    eventType: 'SOURCE_PREPARE_REJECTED',
    stageTitle: 'Phase 1: Source Reservation Rejected',
    phase: 'prepare',
    description: 'Source participant ledger rejected fund reservation due to insufficient available balance or account status.',
  },
  DESTINATION_PREPARE_REJECTED: {
    eventType: 'DESTINATION_PREPARE_REJECTED',
    stageTitle: 'Phase 1: Destination Validation Rejected',
    phase: 'prepare',
    description: 'Destination participant ledger rejected transfer incoming intent obligation.',
  },
  DECISION_MADE: {
    eventType: 'DECISION_MADE',
    stageTitle: 'Decision Point: Consensus Decision Logged',
    phase: 'decision',
    description: 'Coordinator writes atomic, immutable COMMIT or CANCEL decision to transfer_decisions under row lock.',
  },
  DECISION_COMMITTED: {
    eventType: 'DECISION_COMMITTED',
    stageTitle: 'Decision Point: Committing State Acknowledged',
    phase: 'decision',
    description: 'Coordinator transitions transfer to COMMITTING state. Point of no return: rollback is prohibited.',
  },
  SOURCE_CONFIRMED: {
    eventType: 'SOURCE_CONFIRMED',
    stageTitle: 'Phase 2: Source Settlement Confirmed',
    phase: 'confirm',
    description: 'Source ledger releases active balance hold and posts permanent debit journal entry in local ACID transaction.',
  },
  DESTINATION_CONFIRMED: {
    eventType: 'DESTINATION_CONFIRMED',
    stageTitle: 'Phase 2: Destination Settlement Confirmed',
    phase: 'confirm',
    description: 'Destination ledger posts permanent credit journal entry to recipient balance and clears incoming obligation.',
  },
  TRANSFER_SETTLED: {
    eventType: 'TRANSFER_SETTLED',
    stageTitle: 'Final Resolution: Transfer Settled',
    phase: 'settlement',
    description: 'Coordinator confirms settlement across all participants; inter-ledger clearing balances conserved.',
  },
  SOURCE_CANCELLED: {
    eventType: 'SOURCE_CANCELLED',
    stageTitle: 'Phase 2: Source Reservation Cancelled',
    phase: 'cancel',
    description: 'Source ledger releases active hold back to available customer balance.',
  },
  DESTINATION_CANCELLED: {
    eventType: 'DESTINATION_CANCELLED',
    stageTitle: 'Phase 2: Destination Obligation Cancelled',
    phase: 'cancel',
    description: 'Destination ledger cancels incoming transfer intent and releases obligation.',
  },
  TRANSFER_CANCELLED: {
    eventType: 'TRANSFER_CANCELLED',
    stageTitle: 'Final Resolution: Transfer Cancelled',
    phase: 'cancel',
    description: 'Coordinator transitions transfer to terminal CANCELLED state.',
  },
};

/**
 * Return authoritative event metadata or a safe fallback for unknown event types.
 */
export function getWorkflowEventDefinition(eventType: string): WorkflowEventDefinition {
  if (WORKFLOW_EVENT_DEFINITIONS[eventType]) {
    return WORKFLOW_EVENT_DEFINITIONS[eventType];
  }
  return {
    eventType,
    stageTitle: eventType.replace(/_/g, ' '),
    phase: 'unknown',
    description: 'Recorded workflow audit trail event from coordinator execution log.',
  };
}
