import { ALL_PLATFORMS } from './constants';

export const CURRENT_PLATFORM_VERSION = '32';

// Known prior full platform counts:
// Step 31 had 19 platforms. Step 27 had 16 platforms.
const PRIOR_FULL_COUNTS = new Set([16, 17, 18, 19, 20]);

export interface MigrationResult {
  platforms: string[];
  version: string;
  migrated: boolean;
}

export function migrateStoredPlatforms(
  stored: string[] | null,
  storedVersion: string | null,
  allPlatformList: Array<{ id: string }> = ALL_PLATFORMS
): MigrationResult {
  const currentAllIds = allPlatformList.map((p) => p.id);

  // 1. Fresh user: no stored value at all
  if (stored === null) {
    return {
      platforms: currentAllIds,
      version: CURRENT_PLATFORM_VERSION,
      migrated: true,
    };
  }

  // 2. User explicitly selected "none" (stored is empty array)
  if (Array.isArray(stored) && stored.length === 0) {
    return {
      platforms: [],
      version: CURRENT_PLATFORM_VERSION,
      migrated: storedVersion !== CURRENT_PLATFORM_VERSION,
    };
  }

  // 3. User is already on current version
  if (storedVersion === CURRENT_PLATFORM_VERSION) {
    const valid = stored.filter((id) => currentAllIds.includes(id));
    return {
      platforms: valid,
      version: CURRENT_PLATFORM_VERSION,
      migrated: false,
    };
  }

  // 4. User is on an older version or unversioned:
  // If the user previously had "all platforms" selected (matched prior full count or all current IDs),
  // upgrade them to all current platforms so they receive newly added platforms.
  const isPriorFullSelection = PRIOR_FULL_COUNTS.has(stored.length) || stored.length >= currentAllIds.length;
  if (isPriorFullSelection) {
    return {
      platforms: currentAllIds,
      version: CURRENT_PLATFORM_VERSION,
      migrated: true,
    };
  }

  // Otherwise, user had an intentional custom subset (e.g. ['greenhouse', 'lever']).
  // Preserve their custom subset, keeping only IDs that remain valid.
  const preservedSubset = stored.filter((id) => currentAllIds.includes(id));
  return {
    platforms: preservedSubset,
    version: CURRENT_PLATFORM_VERSION,
    migrated: true,
  };
}
