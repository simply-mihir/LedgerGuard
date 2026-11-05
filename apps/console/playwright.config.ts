import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E Configuration for LedgerGuard Console.
 * Real browser automation testing against running FastAPI backend and Next.js frontend.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // Ensure sequential execution for deterministic auth state
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 45000,
  expect: {
    timeout: 10000,
  },
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://127.0.0.1:3300',
    trace: 'off', // Never persist traces containing sensitive session cookies
    video: 'off',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
  webServer: [
    {
      command: 'cd ../.. && LEDGERGUARD_COOKIE_SECURE=false uv run uvicorn ledgerguard.api.app:app --host 127.0.0.1 --port 8010',
      url: 'http://127.0.0.1:8010/health',
      reuseExistingServer: true,
      timeout: 30000,
    },
    {
      command: 'npm run start',
      url: 'http://127.0.0.1:3300',
      reuseExistingServer: true,
      timeout: 30000,
    },
  ],
});
