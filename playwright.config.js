const fs = require('fs');
const os = require('os');
const path = require('path');
const { defineConfig, devices } = require('@playwright/test');

function resolveRealPathPreservingTail(absTargetPath) {
  let current = absTargetPath;
  const tailSegments = [];
  while (true) {
    try {
      fs.lstatSync(current);
      break;
    } catch (err) {
      if (!err || err.code !== 'ENOENT') {
        throw err;
      }
      const parent = path.dirname(current);
      if (parent === current) {
        return absTargetPath;
      }
      tailSegments.unshift(path.basename(current));
      current = parent;
    }
  }
  const realBase = fs.realpathSync.native ? fs.realpathSync.native(current) : fs.realpathSync(current);
  return tailSegments.length > 0 ? path.join(realBase, ...tailSegments) : realBase;
}

function resolveCanonicalPathFollowingLinks(rawPath, baseDir = process.cwd(), maxHops = 40) {
  const initialAbs = path.resolve(baseDir, rawPath);
  const initialParsed = path.parse(initialAbs);
  let resolved = initialParsed.root;
  let queue = initialAbs.slice(initialParsed.root.length).split(/[\\/]+/).filter(Boolean);
  let hops = 0;

  while (queue.length > 0) {
    const seg = queue.shift();
    if (seg === '.') {
      continue;
    }
    if (seg === '..') {
      const parent = path.dirname(resolved);
      if (parent !== resolved) {
        resolved = parent;
      }
      continue;
    }

    const candidate = path.join(resolved, seg);
    let st;
    try {
      st = fs.lstatSync(candidate);
    } catch (err) {
      if (err && err.code === 'ENOENT') {
        resolved = candidate;
        continue;
      }
      throw err;
    }

    if (st.isSymbolicLink()) {
      hops += 1;
      if (hops > maxHops) {
        throw new Error('Exceeded maximum symbolic link resolution hops');
      }
      const rawTarget = fs.readlinkSync(candidate);
      const cleanedTarget = rawTarget.replace(/^\\\\\?\\([A-Za-z]:\\)/, '$1');
      const nextTarget = path.isAbsolute(cleanedTarget)
        ? cleanedTarget
        : path.resolve(path.dirname(candidate), cleanedTarget);
      const nextParsed = path.parse(nextTarget);
      resolved = nextParsed.root;
      const nextSegments = nextTarget.slice(nextParsed.root.length).split(/[\\/]+/).filter(Boolean);
      queue = nextSegments.concat(queue);
      continue;
    }

    resolved = candidate;
  }

  return resolveRealPathPreservingTail(resolved);
}

function toComparablePath(rawPath, baseDir = process.cwd()) {
  const realPath = path.normalize(resolveCanonicalPathFollowingLinks(rawPath, baseDir));
  return process.platform === 'win32' || process.platform === 'darwin' ? realPath.toLowerCase() : realPath;
}

function isWithinOrEqualDir(candidateComparable, dirComparable) {
  const rel = path.relative(dirComparable, candidateComparable);
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel));
}

function collectProtectedOperationalPaths(dataDir, baselinePaths) {
  const protectedSet = new Set(baselinePaths);
  try {
    const entries = fs.readdirSync(dataDir, { withFileTypes: true });
    for (const entry of entries) {
      protectedSet.add(path.join(dataDir, entry.name));
    }
  } catch (err) {
    if (!err || err.code !== 'ENOENT') {
      throw err;
    }
  }
  return Array.from(protectedSet);
}

function getBigIntStatOrNull(targetPath) {
  try {
    return fs.statSync(targetPath, { bigint: true });
  } catch (err) {
    if (err && err.code === 'ENOENT') {
      return null;
    }
    throw err;
  }
}

function checkCandidateIdentitySafe(candidatePath, existingProtectedStats) {
  let candStat;
  try {
    candStat = getBigIntStatOrNull(candidatePath);
  } catch {
    return false;
  }
  if (!candStat) {
    return true;
  }
  if (existingProtectedStats.length === 0) {
    return true;
  }
  if (!candStat.dev || candStat.dev <= 0n || !candStat.ino || candStat.ino <= 0n) {
    // Identity cannot be established reliably while protected artifacts exist: fail closed.
    return false;
  }
  for (const opStat of existingProtectedStats) {
    if (!opStat.dev || opStat.dev <= 0n || !opStat.ino || opStat.ino <= 0n) {
      return false;
    }
    if (candStat.dev === opStat.dev && candStat.ino === opStat.ino) {
      return false;
    }
  }
  return true;
}

function validateSafeTempRoot(rawDir, forbiddenDirs) {
  try {
    if (typeof rawDir !== 'string' || !rawDir.trim() || rawDir.includes('\0')) {
      return null;
    }
    const trimmed = rawDir.trim();
    const forbiddenDirComparables = forbiddenDirs.map((d) => toComparablePath(d, __dirname));
    const roots = [process.cwd(), __dirname];
    const resolvedFromCwd = resolveCanonicalPathFollowingLinks(trimmed, process.cwd());

    for (const root of roots) {
      const resolved = resolveCanonicalPathFollowingLinks(trimmed, root);
      const stat = fs.statSync(resolved);
      if (!stat.isDirectory()) {
        return null;
      }
      fs.accessSync(resolved, fs.constants.R_OK | fs.constants.W_OK);
      const comparable = toComparablePath(resolved, root);
      if (forbiddenDirComparables.some((dirComp) => isWithinOrEqualDir(comparable, dirComp))) {
        return null;
      }
    }

    return resolvedFromCwd;
  } catch {
    return null;
  }
}

function resolveSafeTempRoot(forbiddenDirs) {
  const candidates = [os.tmpdir()];
  if (process.platform === 'win32') {
    if (process.env.LOCALAPPDATA) {
      candidates.push(path.join(process.env.LOCALAPPDATA, 'Temp'));
    }
    if (process.env.USERPROFILE) {
      candidates.push(path.join(process.env.USERPROFILE, 'AppData', 'Local', 'Temp'));
    }
    if (process.env.SystemRoot) {
      candidates.push(path.join(process.env.SystemRoot, 'Temp'));
    }
  } else {
    candidates.push('/tmp', '/var/tmp');
  }

  for (const candidate of candidates) {
    const validated = validateSafeTempRoot(candidate, forbiddenDirs);
    if (validated) {
      return validated;
    }
  }

  throw new Error(
    'Playwright E2E isolation failure: unable to find a safe temporary directory outside operational data/.'
  );
}

function validateE2eFilePath(rawCandidate, forbiddenExactPaths, forbiddenDirs) {
  try {
    if (typeof rawCandidate !== 'string') {
      return null;
    }
    const trimmed = rawCandidate.trim();
    if (
      !trimmed
      || trimmed.includes('\0')
      || trimmed.toLowerCase() === ':memory:'
      || /^file:/i.test(trimmed)
      || /[\\/]$/.test(trimmed)
    ) {
      return null;
    }

    const forbiddenResolvedExact = forbiddenExactPaths.map((p) => resolveCanonicalPathFollowingLinks(p, __dirname));
    const existingProtectedStats = [];
    for (const opPath of forbiddenResolvedExact) {
      const st = getBigIntStatOrNull(opPath);
      if (st) {
        existingProtectedStats.push(st);
      }
    }
    const forbiddenExact = forbiddenResolvedExact.map((p) => toComparablePath(p, __dirname));
    const forbiddenDirComparables = forbiddenDirs.map((d) => toComparablePath(d, __dirname));
    const roots = [process.cwd(), __dirname];
    const resolvedFromCwd = resolveCanonicalPathFollowingLinks(trimmed, process.cwd());

    for (const root of roots) {
      const candidateResolved = resolveCanonicalPathFollowingLinks(trimmed, root);
      try {
        if (fs.statSync(candidateResolved).isDirectory()) {
          return null;
        }
      } catch (err) {
        if (err && err.code !== 'ENOENT') {
          return null;
        }
      }
      const comparable = toComparablePath(candidateResolved, root);
      if (forbiddenExact.includes(comparable)) {
        return null;
      }
      if (forbiddenDirComparables.some((dirComp) => isWithinOrEqualDir(comparable, dirComp))) {
        return null;
      }
      if (!checkCandidateIdentitySafe(candidateResolved, existingProtectedStats)) {
        return null;
      }
    }

    return resolvedFromCwd;
  } catch {
    return null;
  }
}

function resolveSafeE2eFilePath(rawCandidate, fallbackPath, forbiddenExactPaths, forbiddenDirs) {
  const validatedCandidate = validateE2eFilePath(rawCandidate, forbiddenExactPaths, forbiddenDirs);
  if (validatedCandidate) {
    return validatedCandidate;
  }
  const validatedFallback = validateE2eFilePath(fallbackPath, forbiddenExactPaths, forbiddenDirs);
  if (validatedFallback) {
    return validatedFallback;
  }
  throw new Error(
    'Playwright E2E isolation failure: both configured and fallback paths failed safety validation.'
  );
}

const operationalDataDir = path.resolve(__dirname, 'data');
const operationalDbPath = path.resolve(operationalDataDir, 'cache.sqlite');
const operationalSubscriptionsPath = path.resolve(__dirname, 'subscriptions.csv');
const protectedOperationalPaths = collectProtectedOperationalPaths(operationalDataDir, [
  operationalDbPath,
  `${operationalDbPath}-wal`,
  `${operationalDbPath}-shm`,
  operationalSubscriptionsPath,
]);

const safeTempRoot = resolveSafeTempRoot([operationalDataDir, __dirname]);
const defaultE2eDbPath = path.resolve(safeTempRoot, `bottom-pot-e2e-${process.pid}.sqlite`);
const defaultSubscriptionsFile = path.resolve(safeTempRoot, `bottom-pot-e2e-${process.pid}-subscriptions.csv`);

const safeE2eDbPath = resolveSafeE2eFilePath(
  process.env.PLAYWRIGHT_SQLITE_DB_PATH,
  defaultE2eDbPath,
  protectedOperationalPaths,
  [operationalDataDir]
);
const safeSubscriptionsFile = resolveSafeE2eFilePath(
  process.env.PLAYWRIGHT_SUBSCRIPTIONS_FILE,
  defaultSubscriptionsFile,
  protectedOperationalPaths,
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
