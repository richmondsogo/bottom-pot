import { describe, it, expect } from 'vitest';
import { migrateStoredPlatforms, CURRENT_PLATFORM_VERSION } from '../platformMigration';
import { ALL_PLATFORMS } from '../constants';

describe('platformMigration', () => {
  const allIds = ALL_PLATFORMS.map((p) => p.id);

  it('initializes fresh user with all current 13 platforms and version 58', () => {
    const result = migrateStoredPlatforms(null, null);
    expect(result.platforms).toEqual(allIds);
    expect(result.platforms.length).toBe(13);
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(CURRENT_PLATFORM_VERSION).toBe('58');
    expect(result.migrated).toBe(true);
  });

  it('preserves explicit select none across page loads', () => {
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

  it('upgrades prior user who had genuine historical 16 platforms selected to 13 active platforms', () => {
    const old16 = [
      'teamtailor', 'lever', 'ashby', 'workable', 'smartrecruiters', 'jobvite',
      'bamboohr', 'recruitee', 'workday', 'taleo', 'polywork', 'breezy',
      'rippling', 'personio', 'pinpointhq', 'greenhouse'
    ];
    const result = migrateStoredPlatforms(old16, null);
    expect(result.platforms).toEqual(allIds);
    expect(result.platforms.length).toBe(13);
    expect(result.platforms).not.toContain('breezy');
    expect(result.platforms).not.toContain('bamboohr');
    expect(result.platforms).toContain('pinpointhq');
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(true);
  });

  it('upgrades prior user who had Step 51 full 21 platforms selected to Step 58 13 platforms', () => {
    const old21Step51 = [
      'greenhouse', 'lever', 'ashby', 'workable', 'bamboohr', 'jobvite',
      'smartrecruiters', 'icims', 'personio', 'teamtailor', 'recruitee',
      'workday', 'taleo', 'jobadder', 'jazzhr', 'avature', 'successfactors',
      'pinpointhq', 'jobberman', 'myjobmag', 'hotnigerianjobs'
    ];
    const result = migrateStoredPlatforms(old21Step51, '51');
    expect(result.platforms).toEqual(allIds);
    expect(result.platforms.length).toBe(13);
    for (const retired of ['bamboohr', 'jobvite', 'icims', 'taleo', 'jobadder', 'jazzhr', 'avature', 'successfactors']) {
      expect(result.platforms).not.toContain(retired);
    }
    expect(result.platforms).toContain('pinpointhq');
    expect(result.platforms).toContain('jobberman');
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(true);
  });

  it('strips retired legacy engines from an intentional custom subset while preserving remaining selections', () => {
    const customSubset = ['ashby', 'workable', 'bamboohr', 'jazzhr', 'jobberman'];
    const result = migrateStoredPlatforms(customSubset, '51');
    expect(result.platforms).toEqual(['ashby', 'workable', 'jobberman']);
    expect(result.platforms).not.toContain('bamboohr');
    expect(result.platforms).not.toContain('jazzhr');
    expect(result.platforms).not.toContain('greenhouse');
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(true);
  });

  it('preserves custom subset when already on current version', () => {
    const customSubset = ['greenhouse', 'ashby', 'jobberman'];
    const result = migrateStoredPlatforms(customSubset, CURRENT_PLATFORM_VERSION);
    expect(result.platforms).toEqual(['greenhouse', 'ashby', 'jobberman']);
    expect(result.version).toBe(CURRENT_PLATFORM_VERSION);
    expect(result.migrated).toBe(false);
  });
});
