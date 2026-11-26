import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  buildShareableSearchUrl,
  clearRecentSearches,
  getRecentSearches,
  readStateFromUrl,
  recordRecentSearch,
  syncStateToUrl,
  type WorkspaceUrlState,
} from '../urlState';

describe('urlState /app canonical path resolution', () => {
  const originalWindow = globalThis.window;
  let replaceStateSpy: any;

  const mockState: WorkspaceUrlState = {
    searchParams: {
      keywords: 'Python Developer',
      location: 'Lagos',
      workModel: 'remote',
      postAge: '14',
    },
    applicantCountry: 'NG',
    eligibilityFilter: 'eligible_and_unknown',
    tableSearch: 'backend',
    providerFilter: 'greenhouse',
    remoteFilter: 'remote',
    employmentFilter: 'full_time',
    onlySalaryListed: true,
    onlySavedJobs: false,
  };

  const emptyState: WorkspaceUrlState = {
    searchParams: {
      keywords: '',
      location: '',
      workModel: 'any',
      postAge: '7',
    },
    tableSearch: '',
    providerFilter: '',
    remoteFilter: '',
    employmentFilter: '',
    onlySalaryListed: false,
    onlySavedJobs: false,
  };

  beforeEach(() => {
    replaceStateSpy = vi.fn();
  });

  afterEach(() => {
    (globalThis as any).window = originalWindow;
    vi.restoreAllMocks();
  });

  describe('buildShareableSearchUrl', () => {
    it('rewrites root / pathname to /app', () => {
      (globalThis as any).window = {
        location: {
          href: 'http://localhost:3000/',
          origin: 'http://localhost:3000',
          pathname: '/',
          search: '',
        },
      };

      const url = buildShareableSearchUrl(mockState);
      const parsed = new URL(url);
      expect(parsed.pathname).toBe('/app');
      expect(parsed.searchParams.get('q')).toBe('Python Developer');
      expect(parsed.searchParams.get('loc')).toBe('Lagos');
      expect(parsed.searchParams.get('wm')).toBe('remote');
    });

    it('rewrites legacy /search pathname to /app', () => {
      (globalThis as any).window = {
        location: {
          href: 'http://localhost:3000/search?q=Python+Developer',
          origin: 'http://localhost:3000',
          pathname: '/search',
          search: '?q=Python+Developer',
        },
      };

      const url = buildShareableSearchUrl(mockState);
      const parsed = new URL(url);
      expect(parsed.pathname).toBe('/app');
      expect(parsed.searchParams.get('q')).toBe('Python Developer');
    });

    it('preserves /app pathname when already on /app', () => {
      (globalThis as any).window = {
        location: {
          href: 'http://localhost:3000/app',
          origin: 'http://localhost:3000',
          pathname: '/app',
          search: '',
        },
      };

      const url = buildShareableSearchUrl(mockState);
      const parsed = new URL(url);
      expect(parsed.pathname).toBe('/app');
    });

    it('serializes and reads back applicantCountry (cc) and eligibilityFilter (elig)', () => {
      (globalThis as any).window = {
        location: {
          href: 'http://localhost:3000/app',
          origin: 'http://localhost:3000',
          pathname: '/app',
          search: '',
        },
      };

      const url = buildShareableSearchUrl(mockState);
      const parsed = new URL(url);
      expect(parsed.searchParams.get('cc')).toBe('NG');
      expect(parsed.searchParams.get('elig')).toBe('eligible_and_unknown');

      (globalThis as any).window = {
        location: {
          href: url,
          origin: 'http://localhost:3000',
          pathname: '/app',
          search: parsed.search,
        },
      };
      const restored = readStateFromUrl();
      expect(restored?.applicantCountry).toBe('NG');
      expect(restored?.eligibilityFilter).toBe('eligible_and_unknown');
    });
  });

  describe('syncStateToUrl', () => {
    it('rewrites root / to /app when syncing non-delivery workspace state', () => {
      (globalThis as any).window = {
        location: {
          href: 'http://localhost:3000/?view=app',
          origin: 'http://localhost:3000',
          pathname: '/',
          search: '?view=app',
        },
        history: {
          replaceState: replaceStateSpy,
        },
      };

      syncStateToUrl('form', emptyState, true);

      expect(replaceStateSpy).toHaveBeenCalledTimes(1);
      expect(replaceStateSpy).toHaveBeenCalledWith(null, '', '/app?view=app');
    });

    it('rewrites legacy /search to /app when syncing non-delivery state', () => {
      (globalThis as any).window = {
        location: {
          href: 'http://localhost:3000/search?view=app',
          origin: 'http://localhost:3000',
          pathname: '/search',
          search: '?view=app',
        },
        history: {
          replaceState: replaceStateSpy,
        },
      };

      syncStateToUrl('form', emptyState, true);

      expect(replaceStateSpy).toHaveBeenCalledTimes(1);
      expect(replaceStateSpy).toHaveBeenCalledWith(null, '', '/app?view=app');
    });

    it('rewrites legacy /search to /app on delivery screen with shareable URL', () => {
      (globalThis as any).window = {
        location: {
          href: 'http://localhost:3000/search?q=Python+Developer',
          origin: 'http://localhost:3000',
          pathname: '/search',
          search: '?q=Python+Developer',
        },
        history: {
          replaceState: replaceStateSpy,
        },
      };

      syncStateToUrl('delivery', mockState, true);

      expect(replaceStateSpy).toHaveBeenCalledTimes(1);
      const updatedPath = replaceStateSpy.mock.calls[0][2];
      expect(updatedPath.startsWith('/app?')).toBe(true);
    });

    it('preserves /app and does not rewrite when already clean', () => {
      (globalThis as any).window = {
        location: {
          href: 'http://localhost:3000/app?view=app',
          origin: 'http://localhost:3000',
          pathname: '/app',
          search: '?view=app',
        },
        history: {
          replaceState: replaceStateSpy,
        },
      };

      syncStateToUrl('form', emptyState, true);

      // Clean URL is /app?view=app, which already matches window.location
      expect(replaceStateSpy).not.toHaveBeenCalled();
    });
  });

  describe('recentSearches localStorage persistence', () => {
    const originalStorage = (globalThis as any).localStorage;
    let store: Map<string, string>;

    beforeEach(() => {
      store = new Map<string, string>();
      (globalThis as any).localStorage = {
        getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
        setItem: (k: string, v: string) => {
          store.set(k, v);
        },
        removeItem: (k: string) => {
          store.delete(k);
        },
        clear: () => {
          store.clear();
        },
      };
    });

    afterEach(() => {
      (globalThis as any).localStorage = originalStorage;
    });

    it('persists, deduplicates case-insensitively, caps at 5 newest-first, and clears recent searches', () => {
      expect(getRecentSearches()).toEqual([]);

      // Blank query is ignored
      expect(
        recordRecentSearch({ keywords: '   ', location: '', workModel: 'any', postAge: '7' })
      ).toEqual([]);

      const queries = ['Backend', 'Frontend', 'Designer', 'DevOps', 'Data Engineer', 'Security'];
      for (const kw of queries) {
        recordRecentSearch({ keywords: kw, location: '', workModel: 'any', postAge: '7' });
      }

      let recent = getRecentSearches();
      expect(recent).toHaveLength(5);
      expect(recent.map((r) => r.keywords)).toEqual([
        'Security',
        'Data Engineer',
        'DevOps',
        'Designer',
        'Frontend',
      ]);

      // Re-recording an existing entry (different case) moves it to the top without duplicating
      recent = recordRecentSearch({
        keywords: 'designer',
        location: '',
        workModel: 'any',
        postAge: '7',
      });
      expect(recent).toHaveLength(5);
      expect(recent.map((r) => r.keywords)).toEqual([
        'designer',
        'Security',
        'Data Engineer',
        'DevOps',
        'Frontend',
      ]);
      expect(JSON.parse(store.get('bp.recentSearches.v1') || '[]')).toHaveLength(5);

      const cleared = clearRecentSearches();
      expect(cleared).toEqual([]);
      expect(getRecentSearches()).toEqual([]);
      expect(store.has('bp.recentSearches.v1')).toBe(false);
    });
  });
});
