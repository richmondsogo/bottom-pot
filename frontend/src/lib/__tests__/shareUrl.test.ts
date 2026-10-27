import { describe, it, expect, afterEach, vi } from 'vitest';
import { buildShareableSearchUrl, type WorkspaceUrlState } from '../urlState';

describe('buildShareableSearchUrl with optional overridePath', () => {
  const originalWindow = globalThis.window;

  const dummyState: WorkspaceUrlState = {
    searchParams: {
      keywords: 'frontend engineer',
      location: 'Lagos',
      workModel: 'remote',
      postAge: '14',
      includeNigerian: true,
      deepScrape: false,
    },
    tableSearch: 'react',
    providerFilter: 'greenhouse',
    remoteFilter: 'remote',
    employmentFilter: 'full_time',
    onlySalaryListed: true,
    onlySavedJobs: false,
  };

  afterEach(() => {
    (globalThis as unknown as { window: unknown }).window = originalWindow;
    vi.restoreAllMocks();
  });

  it('keeps current pathname by default when pathname is /admin', () => {
    (globalThis as unknown as { window: unknown }).window = {
      location: {
        href: 'http://localhost:5173/admin',
        origin: 'http://localhost:5173',
        pathname: '/admin',
        search: '',
      },
    };

    const shareUrl = buildShareableSearchUrl(dummyState);
    expect(shareUrl).toContain('http://localhost:5173/admin?');
    expect(shareUrl).toContain('q=frontend+engineer');
  });

  it('overrides path to /app when overridePath is specified', () => {
    (globalThis as unknown as { window: unknown }).window = {
      location: {
        href: 'http://localhost:5173/admin',
        origin: 'http://localhost:5173',
        pathname: '/admin',
        search: '',
      },
    };

    const shareUrl = buildShareableSearchUrl(dummyState, '/app');
    expect(shareUrl).toContain('http://localhost:5173/app?');
    expect(shareUrl).toContain('q=frontend+engineer');
  });

  it('maps root / to /app by default when on root', () => {
    (globalThis as unknown as { window: unknown }).window = {
      location: {
        href: 'http://localhost:5173/',
        origin: 'http://localhost:5173',
        pathname: '/',
        search: '',
      },
    };

    const shareUrl = buildShareableSearchUrl(dummyState);
    expect(shareUrl).toContain('http://localhost:5173/app?');
  });
});
