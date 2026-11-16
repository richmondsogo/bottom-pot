const os = require('os');
const path = require('path');
const { defineConfig, devices } = require('@playwright/test');

const defaultE2eDbPath = path.join(os.tmpdir(), `bottom-pot-e2e-${process.pid}.sqlite`);
const requestedDbPath = (process.env.PLAYWRIGHT_SQLITE_DB_PATH || process.env.SQLITE_DB_PATH || '').trim();
const resolvedE2eDbPath =
  requestedDbPath && path.resolve(requestedDbPath) !== path.resolve(__dirname, 'data', 'cache.sqlite')
    ? requestedDbPath
    : defaultE2eDbPath;

if (!process.env.PLAYWRIGHT_SQLITE_DB_PATH) {
  process.env.PLAYWRIGHT_SQLITE_DB_PATH = resolvedE2eDbPath;
}

const defaultSubscriptionsFile = path.join(os.tmpdir(), `bottom-pot-e2e-${process.pid}-subscriptions.csv`);
if (!process.env.PLAYWRIGHT_SUBSCRIPTIONS_FILE) {
  process.env.PLAYWRIGHT_SUBSCRIPTIONS_FILE = defaultSubscriptionsFile;
}

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  reporter: [['list']],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:8000',
    channel: 'chrome',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000',
    url: 'http://127.0.0.1:8000/health',
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === '1',
    timeout: 30_000,
    env: {
      ...process.env,
      SQLITE_DB_PATH: process.env.PLAYWRIGHT_SQLITE_DB_PATH,
      SUBSCRIPTIONS_FILE: process.env.PLAYWRIGHT_SUBSCRIPTIONS_FILE,
      MONITORING_ENABLED: 'false',
      SERPER_API_KEY: process.env.SERPER_API_KEY || 'e2e-test-key',
      SERPER_MODE: process.env.SERPER_MODE || 'cache_only',
      ADMIN_PASSWORD: process.env.ADMIN_PASSWORD || 'test-admin-password',
      ADMIN_SESSION_SECRET: process.env.ADMIN_SESSION_SECRET || 'test-admin-session-secret-at-least-32-chars-long',
      RATE_LIMIT_ADMIN_LOGIN: '1000/minute',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome',
      },
    },
  ],
});
