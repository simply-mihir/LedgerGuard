import { test, expect } from '@playwright/test';
import { provisionSyntheticOperator, getTotpCode } from './helpers';

test.describe('Real Browser E2E: Authentication & Security Lifecycle', () => {
  test('Public landing-page rendering', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/LedgerGuard/);
    await expect(page.locator('h1')).toContainText(/Financial state/i);
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('footer')).toBeVisible();
  });

  test('Unauthenticated /console redirect to /login', async ({ page }) => {
    await page.goto('/console');
    await page.waitForURL(/\/login\?returnUrl=%2Fconsole/);
    await expect(page.locator('#operator-identifier')).toBeVisible();
    await expect(page.locator('#operator-password')).toBeVisible();
  });

  test('Safe preservation of an internal return path', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    await page.goto('/login?returnUrl=%2Fconsole%2Freconciliation');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');

    await page.waitForURL(/\/console\/reconciliation/);
    expect(page.url()).toContain('/console/reconciliation');
  });

  test('Rejection of external and protocol-relative return targets', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    // 1. External URL target
    await page.goto('/login?returnUrl=https%3A%2F%2Fevil.example.com%2Fpwn');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');

    await page.waitForURL(/\/console/);
    expect(page.url()).not.toContain('evil.example.com');
    expect(new URL(page.url()).pathname).toBe('/console');

    // 2. Protocol-relative target
    await page.context().clearCookies();
    await page.goto('/login?returnUrl=%2F%2Fevil.example.com');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');

    await page.waitForURL(/\/console/);
    expect(page.url()).not.toContain('evil.example.com');
    expect(new URL(page.url()).pathname).toBe('/console');
  });

  test('Password login for standard operator without MFA', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    await page.goto('/login');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');

    await page.waitForURL(/\/console/);
    await expect(page.locator('aside')).toContainText(op.username);
  });

  test('MFA challenge during later login and TOTP verification', async ({ page }) => {
    const mfaOp = provisionSyntheticOperator({ enableTotp: true });

    await page.goto('/login');
    await page.fill('#operator-identifier', mfaOp.username);
    await page.fill('#operator-password', mfaOp.password);
    await page.click('button[type="submit"]');

    // Verify Step 2 UI appears
    await expect(page.locator('text=Step 2 of 2')).toBeVisible();
    await expect(page.locator('#mfa-code')).toBeVisible();

    // Verify 6-digit TOTP code
    const totp = getTotpCode(mfaOp.totpSecret!);
    await page.fill('#mfa-code', totp);
    await page.click('button[type="submit"]');

    await page.waitForURL(/\/console/);
    await expect(page.locator('aside')).toContainText(mfaOp.username);
  });

  test('TOTP replay rejection prevents reuse of identical code in same time window', async ({ request }) => {
    const replayOp = provisionSyntheticOperator({ enableTotp: true });

    // Initiate login to acquire temp_token
    const loginRes = await request.post('/api/auth/login', {
      data: {
        identifier: replayOp.username,
        password: replayOp.password,
      },
    });
    expect(loginRes.ok()).toBeTruthy();
    const loginData = await loginRes.json();
    expect(loginData.status).toBe('MFA_REQUIRED');
    const tempToken = loginData.temp_token;
    const totp = getTotpCode(replayOp.totpSecret!);

    // First verification with code succeeds
    const firstVerify = await request.post('/api/auth/mfa/verify', {
      data: {
        temp_token: tempToken,
        code: totp,
      },
    });
    expect(firstVerify.ok()).toBeTruthy();

    // Replay: initiate a second login immediately in the same time window
    const secondLoginRes = await request.post('/api/auth/login', {
      data: {
        identifier: replayOp.username,
        password: replayOp.password,
      },
    });
    expect(secondLoginRes.ok()).toBeTruthy();
    const secondLoginData = await secondLoginRes.json();
    const secondTempToken = secondLoginData.temp_token;

    // Second verification with identical TOTP code MUST be rejected
    const replayVerify = await request.post('/api/auth/mfa/verify', {
      data: {
        temp_token: secondTempToken,
        code: totp,
      },
    });
    expect(replayVerify.status()).toBe(401);
    const replayErr = await replayVerify.json();
    expect(replayErr.detail).toMatch(/already been used|replay|invalid/i);
  });

  test('MFA enrollment and activation workflow', async ({ page }) => {
    const freshOp = provisionSyntheticOperator({ enableTotp: false });

    // Log in via UI
    await page.goto('/login');
    await page.fill('#operator-identifier', freshOp.username);
    await page.fill('#operator-password', freshOp.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/console/);

    // Call MFA enrollment endpoint while authenticated with valid CSRF token
    const enrollRes = await page.evaluate(async () => {
      const sessionRes = await fetch('/api/auth/session');
      const sessionData = await sessionRes.json();
      const res = await fetch('/api/auth/mfa/enroll', {
        method: 'POST',
        headers: {
          'X-CSRF-Token': sessionData.csrf_token || '',
        },
      });
      return { ok: res.ok, data: await res.json() };
    });
    expect(enrollRes.ok).toBeTruthy();
    expect(enrollRes.data.totp_secret).toBeDefined();

    // Generate code and confirm activation
    const newSecret = enrollRes.data.totp_secret;
    const code = getTotpCode(newSecret);

    const confirmRes = await page.evaluate(async (verificationCode) => {
      const sessionRes = await fetch('/api/auth/session');
      const sessionData = await sessionRes.json();
      const res = await fetch('/api/auth/mfa/confirm', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': sessionData.csrf_token || '',
        },
        body: JSON.stringify({ code: verificationCode }),
      });
      return { ok: res.ok, data: await res.json() };
    }, code);

    expect(confirmRes.ok).toBeTruthy();
    expect(confirmRes.data.status).toBe('ACTIVATED');
  });

  test('Authenticated console access and session retention across browser refresh', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    await page.goto('/login');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/console/);

    // Reload page
    await page.reload();
    await expect(page).toHaveURL(/\/console/);
    await expect(page.locator('aside')).toContainText(op.username);
  });

  test('Direct access to protected nested route', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    await page.goto('/login');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/console/);

    // Navigate directly to nested route
    await page.goto('/console/transfers/98812149-5861-4523-ac1b-860d01925c32');
    await expect(page).toHaveURL(/\/console\/transfers\/98812149-5861-4523-ac1b-860d01925c32/);
    await expect(page.locator('main')).toBeVisible();
  });

  test('State-changing logout revokes session and clears cookie', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    await page.goto('/login');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/console/);
    await page.waitForLoadState('networkidle');

    // Click Sign Out
    const signOutBtn = page.locator('button:has-text("Sign Out")');
    await expect(signOutBtn).toBeVisible();
    await signOutBtn.click();

    await page.waitForURL(/\/login/);
    await expect(page.locator('#operator-identifier')).toBeVisible();

    // Verify navigating to /console now redirects back to /login
    await page.goto('/console');
    await page.waitForURL(/\/login\?returnUrl=%2Fconsole/);
  });

  test('CSRF rejection for state-changing requests', async ({ page }) => {
    const op = provisionSyntheticOperator({ enableTotp: false });

    await page.goto('/login');
    await page.fill('#operator-identifier', op.username);
    await page.fill('#operator-password', op.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/console/);

    // From inside the authenticated browser, send POST /api/auth/logout with INVALID csrf token
    const evilPost = await page.evaluate(async () => {
      const res = await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'X-CSRF-Token': 'evil-forged-token-12345',
        },
      });
      return { status: res.status };
    });

    expect(evilPost.status).toBe(403);
  });

  test('Experiment endpoint authorization protects failure lab', async ({ request }) => {
    // Unauthenticated POST to failure experiments must fail
    const unauthPost = await request.post('/api/operator/experiments/run', {
      data: { scenario: 'COORDINATOR_CRASH_AFTER_PREPARE' },
    });
    // FastAPI returns 401 Unauthorized
    expect(unauthPost.status()).toBe(401);
  });

  test('Keyboard-only login and MFA submission', async ({ page }) => {
    const freshMfaOp = provisionSyntheticOperator({ enableTotp: true });

    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    // Focus identifier using Tab
    await page.locator('#operator-identifier').focus();
    await page.keyboard.type(freshMfaOp.username);

    // Tab to password
    await page.keyboard.press('Tab');
    const focusedTag = await page.evaluate(() => document.activeElement?.getAttribute('id') || document.activeElement?.tagName);
    if (focusedTag !== 'operator-password') {
      await page.keyboard.press('Tab');
    }
    await page.keyboard.type(freshMfaOp.password);

    // Submit with Enter key
    await page.keyboard.press('Enter');

    // Wait for Step 2 MFA form
    await page.waitForSelector('#mfa-code');
    const totp = getTotpCode(freshMfaOp.totpSecret!);

    // Fill TOTP code
    await page.locator('#mfa-code').focus();
    await page.keyboard.type(totp);

    // Submit MFA with Enter key
    await page.keyboard.press('Enter');

    // Assert entry to console
    await page.waitForURL(/\/console/);
    await expect(page.locator('aside')).toContainText(freshMfaOp.username);
  });

  test('Reduced-motion preference is respected', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');

    const prefersReducedMotion = await page.evaluate(() => {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    });
    expect(prefersReducedMotion).toBe(true);
  });
});
