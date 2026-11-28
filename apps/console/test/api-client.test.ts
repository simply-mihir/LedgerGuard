import { describe, it, afterEach } from 'node:test';
import assert from 'node:assert';
import { csrfHeaders, executeExperiment, executeReconciliation } from '../lib/api';

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function mockFetch(body: unknown) {
  const calls: { url: string; init: RequestInit }[] = [];
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(JSON.stringify(body), { status: 200 });
  }) as typeof fetch;
  return calls;
}

describe('API client state-changing requests', () => {
  it('csrfHeaders adds the session CSRF token only when present', () => {
    assert.deepStrictEqual(csrfHeaders('tok'), { 'X-CSRF-Token': 'tok' });
    assert.deepStrictEqual(csrfHeaders(null, { A: 'b' }), { A: 'b' });
  });

  it('reconciliation sends the CSRF token and never a static bearer credential', async () => {
    const calls = mockFetch({ run_id: 'r', run_at: 'now', status: 'PASS', accounts_examined: 0,
      journals_examined: 0, lines_examined: 0, trial_balance_debit: 0, trial_balance_credit: 0, findings: [] });
    await executeReconciliation('csrf-123');
    const headers = calls[0].init.headers as Record<string, string>;
    assert.strictEqual(headers['X-CSRF-Token'], 'csrf-123');
    assert.strictEqual(headers['Authorization'], undefined);
  });

  it('experiments send JSON content type, CSRF token and no static credential', async () => {
    const calls = mockFetch({ scenario: 'S', transfer_id: 't', status: 'OK', steps: [], final_accounting_state: {} });
    await executeExperiment('SIGNATURE_RECOVERY', 'csrf-456');
    const headers = calls[0].init.headers as Record<string, string>;
    assert.strictEqual(headers['X-CSRF-Token'], 'csrf-456');
    assert.strictEqual(headers['Content-Type'], 'application/json');
    assert.strictEqual(headers['Authorization'], undefined);
  });
});
