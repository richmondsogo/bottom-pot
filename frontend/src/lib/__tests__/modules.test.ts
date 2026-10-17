import { describe, it, expect, beforeEach } from 'vitest';
import { sortJobs } from '../sort';
import { isVisited, markVisited, clearVisited, getVisitedCount } from '../visited';
import { readStorage, writeStorage, getCompanyInitials, getCompanyTileColor } from '../storage';
import { generateMockJobs } from '../mock';
import { normalizeJob } from '../normalize';

// Provide in-memory localStorage polyfill for Node.js test environment
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

describe('sortJobs', () => {
  const jobs = [
    {
      id: '1',
      title: 'Zeta Engineer',
      company: 'Beta Corp',
      salary: { minimum: 150000 },
      posted_at: '2026-09-01T00:00:00Z',
    },
    {
      id: '2',
      title: 'Alpha Engineer',
      company: 'Zeta Corp',
      salary: { minimum: 90000 },
      posted_at: '2026-09-10T00:00:00Z',
    },
    {
      id: '3',
      title: 'Beta Engineer',
      company: 'Alpha Corp',
      salary: { minimum: 200000 },
      posted_at: '2026-09-05T00:00:00Z',
    },
  ].map((j) => normalizeJob(j as any));

  it('sorts by title ascending and descending', () => {
    const asc = sortJobs(jobs, 'title', true);
    expect(asc.map((j) => j.displayTitle)).toEqual(['Alpha Engineer', 'Beta Engineer', 'Zeta Engineer']);

    const desc = sortJobs(jobs, 'title', false);
    expect(desc.map((j) => j.displayTitle)).toEqual(['Zeta Engineer', 'Beta Engineer', 'Alpha Engineer']);
  });

  it('sorts by company ascending', () => {
    const asc = sortJobs(jobs, 'company', true);
    expect(asc.map((j) => j.company)).toEqual(['Alpha Corp', 'Beta Corp', 'Zeta Corp']);
  });

  it('sorts by salary', () => {
    const asc = sortJobs(jobs, 'salary', true);
    expect(asc.map((j) => j.id)).toEqual(['2', '1', '3']);
  });

  it('sorts by date', () => {
    const desc = sortJobs(jobs, 'date', false);
    expect(desc.map((j) => j.id)).toEqual(['2', '3', '1']);
  });
});

describe('visited store', () => {
  beforeEach(() => {
    clearVisited();
  });

  it('tracks visited postings reliably', () => {
    expect(isVisited('https://jobs.example/1')).toBe(false);
    expect(getVisitedCount()).toBe(0);

    markVisited('https://jobs.example/1');
    expect(isVisited('https://jobs.example/1')).toBe(true);
    expect(isVisited('https://jobs.example/2')).toBe(false);
    expect(getVisitedCount()).toBe(1);

    clearVisited();
    expect(isVisited('https://jobs.example/1')).toBe(false);
    expect(getVisitedCount()).toBe(0);
  });
});

describe('storage & company monogram tiles', () => {
  it('reads and writes fallback storage values', () => {
    expect(readStorage('test_key_missing', 42)).toBe(42);
    writeStorage('test_key_exists', { name: 'Bottom Pot' });
    expect(readStorage('test_key_exists', null)).toEqual({ name: 'Bottom Pot' });
  });

  it('generates 1-2 uppercase monogram initials', () => {
    expect(getCompanyInitials('Google')).toBe('GO');
    expect(getCompanyInitials('Via Logic LLC')).toBe('VL');
    expect(getCompanyInitials('Stripe')).toBe('ST');
    expect(getCompanyInitials('')).toBe('—');
  });

  it('generates deterministic restrained monogram colors', () => {
    const colorA1 = getCompanyTileColor('Stripe');
    const colorA2 = getCompanyTileColor('Stripe');
    const colorB = getCompanyTileColor('Moniepoint');

    expect(colorA1).toEqual(colorA2);
    expect(colorA1.bg).toMatch(/^#[0-9A-Fa-f]{6}$/);
    expect(colorA1.color).toMatch(/^#[0-9A-Fa-f]{6}$/);
    expect(colorB.bg).toMatch(/^#[0-9A-Fa-f]{6}$/);
  });
});

describe('mock dataset generator', () => {
  it('generates over 150 realistic listings with required edge cases', () => {
    const mockJobs = generateMockJobs();
    expect(mockJobs.length).toBeGreaterThanOrEqual(150);

    // Verify long title edge case
    const longTitleJob = mockJobs.find((j) => j.id === 'edge:long-title:1');
    expect(longTitleJob).toBeDefined();
    expect(longTitleJob!.title.length).toBeGreaterThan(100);

    // Verify Japanese non-Latin script edge case
    const japaneseJob = mockJobs.find((j) => j.id === 'edge:japanese:2');
    expect(japaneseJob).toBeDefined();
    expect(japaneseJob!.title).toContain('シニアソフトウェアエンジニア');

    // Verify odd company casing
    const oddCasing = mockJobs.find((j) => j.company === 'e.e. cummings tech');
    expect(oddCasing).toBeDefined();

    // Verify diverse work models
    expect(mockJobs.some((j) => j.work_model === 'remote')).toBe(true);
    expect(mockJobs.some((j) => j.work_model === 'hybrid')).toBe(true);
    expect(mockJobs.some((j) => j.work_model === 'in_person')).toBe(true);
    expect(mockJobs.some((j) => j.work_model === null)).toBe(true);
  });
});
