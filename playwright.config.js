const { defineConfig, devices } = require('@playwright/test');

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
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: {
      ...process.env,
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
