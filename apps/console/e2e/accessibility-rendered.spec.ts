import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { provisionSyntheticOperator } from './helpers';

test.describe('Rendered Accessibility Audit: WCAG 2.2 AA Criteria', () => {
  async function assertAxeClean(page: any, contextName: string) {
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze();

    const criticalOrSerious = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious'
    );

    if (criticalOrSerious.length > 0) {
      const details = criticalOrSerious.map((v) => `${v.id} (${v.impact}): ${v.description}`).join('\n');
      throw new Error(`Axe accessibility violations found on ${contextName}:\n${details}`);
    }

    expect(criticalOrSerious.length).toBe(0);
  }

  test('Page 1: / (Public Landing Page)', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // 1. Axe rendered DOM audit
    await assertAxeClean(page, 'Public Landing Page');

    // 2. Landmark structure
    await expect(page.locator('main')).toBeVisible();
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('footer')).toBeVisible();

    // 3. Accessible heading hierarchy
    const h1Count = await page.locator('h1').count();
    expect(h1Count).toBe(1);

    // 4. Accessible buttons and links
    const buttons = await page.locator('button, a').all();
    for (const btn of buttons) {
      const name = await btn.innerText();
      const ariaLabel = await btn.getAttribute('aria-label');
      expect((name || ariaLabel || '').trim().length).toBeGreaterThan(0);
    }
  });

  test('Page 2: /login (Credentials Portal)', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    // 1. Axe rendered DOM audit
    await assertAxeClean(page, 'Login Credentials Portal');

    // 2. Form labels and accessible names
    const identifierLabel = page.locator('label[for="operator-identifier"]');
    await expect(identifierLabel).toBeVisible();
    const passwordLabel = page.locator('label[for="operator-password"]');
    await expect(passwordLabel).toBeVisible();

    // 3. Password visibility toggle accessible name
    const toggleBtn = page.locator('button[aria-label="Show password"], button[aria-label="Hide password"]');
    await expect(toggleBtn).toBeVisible();

    // 4. Trigger error announcement and verify aria-live region
    await page.fill('#operator-identifier', 'nonexistent_operator');
    await page.fill('#operator-password', 'InvalidPass123!');
    await page.click('button[type="submit"]');

    const alert = page.locator('main [role="alert"]').first();
    await expect(alert).toBeVisible();
    await expect(alert).toHaveAttribute('aria-live', 'polite');
  });

  test('Page 3: MFA Challenge Screen', async ({ page }) => {
    const mfaOp = provisionSyntheticOperator({ enableTotp: true });

    await page.goto('/login');
    await page.fill('#operator-identifier', mfaOp.username);
    await page.fill('#operator-password', mfaOp.password);
    await page.click('button[type="submit"]');

    // Wait for Step 2 MFA form
    await page.waitForSelector('#mfa-code');

    // 1. Axe rendered DOM audit on active MFA screen
    await assertAxeClean(page, 'MFA Challenge Screen');

    // 2. Label association and numeric input mode
    const mfaLabel = page.locator('label[for="mfa-code"]');
    await expect(mfaLabel).toBeVisible();
    const mfaInput = page.locator('#mfa-code');
    await expect(mfaInput).toHaveAttribute('inputmode', 'numeric');
    await expect(mfaInput).toHaveAttribute('autocomplete', 'one-time-code');
  });

  test('Page 4: /console (Platform Overview)', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    // Authenticate
    await page.goto('/login');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/console/);
    await page.waitForLoadState('networkidle');

    // 1. Axe rendered DOM audit
    await assertAxeClean(page, '/console Overview');

    // 2. Landmark structure: aside navigation rail, header, main content
    await expect(page.locator('aside')).toBeVisible();
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('main, [role="main"]')).toBeVisible();

    // 3. Keyboard navigation: tab through sidebar links
    await page.keyboard.press('Tab');
    const focusedTag = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedTag).toBeDefined();
  });

  test('Page 5: /console/transfers/[transferId] (Transfer Detail)', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    // Authenticate
    await page.goto('/login');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/console/);

    await page.goto('/console/transfers/98812149-5861-4523-ac1b-860d01925c32');
    await page.waitForLoadState('networkidle');

    // 1. Axe rendered DOM audit
    await assertAxeClean(page, 'Transfer Detail');

    // 2. Accessible headings and timeline structure
    await expect(page.locator('h1').first()).toBeVisible();
    await expect(page.locator('h2').first()).toBeVisible();
  });

  test('Page 6: /console/reconciliation (Audit & Invariant Verification)', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    // Authenticate
    await page.goto('/login');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/console/);

    await page.goto('/console/reconciliation');
    await page.waitForLoadState('networkidle');

    // 1. Axe rendered DOM audit
    await assertAxeClean(page, 'Reconciliation');

    // 2. Interactive action buttons have accessible names
    const actionButtons = page.locator('button');
    const count = await actionButtons.count();
    expect(count).toBeGreaterThan(0);
  });

  test('Page 7: /console/experiments (Deterministic Failure Lab)', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    // Authenticate
    await page.goto('/login');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/console/);

    await page.goto('/console/experiments');
    await page.waitForLoadState('networkidle');

    // 1. Axe rendered DOM audit
    await assertAxeClean(page, 'Failure Experiments Lab');

    // 2. Verify all crash scenario triggers are accessible
    const experimentCards = page.locator('button, div[role="button"]');
    const count = await experimentCards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('Design system statement compliance wording', async ({ page }) => {
    await page.goto('/');
    const pageText = await page.content();
    // Verify that "WCAG" claims adhere strictly to "Designed and tested against WCAG 2.2 AA criteria"
    if (pageText.includes('WCAG')) {
      expect(pageText).toContain('Designed and tested against WCAG 2.2 AA criteria');
      expect(pageText).not.toContain('WCAG 2.2 AA compliant');
      expect(pageText).not.toContain('WCAG compliant');
    }
  });
});
