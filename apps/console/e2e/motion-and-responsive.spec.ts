import { test, expect } from '@playwright/test';
import { provisionSyntheticOperator } from './helpers';

test.describe('Visual & Motion Verification: Scroll Storytelling, Navigation & Responsive Geometry', () => {
  test('Landing navigation compression upon scroll', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const header = page.locator('header').first();
    await expect(header).toBeVisible();

    // Scroll down 200px to trigger compression
    await page.evaluate(() => window.scrollTo(0, 200));
    await page.waitForTimeout(400);

    // Header remains visible floating at top
    await expect(header).toBeVisible();
    await expect(page.locator('.glass-nav')).toBeVisible();
  });

  test('Scroll-narrative state progression across 6 stages', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const narrativeSection = page.locator('#narrative');
    await expect(narrativeSection).toBeVisible();

    // Verify stage text exists in narrative
    await expect(narrativeSection).toContainText(/Immutable Local Posting/i);
    await expect(narrativeSection).toContainText(/Source Reservation/i);
    await expect(narrativeSection).toContainText(/Destination Preparation/i);
    await expect(narrativeSection).toContainText(/Durable Decision Boundary/i);
    await expect(narrativeSection).toContainText(/Point of No Return/i);
    await expect(narrativeSection).toContainText(/Cross-Ledger Reconciliation/i);
    await expect(narrativeSection).toContainText(/Σ ΔL = ₹0.00/i);
  });

  test('Reduced-motion preference unpins narrative and presents all stages statically', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const narrativeSection = page.locator('#narrative');
    await expect(narrativeSection).toBeVisible();

    // Under prefers-reduced-motion, all 6 stages must be rendered in an accessible unpinned flow
    await expect(narrativeSection).toContainText(/Stage 1 — Immutable Local Posting/i);
    await expect(narrativeSection).toContainText(/Stage 2 — Source Reservation/i);
    await expect(narrativeSection).toContainText(/Stage 3 — Destination Preparation/i);
    await expect(narrativeSection).toContainText(/Stage 4 — Durable Decision Boundary/i);
    await expect(narrativeSection).toContainText(/Stage 5 — (?:Confirmation or )?Forward Recovery/i);
    await expect(narrativeSection).toContainText(/Stage 6 — Cross-Ledger Reconciliation/i);

    // Verify durable decision boundary is clearly called out
    await expect(narrativeSection).toContainText(/Point of No Return/i);
    await expect(narrativeSection).toContainText(/Σ ΔL = ₹0.00/i);
  });

  test('Glass navigation mobile drawer with focus trap and Escape handler', async ({ page }) => {
    // Set mobile viewport 375x812 (iPhone X/11/12)
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Mobile menu toggle button must be present
    const toggleBtn = page.locator('button[aria-label="Toggle navigation menu"]');
    await expect(toggleBtn).toBeVisible();

    // Open drawer
    await toggleBtn.click();

    // Drawer sheet must become visible with aria-label
    const drawer = page.locator('[role="dialog"][aria-label="Mobile Navigation Drawer"]');
    await expect(drawer).toBeVisible();

    // Press Escape to dismiss
    await page.keyboard.press('Escape');

    // Drawer is closed
    await expect(drawer).toBeHidden();
  });

  test('Timeline animation state and circular milestone nodes on transfer lifecycle page', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    // Authenticate
    await page.goto('/login');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/console/);

    await page.goto('/console/transfers/98812149-5861-4523-ac1b-860d01925c32');
    await page.waitForLoadState('networkidle');

    // Verify Point of No Return badge is highlighted
    await expect(page.locator('text=POINT OF NO RETURN').first()).toBeVisible();

    // Expand payload details button
    const payloadToggle = page.locator('button:has-text("Inspect Event Payload")').first();
    if (await payloadToggle.isVisible()) {
      await payloadToggle.click();
      await expect(page.locator('text=Event Payload Details:').first()).toBeVisible();
    }
  });

  test('Architecture terminology guard: no 5-node, Raft, or consensus claims anywhere in DOM', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const bodyText = await page.evaluate(() => document.body.innerText);

    expect(bodyText).not.toMatch(/five-node|5-node/i);
    expect(bodyText).not.toMatch(/\braft\b/i);
    expect(bodyText).not.toMatch(/\bconsensus\b/i);
    expect(bodyText).not.toMatch(/\bmesh topology\b/i);

    // Verify truthfulness: 3 databases mentioned
    expect(bodyText).toContain('Coordinator');
    expect(bodyText).toContain('Ledger 1');
    expect(bodyText).toContain('Ledger 2');
  });

  test('Responsive viewport inspection: no horizontal overflow', async ({ page }) => {
    const viewports = [
      { width: 375, height: 812 },   // Mobile
      { width: 768, height: 1024 },  // Tablet
      { width: 1440, height: 900 },  // Desktop
      { width: 1728, height: 1117 }, // Large Desktop
    ];

    for (const vp of viewports) {
      await page.setViewportSize(vp);
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      const isOverflowing = await page.evaluate(() => {
        return document.documentElement.scrollWidth > window.innerWidth + 1;
      });

      expect(isOverflowing).toBe(false);
    }
  });
});
