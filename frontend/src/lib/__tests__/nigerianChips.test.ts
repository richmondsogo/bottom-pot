import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { NIGERIAN_PLATFORM_IDS, ALL_PLATFORMS } from '../constants';
import {
  applyNgToPlatforms,
  areAllNigerianSelected,
  toggleNigerianPlatforms,
} from '../nigerianPlatforms';
import { buildShareableSearchUrl } from '../urlState';
import { readStorage, writeStorage } from '../storage';

describe('Nigerian platforms derivation and toggle logic', () => {
  const originalWindow = globalThis.window;
  const originalLocalStorage = globalThis.localStorage;

  const allIds = ALL_PLATFORMS.map((p) => p.id);
  const atsOnly = allIds.filter((id) => !NIGERIAN_PLATFORM_IDS.includes(id as any));

  let store: Record<string, string> = {};

  beforeEach(() => {
    store = {};
    (globalThis as any).localStorage = {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, val: string) => {
        store[key] = val;
      },
      removeItem: (key: string) => {
        delete store[key];
      },
      clear: () => {
        store = {};
      },
    };

    (globalThis as any).window = {
      location: {
        href: 'http://localhost:5173/app',
        origin: 'http://localhost:5173',
        pathname: '/app',
        search: '',
      },
    };
  });

  afterEach(() => {
    (globalThis as any).window = originalWindow;
    (globalThis as any).localStorage = originalLocalStorage;
    vi.restoreAllMocks();
  });

  it('correctly derives whether all Nigerian platforms are selected', () => {

    expect(areAllNigerianSelected(allIds)).toBe(true);
    expect(areAllNigerianSelected(atsOnly)).toBe(false);

    // Only Jobberman and MyJobMag (missing HotNigerianJobs) -> false
    const partial = [...atsOnly, 'jobberman', 'myjobmag'];
    expect(areAllNigerianSelected(partial)).toBe(false);

    // Adding hotnigerianjobs -> true
    expect(areAllNigerianSelected([...partial, 'hotnigerianjobs'])).toBe(true);
  });

  it('toggles all Nigerian platforms on and off', () => {
    // When unchecked, turning it on adds all missing Nigerian IDs
    const added = toggleNigerianPlatforms(atsOnly, true);
    for (const id of NIGERIAN_PLATFORM_IDS) {
      expect(added).toContain(id);
    }

    // When checked, turning it off removes all Nigerian IDs
    const cleared = toggleNigerianPlatforms(added, false);
    for (const id of NIGERIAN_PLATFORM_IDS) {
      expect(cleared).not.toContain(id);
    }
  });

  it('applies URL ng parameter rules accurately', () => {
    // ng=null (absent): leaves saved selection untouched
    expect(applyNgToPlatforms(atsOnly, null)).toEqual(atsOnly);
    expect(applyNgToPlatforms(allIds, null)).toEqual(allIds);

    // ng=0: removes all Nigerian chips
    const withoutNg = applyNgToPlatforms(allIds, '0');
    for (const id of NIGERIAN_PLATFORM_IDS) {
      expect(withoutNg).not.toContain(id);
    }

    // ng=1: adds all three only if none is selected
    const fromAtsOnly = applyNgToPlatforms(atsOnly, '1');
    for (const id of NIGERIAN_PLATFORM_IDS) {
      expect(fromAtsOnly).toContain(id);
    }

    // ng=1: if one was already selected (e.g. jobberman), leaves existing untouched
    const partial = ['jobberman', 'greenhouse'];
    const fromPartial = applyNgToPlatforms(partial, '1');
    expect(fromPartial).toEqual(partial);
  });

  it('safely loads old stored blobs containing includeNigerian without error', () => {
    // Simulate legacy localStorage blob
    const legacySearchParams = {
      keywords: 'Software Engineer',
      location: 'Lagos',
      workModel: 'remote',
      postAge: '14',
      includeNigerian: true,
      deepScrape: false,
    };
    writeStorage('bp.legacyTest', legacySearchParams);

    const loaded = readStorage<any>('bp.legacyTest', {});
    expect(loaded.keywords).toBe('Software Engineer');
    // Legacy field may exist on parsed JSON but does not break the app
    expect(loaded.includeNigerian).toBe(true);
  });

  it('buildShareableSearchUrl writes ng derived from selectedPlatforms', () => {
    const mockStateWithNg = {
      searchParams: {
        keywords: 'Frontend',
        location: '',
        workModel: 'any',
        postAge: '7',
        deepScrape: false,
      },
      selectedPlatforms: allIds,
      tableSearch: '',
      providerFilter: '',
      remoteFilter: '',
      employmentFilter: '',
      onlySalaryListed: false,
      onlySavedJobs: false,
    };

    const urlWith = buildShareableSearchUrl(mockStateWithNg as any);
    expect(urlWith).toContain('ng=1');

    const mockStateWithoutNg = {
      ...mockStateWithNg,
      selectedPlatforms: atsOnly,
    };
    const urlWithout = buildShareableSearchUrl(mockStateWithoutNg as any);
    expect(urlWithout).toContain('ng=0');
  });
});
