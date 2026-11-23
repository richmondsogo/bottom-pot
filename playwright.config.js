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

function toComparablePath(rawPath, baseDir = process.cwd(), forceCaseInsensitive = false) {
  const realPath = path.normalize(resolveCanonicalPathFollowingLinks(rawPath, baseDir));
  return (forceCaseInsensitive || process.platform === 'win32' || process.platform === 'darwin')
    ? realPath.toLowerCase()
    : realPath;
}

function isWithinOrEqualDir(candidateComparable, dirComparable) {
  const rel = path.relative(dirComparable, candidateComparable);
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel));
}

function normalizeCandidateVariants(rawPath) {
  const variants = [rawPath];
  if (path.sep !== '\\' && rawPath.includes('\\')) {
    const slashVariant = rawPath.replace(/\\/g, '/');
    if (!variants.includes(slashVariant)) {
      variants.push(slashVariant);
    }
  }
  return variants;
}

function getDefaultProductionDataDir() {
  if (process.platform === 'win32') {
    const localAppData = (process.env.LOCALAPPDATA || '').trim();
    const base = localAppData || path.join(os.homedir(), 'AppData', 'Local');
    return path.join(base, 'bottom-pot');
  }
  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', 'bottom-pot');
  }
  const xdgDataHome = (process.env.XDG_DATA_HOME || '').trim();
  const base = xdgDataHome || path.join(os.homedir(), '.local', 'share');
  return path.join(base, 'bottom-pot');
}

function isTempRootOrFilesystemRoot(candidateResolved) {
  try {
    const parsed = path.parse(candidateResolved);
    if (path.normalize(candidateResolved) === path.normalize(parsed.root)) {
      return true;
    }
    const sysTmp = toComparablePath(os.tmpdir(), __dirname);
    const candComp = toComparablePath(candidateResolved, __dirname);
    return isWithinOrEqualDir(sysTmp, candComp);
  } catch {
    return true;
  }
}

function collectProtectedOperationalRoots() {
  const roots = [__dirname];
  const extraRaw = (process.env.BOTTOM_POT_TEST_EXTRA_PROTECTED_ROOT || '').trim();
  if (extraRaw) {
    roots.push(path.resolve(__dirname, extraRaw));
  }
  return roots;
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
    const forbiddenExact = forbiddenResolvedExact.map((p) => toComparablePath(p, __dirname, false));
    const forbiddenExactCi = forbiddenResolvedExact.map((p) => toComparablePath(p, __dirname, true));
    const forbiddenDirComparables = forbiddenDirs.map((d) => toComparablePath(d, __dirname, false));
    const forbiddenDirComparablesCi = forbiddenDirs.map((d) => toComparablePath(d, __dirname, true));
    const roots = [process.cwd(), ...collectProtectedOperationalRoots()];
    const resolvedFromCwd = resolveCanonicalPathFollowingLinks(trimmed, process.cwd());

    for (const variant of normalizeCandidateVariants(trimmed)) {
      for (const root of roots) {
        const candidateResolved = resolveCanonicalPathFollowingLinks(variant, root);
        try {
          if (fs.statSync(candidateResolved).isDirectory()) {
            return null;
          }
        } catch (err) {
          if (err && err.code !== 'ENOENT') {
            return null;
          }
        }
        const comparable = toComparablePath(candidateResolved, root, false);
        const comparableCi = toComparablePath(candidateResolved, root, true);
        if (forbiddenExact.includes(comparable) || forbiddenExactCi.includes(comparableCi)) {
          return null;
        }
        if (
          forbiddenDirComparables.some((dirComp) => isWithinOrEqualDir(comparable, dirComp))
          || forbiddenDirComparablesCi.some((dirComp) => isWithinOrEqualDir(comparableCi, dirComp))
        ) {
          return null;
        }
        if (!checkCandidateIdentitySafe(candidateResolved, existingProtectedStats)) {
          return null;
        }
      }
    }

    return resolvedFromCwd;
  } catch {
    return null;
  }
}

function createUniqueDisposableRunDir(safeRoot, forbiddenDirs) {
  let runDir;
  try {
    runDir = fs.mkdtempSync(path.join(safeRoot, 'bottom-pot-e2e-'));
  } catch (err) {
    throw new Error(`Playwright E2E isolation failure: unable to create disposable directory: ${err.message}`);
  }
  const validatedDir = validateSafeTempRoot(runDir, forbiddenDirs);
  if (!validatedDir) {
    throw new Error('Playwright E2E isolation failure: created disposable directory failed safety validation.');
  }
  const st = fs.lstatSync(validatedDir);
  if (st.isSymbolicLink() || !st.isDirectory()) {
    throw new Error('Playwright E2E isolation failure: disposable directory must be a real directory.');
  }
  return validatedDir;
}

function createVerifiedE2eFilePath(targetPath, forbiddenExactPaths, forbiddenDirs) {
  const validated = validateE2eFilePath(targetPath, forbiddenExactPaths, forbiddenDirs);
  if (!validated) {
    throw new Error(
      'Playwright E2E isolation failure: disposable path failed safety validation.'
    );
  }
  return validated;
}

const protectedRoots = collectProtectedOperationalRoots();
const inheritedDataDir = (process.env.BOTTOM_POT_DATA_DIR || '').trim();
const externalDataCandidates = [getDefaultProductionDataDir()];
if (inheritedDataDir) {
  externalDataCandidates.push(path.resolve(__dirname, inheritedDataDir));
}
const externalDataDirs = [];
for (const candidateDir of externalDataCandidates) {
  try {
    const resolvedDir = resolveCanonicalPathFollowingLinks(candidateDir, __dirname);
    if (!isTempRootOrFilesystemRoot(resolvedDir)) {
      externalDataDirs.push(resolvedDir);
    }
  } catch {
    externalDataDirs.push(path.resolve(__dirname, candidateDir));
  }
}

const repoDataDirs = protectedRoots.map((root) => path.resolve(root, 'data'));
const operationalDataDirs = [...repoDataDirs, ...externalDataDirs];
const operationalDataDir = operationalDataDirs[0];
const protectedOperationalPaths = [
  ...protectedRoots.flatMap((root) => {
    const dataDir = path.resolve(root, 'data');
    const dbPath = path.resolve(dataDir, 'cache.sqlite');
    const subsPath = path.resolve(root, 'subscriptions.csv');
    return collectProtectedOperationalPaths(dataDir, [
      dbPath,
      `${dbPath}-wal`,
      `${dbPath}-shm`,
      path.join(dataDir, 'cache.sqlite-journal'),
      subsPath,
    ]);
  }),
  ...externalDataDirs.flatMap((extDir) => {
    const dbPath = path.resolve(extDir, 'cache.sqlite');
    const subsPath = path.resolve(extDir, 'subscriptions.csv');
    return collectProtectedOperationalPaths(extDir, [
      dbPath,
      `${dbPath}-wal`,
      `${dbPath}-shm`,
      path.join(extDir, 'cache.sqlite-journal'),
      subsPath,
    ]);
  }),
];

const existingProtectedDirs = (process.env.BOTTOM_POT_PROTECTED_DATA_DIRS || '').trim();
const protectedDirsForEnv = [
  ...(existingProtectedDirs ? existingProtectedDirs.split(path.delimiter).filter(Boolean) : []),
  ...(inheritedDataDir ? [inheritedDataDir] : []),
].join(path.delimiter);

const safeTempRoot = resolveSafeTempRoot([...operationalDataDirs, ...protectedRoots]);
const disposableRunDir = createUniqueDisposableRunDir(safeTempRoot, [...operationalDataDirs, ...protectedRoots]);

// Unconditionally own the E2E database and subscriptions paths: ignore and overwrite any inherited values.
const safeE2eDbPath = createVerifiedE2eFilePath(
  path.resolve(disposableRunDir, 'e2e-cache.sqlite'),
  protectedOperationalPaths,
  operationalDataDirs
);
const safeSubscriptionsFile = createVerifiedE2eFilePath(
  path.resolve(disposableRunDir, 'e2e-subscriptions.csv'),
  protectedOperationalPaths,
  operationalDataDirs
);

// Fail closed: always overwrite inherited E2E and backend DB path variables with verified unique paths.
process.env.PLAYWRIGHT_SQLITE_DB_PATH = safeE2eDbPath;
process.env.SQLITE_DB_PATH = safeE2eDbPath;
process.env.PLAYWRIGHT_SUBSCRIPTIONS_FILE = safeSubscriptionsFile;
process.env.SUBSCRIPTIONS_FILE = safeSubscriptionsFile;
process.env.BOTTOM_POT_DATA_DIR = '';
if (protectedDirsForEnv) {
  process.env.BOTTOM_POT_PROTECTED_DATA_DIRS = protectedDirsForEnv;
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
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      ...process.env,
      BOTTOM_POT_DATA_DIR: '',
      ...(protectedDirsForEnv ? { BOTTOM_POT_PROTECTED_DATA_DIRS: protectedDirsForEnv } : {}),
      SQLITE_DB_PATH: safeE2eDbPath,
      PLAYWRIGHT_SQLITE_DB_PATH: safeE2eDbPath,
      SUBSCRIPTIONS_FILE: safeSubscriptionsFile,
      PLAYWRIGHT_SUBSCRIPTIONS_FILE: safeSubscriptionsFile,
      BOTTOM_POT_TEST_MODE: '1',
      BOTTOM_POT_ALLOW_OPERATIONAL_DB: '0',
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
