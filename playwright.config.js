const fs = require('fs');
const os = require('os');
const path = require('path');
const { defineConfig, devices } = require('@playwright/test');

function resolveRealPathPreservingTail(absTargetPath) {
  let current = absTargetPath;
  const tailSegments = [];
  while (!fs.existsSync(current)) {
    const parent = path.dirname(current);
    if (parent === current) {
      return absTargetPath;
    }
    tailSegments.unshift(path.basename(current));
    current = parent;
  }
  const realBase = fs.realpathSync.native ? fs.realpathSync.native(current) : fs.realpathSync(current);
  return tailSegments.length > 0 ? path.join(realBase, ...tailSegments) : realBase;
}

function toComparablePath(absPath) {
  const realPath = path.normalize(resolveRealPathPreservingTail(path.resolve(absPath)));
  return process.platform === 'win32' || process.platform === 'darwin' ? realPath.toLowerCase() : realPath;
}

function isWithinOrEqualDir(candidateComparable, dirComparable) {
  const rel = path.relative(dirComparable, candidateComparable);
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel));
}

function resolveSafeE2eFilePath(rawCandidate, fallbackPath, forbiddenExactPaths, forbiddenDirs) {
  try {
    if (typeof rawCandidate !== 'string') {
      return fallbackPath;
    }
    const trimmed = rawCandidate.trim();
    if (
      !trimmed
      || trimmed.includes('\0')
      || trimmed.toLowerCase() === ':memory:'
      || /^file:/i.test(trimmed)
      || /[\\/]$/.test(trimmed)
    ) {
      return fallbackPath;
    }

    const forbiddenExact = forbiddenExactPaths.map(toComparablePath);
    const forbiddenDirComparables = forbiddenDirs.map(toComparablePath);
    const roots = [process.cwd(), __dirname];
    const resolvedFromCwd = path.resolve(process.cwd(), trimmed);

    for (const root of roots) {
      const candidateAbs = path.resolve(root, trimmed);
      if (fs.existsSync(candidateAbs) && fs.statSync(candidateAbs).isDirectory()) {
        return fallbackPath;
      }
      const comparable = toComparablePath(candidateAbs);
      if (forbiddenExact.includes(comparable)) {
        return fallbackPath;
      }
      if (forbiddenDirComparables.some((dirComp) => isWithinOrEqualDir(comparable, dirComp))) {
        return fallbackPath;
      }
    }

    return resolvedFromCwd;
  } catch {
    return fallbackPath;
  }
}

const operationalDataDir = path.resolve(__dirname, 'data');
const operationalDbPath = path.resolve(operationalDataDir, 'cache.sqlite');
const operationalSubscriptionsPath = path.resolve(__dirname, 'subscriptions.csv');

const defaultE2eDbPath = path.resolve(os.tmpdir(), `bottom-pot-e2e-${process.pid}.sqlite`);
const defaultSubscriptionsFile = path.resolve(os.tmpdir(), `bottom-pot-e2e-${process.pid}-subscriptions.csv`);

const safeE2eDbPath = resolveSafeE2eFilePath(
  process.env.PLAYWRIGHT_SQLITE_DB_PATH,
  defaultE2eDbPath,
  [operationalDbPath],
  [operationalDataDir]
);
const safeSubscriptionsFile = resolveSafeE2eFilePath(
  process.env.PLAYWRIGHT_SUBSCRIPTIONS_FILE,
  defaultSubscriptionsFile,
  [operationalSubscriptionsPath],
  [operationalDataDir]
);

// Fail closed: always overwrite inherited E2E path variables with validated isolated paths.
process.env.PLAYWRIGHT_SQLITE_DB_PATH = safeE2eDbPath;
process.env.PLAYWRIGHT_SUBSCRIPTIONS_FILE = safeSubscriptionsFile;

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
      SQLITE_DB_PATH: safeE2eDbPath,
      PLAYWRIGHT_SQLITE_DB_PATH: safeE2eDbPath,
      SUBSCRIPTIONS_FILE: safeSubscriptionsFile,
      PLAYWRIGHT_SUBSCRIPTIONS_FILE: safeSubscriptionsFile,
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
