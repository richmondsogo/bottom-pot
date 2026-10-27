import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  buildShareableSearchUrl,
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
      includeNigerian: true,
      deepScrape: false,
    },
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
      includeNigerian: true,
      deepScrape: false,
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
});
