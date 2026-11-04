import test from 'node:test';
import assert from 'node:assert';
import {
  WORKFLOW_EVENT_DEFINITIONS,
  getWorkflowEventDefinition,
} from '../lib/constants.ts';

test('Authoritative Workflow Events: Maps all 11 real backend event types', () => {
  const expectedEvents = [
    'PHASE_PREPARE_STARTED',
    'SOURCE_PREPARE_REJECTED',
    'DESTINATION_PREPARE_REJECTED',
    'DECISION_MADE',
    'DECISION_COMMITTED',
    'SOURCE_CONFIRMED',
    'DESTINATION_CONFIRMED',
    'TRANSFER_SETTLED',
    'SOURCE_CANCELLED',
    'DESTINATION_CANCELLED',
    'TRANSFER_CANCELLED',
  ];

  for (const eventType of expectedEvents) {
    const def = WORKFLOW_EVENT_DEFINITIONS[eventType];
    assert.ok(def, `Missing definition for authoritative event ${eventType}`);
    assert.strictEqual(def.eventType, eventType);
    assert.ok(def.stageTitle.length > 0, `Empty stageTitle for ${eventType}`);
    assert.ok(def.description.length > 0, `Empty description for ${eventType}`);
    assert.ok(
      ['prepare', 'decision', 'confirm', 'settlement', 'cancel'].includes(def.phase),
      `Unexpected phase ${def.phase} for ${eventType}`
    );
  }
});

test('Safe Fallback: Handles unknown future workflow event types safely', () => {
  const unknownType = 'PARTICIPANT_TIMEOUT_OBSERVED';
  const def = getWorkflowEventDefinition(unknownType);

  assert.strictEqual(def.eventType, unknownType);
  assert.strictEqual(def.stageTitle, 'PARTICIPANT TIMEOUT OBSERVED');
  assert.strictEqual(def.phase, 'unknown');
  assert.ok(def.description.includes('workflow audit trail'));
});

test('Integrity Check: Fabricated synthetic event types are not present', () => {
  const fabricated = [
    'transfer.intent.created',
    'participant.source.hold_reserved',
    'participant.destination.intent_accepted',
    'coordinator.decision.committed',
    'participant.source.settlement_posted',
    'participant.destination.settlement_posted',
    'transfer.lifecycle.settled',
  ];

  for (const fake of fabricated) {
    assert.strictEqual(
      WORKFLOW_EVENT_DEFINITIONS[fake],
      undefined,
      `Fabricated event ${fake} should not exist in WORKFLOW_EVENT_DEFINITIONS`
    );
  }
});
