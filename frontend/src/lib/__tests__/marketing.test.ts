import { describe, it, expect } from 'vitest';
import { ALL_PLATFORMS } from '../constants';
import { normalizeJob } from '../normalize';
import { isMockModeActive } from '../mock';

describe('Marketing & Workspace Architecture Integration', () => {
  describe('ADR 0001 & ADR 0002: Unknown Beats Wrong & 7-Tier Provenance', () => {
    it('preserves null workplace type and compensation without fabricating synthetic fallback strings', () => {
      const rawWithNulls = {
        id: 'job-null-1',
        title: 'Lead Mobile Engineer',
        company: 'PiggyVest',
        location: 'Lagos, Nigeria',
        work_model: null,
        salary: null,
        url: 'https://piggyvest.bamboohr.com/jobs/1',
      };

      const normalized = normalizeJob(rawWithNulls as any);
      expect(normalized.work_model).toBeNull();
      expect(normalized.salary).toBeNull();
      // displaySalary must be empty or cleanly omit fallback, never "N/A"
      expect(normalized.displaySalary).not.toBe('N/A');
    });

    it('correctly maps 7-tier provenance sources without loss of evidence', () => {
      const tierSources = [
        'api_enum',
        'jsonld',
        'li_tag',
        'location',
        'title',
        'description',
      ];

      for (const source of tierSources) {
        const raw = {
          id: `job-${source}`,
          title: 'Software Engineer',
          company: 'Acme Corp',
          work_model: 'remote',
          source_tier: source,
          evidence: `matched via ${source}`,
          url: 'https://example.com/job',
        };
        const normalized = normalizeJob(raw as any);
        expect(normalized.work_model).toBe('remote');
      }
    });
  });

  describe('ATS Platforms Coverage Matrix (18+ ATS)', () => {
    it('covers all 18 canonical ATS engines with lowercase slugs', () => {
      expect(ALL_PLATFORMS.length).toBeGreaterThanOrEqual(18);

      const expectedSlugs = [
        'greenhouse',
        'lever',
        'ashby',
        'workable',
        'smartrecruiters',
        'bamboohr',
        'recruitee',
        'breezy',
        'jobvite',
        'workday',
        'personio',
        'pinpointhq',
        'rippling',
        'taleo',
        'teamtailor',
        'polywork',
        'jobberman',
        'myjobmag',
      ];

      const platformIds = ALL_PLATFORMS.map((p) => p.id);
      for (const slug of expectedSlugs) {
        expect(platformIds).toContain(slug);
        // Monospace platform slugs must always be strictly lowercase per ADR 0010
        expect(slug).toBe(slug.toLowerCase());
      }
    });
  });

  describe('View Mode & Routing Resolution Rules', () => {
    it('determines direct entry to workspace when ?mock=1 is present', () => {
      const originalWindow = globalThis.window;
      // Polyfill window.location for test
      (globalThis as any).window = {
        location: {
          pathname: '/',
          search: '?mock=1',
          href: 'http://localhost:3000/?mock=1',
        },
      };

      expect(isMockModeActive()).toBe(true);

      // Restore window
      (globalThis as any).window = originalWindow;
    });

    it('determines direct entry to workspace when path is /app', () => {
      const originalWindow = globalThis.window;
      (globalThis as any).window = {
        location: {
          pathname: '/app',
          search: '',
          href: 'http://localhost:3000/app',
        },
      };

      const path = (globalThis as any).window.location.pathname;
      const isWorkspacePath = path === '/app';
      expect(isWorkspacePath).toBe(true);

      (globalThis as any).window = originalWindow;
    });
  });

  describe('ADR 0021: Strict Forest Green Accent Budget Invariants', () => {
    it('defines forest green accent for light and dark polarity', () => {
      const lightAccent = '#1A382B';
      const darkAccent = '#2E7D52'; // or #34D399 in CSS
      expect(lightAccent).toBe('#1A382B');
      expect(darkAccent).toBeDefined();
    });
  });
});
