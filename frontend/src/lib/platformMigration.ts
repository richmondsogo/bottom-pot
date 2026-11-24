import { ALL_PLATFORMS } from './constants';

export const CURRENT_PLATFORM_VERSION = '58';

// Historical full inventories retained strictly so prior users with saved full selections
// migrate cleanly to the active platform list (which retires near-zero legacy Serper-only
// engines in Step 58 alongside previously excluded 'polywork', 'rippling', and 'breezy').
export const HISTORICAL_FULL_INVENTORIES: string[][] = [
  // Step 27: initial ATS 16 platforms
  [
    'greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters', 'jobvite',
    'bamboohr', 'recruitee', 'workday', 'taleo', 'polywork', 'breezy',
    'rippling', 'personio', 'pinpointhq', 'teamtailor'
  ],
  // 18 platforms (ATS 16 + jobberman + myjobmag)
  [
    'greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters', 'jobvite',
    'bamboohr', 'recruitee', 'workday', 'taleo', 'polywork', 'breezy',
    'rippling', 'personio', 'pinpointhq', 'teamtailor', 'jobberman', 'myjobmag'
  ],
  // Step 31: 19 platforms (+ hotnigerianjobs)
  [
    'greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters', 'jobvite',
    'bamboohr', 'recruitee', 'workday', 'taleo', 'polywork', 'breezy',
    'rippling', 'personio', 'pinpointhq', 'teamtailor', 'jobberman', 'myjobmag', 'hotnigerianjobs'
  ],
  // Step 32–49: 21 platforms (18 ATS including rejected breezy + 3 Nigerian)
  [
    'greenhouse', 'lever', 'ashby', 'workable', 'bamboohr', 'jobvite',
    'smartrecruiters', 'icims', 'personio', 'teamtailor', 'recruitee', 'breezy',
    'workday', 'taleo', 'jobadder', 'jazzhr', 'avature', 'successfactors',
    'jobberman', 'myjobmag', 'hotnigerianjobs'
  ],
  // Step 50: 20 platforms (17 ATS excluding rejected breezy + 3 Nigerian)
  [
    'greenhouse', 'lever', 'ashby', 'workable', 'bamboohr', 'jobvite',
    'smartrecruiters', 'icims', 'personio', 'teamtailor', 'recruitee',
    'workday', 'taleo', 'jobadder', 'jazzhr', 'avature', 'successfactors',
    'jobberman', 'myjobmag', 'hotnigerianjobs'
  ],
  // Step 51-57: 21 platforms (18 ATS including pinpointhq + 3 Nigerian)
  [
    'greenhouse', 'lever', 'ashby', 'workable', 'bamboohr', 'jobvite',
    'smartrecruiters', 'icims', 'personio', 'teamtailor', 'recruitee',
    'workday', 'taleo', 'jobadder', 'jazzhr', 'avature', 'successfactors',
    'pinpointhq', 'jobberman', 'myjobmag', 'hotnigerianjobs'
  ],
];

export function setsEqual(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false;
  for (const item of a) {
    if (!b.has(item)) return false;
  }
  return true;
}

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
  // Check if stored selection matches a genuine historical full inventory (comparing as sets)
  const storedSet = new Set(stored);
  const currentSet = new Set(currentAllIds);
  const isPriorFullSelection =
    setsEqual(storedSet, currentSet) ||
    HISTORICAL_FULL_INVENTORIES.some((inventory) => setsEqual(storedSet, new Set(inventory)));

  if (isPriorFullSelection) {
    return {
      platforms: currentAllIds,
      version: CURRENT_PLATFORM_VERSION,
      migrated: true,
    };
  }

  // Otherwise, user had an intentional custom subset (e.g. a custom 16-platform set).
  // Preserve their custom subset, keeping only IDs that remain valid.
  const preservedSubset = stored.filter((id) => currentAllIds.includes(id));
  return {
    platforms: preservedSubset,
    version: CURRENT_PLATFORM_VERSION,
    migrated: true,
  };
}
