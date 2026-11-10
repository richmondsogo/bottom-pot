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

  it('upgrades prior user who had all old platforms selected (16 platforms)', () => {
    const old16 = [
      'greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters', 'jobvite',
      'bamboohr', 'recruitee', 'workday', 'taleo', 'polywork', 'breezy',
      'rippling', 'personio', 'pinpointhq', 'teamtailor'
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
