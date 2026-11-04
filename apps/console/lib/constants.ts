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

export interface TCCStageDefinition {
  stageNumber: number;
  id: string;
  title: string;
  protocolEvent: string;
  description: string;
  phase: 'prepare' | 'decision' | 'confirm' | 'settlement';
}

/**
 * The 7 canonical stages of the LedgerGuard TCC Transfer Protocol.
 */
export const TCC_STAGES: TCCStageDefinition[] = [
  {
    stageNumber: 1,
    id: 'intent_created',
    title: 'Intent Created',
    protocolEvent: 'transfer.intent.created',
    description: 'Coordinator accepts request and writes transfer intent under idempotency lock.',
    phase: 'prepare',
  },
  {
    stageNumber: 2,
    id: 'source_reservation',
    title: 'Source Reservation',
    protocolEvent: 'participant.source.hold_reserved',
    description: 'Source ledger isolates funds via balance hold in local ACID transaction.',
    phase: 'prepare',
  },
  {
    stageNumber: 3,
    id: 'destination_reservation',
    title: 'Destination Reservation',
    protocolEvent: 'participant.destination.intent_accepted',
    description: 'Destination ledger validates recipient account status and registers incoming obligation.',
    phase: 'prepare',
  },
  {
    stageNumber: 4,
    id: 'durable_decision',
    title: 'Durable Decision Logged',
    protocolEvent: 'coordinator.decision.committed',
    description: 'Coordinator commits durable COMMIT decision under row lock. Irreversible recovery boundary.',
    phase: 'decision',
  },
  {
    stageNumber: 5,
    id: 'source_confirmation',
    title: 'Source Confirmation',
    protocolEvent: 'participant.source.settlement_posted',
    description: 'Source ledger releases hold and posts immutable debit journal entry.',
    phase: 'confirm',
  },
  {
    stageNumber: 6,
    id: 'destination_confirmation',
    title: 'Destination Confirmation',
    protocolEvent: 'participant.destination.settlement_posted',
    description: 'Destination ledger posts immutable credit journal entry to recipient balance.',
    phase: 'confirm',
  },
  {
    stageNumber: 7,
    id: 'settlement_resolved',
    title: 'Settlement Complete',
    protocolEvent: 'transfer.lifecycle.settled',
    description: 'Both autonomous ledgers settled; inter-ledger clearing balances conserved.',
    phase: 'settlement',
  },
];
