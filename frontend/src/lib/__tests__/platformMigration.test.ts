import { describe, it, expect } from 'vitest';
import { migrateStoredPlatforms, CURRENT_PLATFORM_VERSION } from '../platformMigration';
import { ALL_PLATFORMS } from '../constants';

describe('platformMigration', () => {
  const allIds = ALL_PLATFORMS.map((p) => p.id);

  it('initializes fresh user with all current platforms and current version', () => {
    const result = migrateStoredPlatforms(null, null);
    expect(result.platforms).toEqual(allIds);
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(true);
  });

  it('preserves explicit select none across page loads', () => {
    // User selected none and it was stored as []
    const result = migrateStoredPlatforms([], CURRENT_PLATFORM_VERSION);
    expect(result.platforms).toEqual([]);
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(false);
  });

  it('preserves select none even if version was unversioned', () => {
    const result = migrateStoredPlatforms([], null);
    expect(result.platforms).toEqual([]);
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(true);
  });

  it('upgrades prior user who had genuine historical 16 platforms selected (regardless of order)', () => {
    const old16 = [
      'teamtailor', 'lever', 'ashby', 'workable', 'smartrecruiters', 'jobvite',
      'bamboohr', 'recruitee', 'workday', 'taleo', 'polywork', 'breezy',
      'rippling', 'personio', 'pinpointhq', 'greenhouse'
    ];
    const result = migrateStoredPlatforms(old16, null);
    // Should now have all 21 platforms, including newly added ones
    expect(result.platforms).toEqual(allIds);
    expect(result.platforms.length).toBe(21);
    expect(result.platforms).toContain('jazzhr');
    expect(result.platforms).toContain('avature');
    expect(result.platforms).toContain('successfactors');
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(true);
  });

  it('upgrades prior user who had all 18 platforms selected', () => {
    const old18 = [
      'greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters', 'jobvite',
      'bamboohr', 'recruitee', 'workday', 'taleo', 'polywork', 'breezy',
      'rippling', 'personio', 'pinpointhq', 'teamtailor', 'jobberman', 'myjobmag'
    ];
    const result = migrateStoredPlatforms(old18, null);
    expect(result.platforms).toEqual(allIds);
    expect(result.platforms.length).toBe(21);
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(true);
  });

  it('upgrades prior user who had all 19 platforms selected from step 31', () => {
    const old19 = [
      'greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters', 'jobvite',
      'bamboohr', 'recruitee', 'workday', 'taleo', 'polywork', 'breezy',
      'rippling', 'personio', 'pinpointhq', 'teamtailor', 'jobberman', 'myjobmag', 'hotnigerianjobs'
    ];
    const result = migrateStoredPlatforms(old19, null);
    expect(result.platforms).toEqual(allIds);
    expect(result.platforms.length).toBe(21);
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(true);
  });

  it('preserves an intentional custom 16-provider selection without expanding to all 21', () => {
    // 16 platforms chosen by user that do NOT match the historical 16 full set
    // (e.g. contains 'jobberman' and 'hotnigerianjobs', but omits 'greenhouse' and 'lever')
    const custom16 = [
      'ashby', 'workable', 'smartrecruiters', 'jobvite', 'bamboohr', 'recruitee',
      'workday', 'taleo', 'breezy', 'personio', 'teamtailor', 'jobberman',
      'myjobmag', 'hotnigerianjobs', 'jazzhr', 'jobadder'
    ];
    expect(custom16.length).toBe(16);

    const result = migrateStoredPlatforms(custom16, null);
    // Must remain the custom selection, NOT upgraded to all 21 platforms!
    expect(result.platforms.length).toBe(16);
    expect(result.platforms).not.toContain('greenhouse');
    expect(result.platforms).not.toContain('lever');
    expect(result.platforms).toContain('jobberman');
    expect(result.platforms).toContain('jazzhr');
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(true);
  });

  it('preserves intentional custom subset without forcing all platforms', () => {
    const customSubset = ['greenhouse', 'lever'];
    const result = migrateStoredPlatforms(customSubset, null);
    expect(result.platforms).toEqual(['greenhouse', 'lever']);
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(true);
  });

  it('preserves custom subset when already on current version', () => {
    const customSubset = ['greenhouse', 'ashby', 'jobberman'];
    const result = migrateStoredPlatforms(customSubset, CURRENT_PLATFORM_VERSION);
    expect(result.platforms).toEqual(['greenhouse', 'ashby', 'jobberman']);
    expect(result.migrated).toBe(false);
  });
});
