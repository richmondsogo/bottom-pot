import { describe, it, expect, beforeEach } from 'vitest';
import { matchesJobIdentity, upsertJobBatch } from '../identity';
import {
  findSavedJobEntry,
  isJobSaved,
  toggleSavedJob,
  getSavedJobsMap,
} from '../savedJobs';
import type { JobListing } from '../../types';

// In-memory storage polyfill for Node.js test environment
const memoryStore = new Map<string, string>();
const mockStorage = {
  getItem: (key: string) => memoryStore.get(key) ?? null,
  setItem: (key: string, val: string) => { memoryStore.set(key, String(val)); },
  removeItem: (key: string) => { memoryStore.delete(key); },
  clear: () => { memoryStore.clear(); },
  key: (i: number) => Array.from(memoryStore.keys())[i] ?? null,
  get length() { return memoryStore.size; },
};

Object.defineProperty(globalThis, 'localStorage', {
  value: mockStorage,
  writable: true,
  configurable: true,
});

describe('matchesJobIdentity', () => {
  it('matches on exact id', () => {
    expect(matchesJobIdentity({ id: 'job-1' }, 'job-1')).toBe(true);
    expect(matchesJobIdentity({ id: 'job-1' }, { id: 'job-1' })).toBe(true);
    expect(matchesJobIdentity({ id: 'job-1' }, 'job-2')).toBe(false);
  });

  it('matches when candidate id is in target aliases', () => {
    expect(
      matchesJobIdentity({ id: 'alias-a' }, { id: 'canon-1', aliases: ['alias-a', 'alias-b'] })
    ).toBe(true);
  });

  it('matches when target id is in candidate aliases', () => {
    expect(
      matchesJobIdentity({ id: 'canon-1', aliases: ['alias-a'] }, 'alias-a')
    ).toBe(true);
    expect(
      matchesJobIdentity({ id: 'canon-1', aliases: ['alias-a'] }, { id: 'alias-a' })
    ).toBe(true);
  });

  it('matches when candidate and target share an alias', () => {
    expect(
      matchesJobIdentity(
        { id: 'canon-1', aliases: ['common-alias'] },
        { id: 'canon-2', aliases: ['common-alias', 'other'] }
      )
    ).toBe(true);
  });

  it('returns false when no id or alias intersect', () => {
    expect(
      matchesJobIdentity(
        { id: 'canon-1', aliases: ['a1'] },
        { id: 'canon-2', aliases: ['b1'] }
      )
    ).toBe(false);
  });
});

describe('Saved Jobs with Aliases', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  const baseJob: JobListing = {
    id: 'serper-snippet-1',
    provider: 'greenhouse',
    data_source: 'snippet',
    title: 'Frontend Engineer',
    company: 'Stripe',
    company_slug: 'stripe',
    scraped_at: new Date().toISOString(),
    source_url: 'https://boards.greenhouse.io/stripe/jobs/1',
    apply_url: 'https://boards.greenhouse.io/stripe/jobs/1',
    aliases: ['greenhouse:stripe:1'],
  };

  it('recognizes a saved job when inspected via an alias', () => {
    // User saves the snippet
    toggleSavedJob(baseJob);
    expect(isJobSaved(baseJob.id)).toBe(true);

    // Later, an upgraded record arrives with primary ID 'greenhouse:stripe:1' and alias 'serper-snippet-1'
    const upgradedJob: JobListing = {
      ...baseJob,
      id: 'greenhouse:stripe:1',
      data_source: 'api',
      aliases: ['serper-snippet-1'],
    };

    // Must be recognized as saved via either id or aliases!
    expect(isJobSaved(upgradedJob)).toBe(true);
    expect(isJobSaved('greenhouse:stripe:1')).toBe(true);
    expect(findSavedJobEntry(upgradedJob)?.job.id).toBe('serper-snippet-1');
  });

  it('toggles off a saved job when passed an upgraded aliased record', () => {
    toggleSavedJob(baseJob);
    expect(Object.keys(getSavedJobsMap()).length).toBe(1);

    const upgradedJob: JobListing = {
      ...baseJob,
      id: 'greenhouse:stripe:1',
      aliases: ['serper-snippet-1'],
    };

    // Toggle off using the upgraded record
    const res = toggleSavedJob(upgradedJob);
    expect(res.saved).toBe(false);
    expect(Object.keys(getSavedJobsMap()).length).toBe(0);
  });
});

describe('upsertJobBatch', () => {
  const job1: JobListing = {
    id: 'job-1',
    provider: 'greenhouse',
    data_source: 'snippet',
    title: 'Backend Dev',
    company: 'Acme',
    scraped_at: new Date().toISOString(),
    source_url: 'https://example.com/1',
    apply_url: 'https://example.com/1',
    aliases: ['alias-1'],
  };

  const job2: JobListing = {
    id: 'job-2',
    provider: 'lever',
    data_source: 'api',
    title: 'SRE',
    company: 'Acme',
    scraped_at: new Date().toISOString(),
    source_url: 'https://example.com/2',
    apply_url: 'https://example.com/2',
  };

  it('replaces an existing snippet in-place when upgraded', () => {
    const existing = [job1, job2];

    const upgradedJob1: JobListing = {
      ...job1,
      id: 'greenhouse:acme:1',
      data_source: 'api',
      description: 'Full rich description',
      aliases: ['job-1', 'alias-1'],
    };

    const { results, upgradedCount } = upsertJobBatch(existing, [upgradedJob1]);

    expect(results.length).toBe(2);
    expect(upgradedCount).toBe(1);
    // Index 0 was replaced in-place!
    expect(results[0].data_source).toBe('api');
    expect(results[0].description).toBe('Full rich description');
    // Index 1 is untouched
    expect(results[1].id).toBe('job-2');
  });

  it('appends new jobs that do not match existing', () => {
    const existing = [job1];
    const { results, upgradedCount } = upsertJobBatch(existing, [job2]);

    expect(results.length).toBe(2);
    expect(upgradedCount).toBe(0);
    expect(results[0].id).toBe('job-1');
    expect(results[1].id).toBe('job-2');
  });
});
