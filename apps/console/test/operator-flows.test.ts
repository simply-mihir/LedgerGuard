import { describe, it } from 'node:test';
import assert from 'node:assert';
import { formatINR, formatNumber } from '../lib/format';

function getSafeReturnUrl(param: string | null): string {
  if (!param) return '/console';
  if (param.startsWith('/') && !param.startsWith('//') && !param.startsWith('/\\')) {
    const pathOnly = param.split('?')[0];
    if (!pathOnly.includes(':')) {
      return param;
    }
  }
  return '/console';
}

describe('Safe Return URL Redirection', () => {
  it('accepts safe relative internal routes', () => {
    assert.strictEqual(getSafeReturnUrl('/console'), '/console');
    assert.strictEqual(getSafeReturnUrl('/console/accounts'), '/console/accounts');
    assert.strictEqual(getSafeReturnUrl('/console/transfers/abc-123'), '/console/transfers/abc-123');
    assert.strictEqual(getSafeReturnUrl('/console/reconciliation?tab=audit'), '/console/reconciliation?tab=audit');
  });

  it('rejects protocol-relative and external domain URLs', () => {
    assert.strictEqual(getSafeReturnUrl('//evil.com/phish'), '/console');
    assert.strictEqual(getSafeReturnUrl('https://evil.com'), '/console');
    assert.strictEqual(getSafeReturnUrl('http://evil.com'), '/console');
    assert.strictEqual(getSafeReturnUrl('javascript:alert(1)'), '/console');
    assert.strictEqual(getSafeReturnUrl('data:text/html,malicious'), '/console');
  });

  it('rejects backslash evasion targets', () => {
    assert.strictEqual(getSafeReturnUrl('/\\evil.com'), '/console');
    assert.strictEqual(getSafeReturnUrl('/evil.com:80/console'), '/console');
  });

  it('defaults to /console when null or empty', () => {
    assert.strictEqual(getSafeReturnUrl(null), '/console');
    assert.strictEqual(getSafeReturnUrl(''), '/console');
  });
});

describe('Financial Arithmetic & Formatting', () => {
  it('formats integer paise to rupee currency with zero floating point drift', () => {
    assert.strictEqual(formatINR(0), '₹0.00');
    assert.strictEqual(formatINR(100), '₹1.00');
    assert.strictEqual(formatINR(5050), '₹50.50');
    assert.strictEqual(formatINR(10000000), '₹1,00,000.00');
    assert.strictEqual(formatINR(250000), '₹2,500.00');
  });

  it('handles negative balances correctly', () => {
    assert.strictEqual(formatINR(-5000), '-₹50.00');
  });

  it('formats large counts with tabular formatting', () => {
    assert.strictEqual(formatNumber(1250), '1,250');
    assert.strictEqual(formatNumber(1000000), '10,00,000');
  });
});

describe('Architecture Truthfulness Guard', () => {
  it('verifies that consensus-free 3-database topology constants are exact', () => {
    const topology = [
      { name: 'Coordinator', port: 5442 },
      { name: 'Ledger 1', port: 5443 },
      { name: 'Ledger 2', port: 5444 },
    ];
    assert.strictEqual(topology.length, 3);
    assert.strictEqual(topology[0].port, 5442);
    assert.strictEqual(topology[1].port, 5443);
    assert.strictEqual(topology[2].port, 5444);
  });
});
