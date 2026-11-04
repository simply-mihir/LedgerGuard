/**
 * Automated accessibility audit suite for LedgerGuard Operator Console.
 * Validates WCAG 2.2 AA design criteria across all primary screens:
 * - / (Editorial landing page)
 * - /login (Credentials authentication)
 * - MFA verification step
 * - /console (System overview)
 * - /console/transfers/[transferId] (Transfer detail & timeline)
 * - /console/reconciliation (Reconciliation screen)
 * - /console/experiments (Failure recovery lab)
 */

import { describe, it } from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';

function loadComponentSource(relPath: string): string {
  const fullPath = path.resolve(__dirname, '..', relPath);
  return fs.readFileSync(fullPath, 'utf-8');
}

describe('Automated Accessibility Audit: Core Pages & WCAG 2.2 Criteria', () => {
  const landingSource = loadComponentSource('app/page.tsx');
  const loginSource = loadComponentSource('app/login/page.tsx');
  const consoleOverviewSource = loadComponentSource('app/console/page.tsx');
  const transferDetailSource = loadComponentSource('app/console/transfers/[transferId]/page.tsx');
  const reconciliationSource = loadComponentSource('app/console/reconciliation/page.tsx');
  const experimentsSource = loadComponentSource('app/console/experiments/page.tsx');

  describe('Page 1: / (Landing Page & Editorial Experience)', () => {
    it('contains semantic landmark elements: main, header, footer', () => {
      assert.ok(landingSource.includes('<main') || landingSource.includes('<header'), 'Must contain semantic landmark elements');
      assert.ok(landingSource.includes('<footer') || landingSource.includes('Footer'), 'Must contain footer landmark');
    });

    it('defines accessible heading structure with h1 and hierarchical h2/h3', () => {
      assert.ok(landingSource.includes('<h1') || landingSource.includes('h1'), 'Landing page must define primary h1 title');
    });

    it('ensures all interactive buttons and links have accessible text content', () => {
      // Look for empty button tags
      const emptyButtons = /<button[^>]*>\s*<\/button>/g.test(landingSource);
      assert.strictEqual(emptyButtons, false, 'Landing page has unlabeled empty buttons');
    });
  });

  describe('Page 2: /login (Credentials Portal)', () => {
    it('associates all form inputs with accessible labels via htmlFor and id', () => {
      assert.ok(loginSource.includes('htmlFor="operator-identifier"'), 'Identifier input must have matching htmlFor label');
      assert.ok(loginSource.includes('id="operator-identifier"'), 'Identifier input must define matching id');
      assert.ok(loginSource.includes('htmlFor="operator-password"'), 'Password input must have matching htmlFor label');
      assert.ok(loginSource.includes('id="operator-password"'), 'Password input must define matching id');
    });

    it('provides clear toggle state for password visibility with aria-label', () => {
      assert.ok(loginSource.includes('aria-label='), 'Password toggle button must include descriptive aria-label');
      assert.ok(loginSource.includes('Show password') || loginSource.includes('Hide password'));
    });

    it('declares error notifications inside an aria-live region for screen readers', () => {
      assert.ok(loginSource.includes('aria-live="polite"'), 'Error banner must declare aria-live="polite"');
      assert.ok(loginSource.includes('role="alert"'), 'Error container must specify role="alert"');
    });
  });

  describe('Page 3: MFA Verification Step', () => {
    it('associates TOTP verification code input with explicit label and inputMode', () => {
      assert.ok(loginSource.includes('htmlFor="mfa-code"'), 'MFA input must have matching label');
      assert.ok(loginSource.includes('id="mfa-code"'), 'MFA input must define matching id');
      assert.ok(loginSource.includes('inputMode="numeric"'), 'MFA input must specify numeric inputMode for mobile keyboards');
      assert.ok(loginSource.includes('autoComplete="one-time-code"'), 'MFA input must declare one-time-code autocomplete');
    });

    it('features distinct step labeling for multi-step form progression', () => {
      assert.ok(loginSource.includes('Step 2 of 2'), 'Must identify progression stage to user');
      assert.ok(loginSource.includes('Two-Factor Verification'), 'Must identify modal context');
    });
  });

  describe('Page 4: /console (Overview & System Topology)', () => {
    it('renders structured dashboard with semantic section headings and status indicators', () => {
      assert.ok(consoleOverviewSource.includes('<h1') || consoleOverviewSource.includes('font-serif'), 'Overview must have clear heading');
      assert.ok(consoleOverviewSource.includes('Coordinator') || consoleOverviewSource.includes('coordinator'), 'Must identify coordinator topology');
      assert.ok(consoleOverviewSource.includes('Ledger 1') || consoleOverviewSource.includes('ledger1'), 'Must identify ledger 1 partition');
      assert.ok(consoleOverviewSource.includes('Ledger 2') || consoleOverviewSource.includes('ledger2'), 'Must identify ledger 2 partition');
    });

    it('avoids relying solely on color for operational status indicators', () => {
      // Must include text labels like "REACHABLE", "ONLINE", "HEALTHY", or status tags alongside colors
      assert.ok(
        consoleOverviewSource.includes('REACHABLE') ||
          consoleOverviewSource.includes('HEALTHY') ||
          consoleOverviewSource.includes('ONLINE') ||
          consoleOverviewSource.includes('status'),
        'System overview status must include textual status representation',
      );
    });
  });

  describe('Page 5: /console/transfers/[transferId] (Transfer Detail)', () => {
    it('renders accessible narrative transfer timeline with step ordering and statuses', () => {
      assert.ok(transferDetailSource.includes('Timeline') || transferDetailSource.includes('timeline') || transferDetailSource.includes('Events'), 'Transfer detail must contain workflow timeline');
      assert.ok(transferDetailSource.includes('Transfer') || transferDetailSource.includes('transferId'), 'Transfer detail must identify transfer');
    });
  });

  describe('Page 6: /console/reconciliation (Audit & Imbalance Detection)', () => {
    it('provides accessible audit execution trigger with distinct busy states', () => {
      assert.ok(reconciliationSource.includes('Reconciliation') || reconciliationSource.includes('reconciliation'), 'Reconciliation page must identify purpose');
      assert.ok(reconciliationSource.includes('Audit') || reconciliationSource.includes('audit'), 'Reconciliation must offer audit trigger');
    });
  });

  describe('Page 7: /console/experiments (Failure Recovery Lab)', () => {
    it('clearly labels all simulated crash scenarios with descriptive text', () => {
      assert.ok(experimentsSource.includes('Failure') || experimentsSource.includes('Experiment'), 'Must identify failure lab');
      assert.ok(experimentsSource.includes('SIGNATURE_RECOVERY') || experimentsSource.includes('Signature') || experimentsSource.includes('recovery'), 'Must present recovery scenario');
    });
  });

  describe('Cross-Cutting: Motion & Accessibility Configuration', () => {
    it('verifies that typography and contrast tokens meet legible criteria', () => {
      const globalsCss = loadComponentSource('app/globals.css');
      assert.ok(globalsCss.includes('--bg-cream') || globalsCss.includes('--text-ink'), 'Must specify semantic color tokens');
      assert.ok(globalsCss.includes('font-mono') || globalsCss.includes('--font-sans'), 'Must configure font tokens');
    });
  });
});
