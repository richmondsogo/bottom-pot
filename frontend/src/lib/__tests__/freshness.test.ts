import { describe, it, expect } from 'vitest';
import {
  FRESH_MAX_DAYS,
  RECENT_MAX_DAYS,
  computeAgeDays,
  formatAgeBadgeLabel,
  getFreshnessRankKey,
  resolveFreshnessTier,
} from '../freshness';
import { normalizeJob } from '../normalize';
import { sortJobs } from '../sort';
import type { JobListing } from '../../types';

const BASE_NOW_MS = Date.UTC(2026, 10, 23, 12, 0, 0);

function isoDaysAgo(days: number): string {
  return new Date(BASE_NOW_MS - days * 86400000).toISOString();
}

function makeListing(id: string, overrides: Partial<JobListing> = {}): JobListing {
  return {
    id,
    title: `Engineer ${id}`,
    company: `Company ${id}`,
    location: 'Remote',
    work_model: 'remote',
    apply_url: `https://example.com/${id}`,
    source_url: `https://example.com/${id}`,
    provider: 'greenhouse',
    data_source: 'api',
    ...overrides,
  };
}

describe('freshness calculation and badges', () => {
  it('enforces exact tier boundaries at 30d and 90d', () => {
    expect(FRESH_MAX_DAYS).toBe(30);
    expect(RECENT_MAX_DAYS).toBe(90);

    expect(resolveFreshnessTier({ posted_at: isoDaysAgo(0) }, BASE_NOW_MS)).toBe('fresh');
    expect(resolveFreshnessTier({ posted_at: isoDaysAgo(30) }, BASE_NOW_MS)).toBe('fresh');
    expect(resolveFreshnessTier({ posted_at: isoDaysAgo(31) }, BASE_NOW_MS)).toBe('recent');
    expect(resolveFreshnessTier({ posted_at: isoDaysAgo(90) }, BASE_NOW_MS)).toBe('recent');
    expect(resolveFreshnessTier({ posted_at: isoDaysAgo(91) }, BASE_NOW_MS)).toBe('stale');
    expect(resolveFreshnessTier({ posted_at: null, first_seen_at: isoDaysAgo(5) }, BASE_NOW_MS)).toBe('unknown');
    expect(resolveFreshnessTier({ posted_at: null, first_seen_at: isoDaysAgo(95) }, BASE_NOW_MS)).toBe('stale');
  });

  it('honors explicit backend evergreen tier and formats visible age badges', () => {
    const evergreenTier = resolveFreshnessTier(
      { freshness: 'evergreen', posted_at: isoDaysAgo(120) },
      BASE_NOW_MS
    );
    expect(evergreenTier).toBe('evergreen');
    expect(formatAgeBadgeLabel(0, 'fresh')).toBe('Today');
    expect(formatAgeBadgeLabel(5, 'fresh')).toBe('5d ago');
    expect(formatAgeBadgeLabel(120, 'evergreen')).toBe('4mo ago · Evergreen');
    expect(formatAgeBadgeLabel(400, 'stale')).toBe('1y ago · Older');
    expect(formatAgeBadgeLabel(null, 'unknown')).toBe('Date unlisted');
    expect(computeAgeDays(null, isoDaysAgo(7), BASE_NOW_MS)).toBe(7);
  });

  it('orders default sort by freshness tier while honoring explicit user sorts', () => {
    const staleJob = normalizeJob(makeListing('stale', { posted_at: isoDaysAgo(150), title: 'Alpha Old' }), BASE_NOW_MS);
    const unknownJob = normalizeJob(makeListing('unknown', { posted_at: null, title: 'Beta Unlisted' }), BASE_NOW_MS);
    const evergreenJob = normalizeJob(makeListing('evergreen', { freshness: 'evergreen', posted_at: isoDaysAgo(180), title: 'Gamma Pipeline' }), BASE_NOW_MS);
    const recentJob = normalizeJob(makeListing('recent', { posted_at: isoDaysAgo(45), title: 'Delta Recent' }), BASE_NOW_MS);
    const freshJob = normalizeJob(makeListing('fresh', { posted_at: isoDaysAgo(2), title: 'Zeta Fresh' }), BASE_NOW_MS);

    expect(getFreshnessRankKey('fresh')).toBeLessThan(getFreshnessRankKey('recent'));
    const defaultOrdered = sortJobs([staleJob, unknownJob, evergreenJob, recentJob, freshJob], null, true);
    expect(defaultOrdered.map((j) => j.id)).toEqual(['fresh', 'recent', 'evergreen', 'unknown', 'stale']);

    const explicitTitleOrdered = sortJobs(defaultOrdered, 'title', true);
    expect(explicitTitleOrdered.map((j) => j.id)).toEqual(['stale', 'unknown', 'recent', 'evergreen', 'fresh']);
  });
});
