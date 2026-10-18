import { describe, it, expect } from 'vitest';
import {
  formatSalary,
  formatJobType,
  formatWorkModel,
  formatRelativeTime,
  hasSalary,
  hasAnySalary,
  extractDomain,
  formatCompanyDisplayName,
  formatPostingDate,
  normalizeJob,
  EMPTY_VALUE,
} from '../normalize';
import type { JobListing } from '../../types';

describe('normalize utilities', () => {
  it('formats salary with minimum and maximum correctly', () => {
    const salary = { minimum: 100000, maximum: 140000, currency: 'USD', period: 'year' };
    expect(formatSalary(salary, 'table')).toBe('USD 100,000 – 140,000 / year');
  });

  it('uses unified empty value "—" for missing salary in table mode, and "Not disclosed" in detail mode', () => {
    expect(formatSalary(null, 'table')).toBe(EMPTY_VALUE);
    expect(formatSalary(null, 'detail')).toBe('Not disclosed');
    expect(formatSalary(undefined, 'table')).toBe(EMPTY_VALUE);
  });

  it('detects disclosed salary accurately with hasSalary and hasAnySalary', () => {
    expect(hasSalary(null)).toBe(false);
    expect(hasSalary('Not listed')).toBe(false);
    expect(hasSalary({ minimum: 50000, maximum: 80000 })).toBe(true);
    expect(hasSalary('NGN 500,000 / month')).toBe(true);

    expect(hasAnySalary([{ salary: null } as any, { salary: 'Unknown' } as any])).toBe(false);
    expect(hasAnySalary([{ salary: null } as any, { salary: { minimum: 75000 } } as any])).toBe(true);
  });

  it('formats work models with unified empty values in table mode', () => {
    expect(formatWorkModel('remote', 'table')).toBe('Remote');
    expect(formatWorkModel('hybrid', 'table')).toBe('Hybrid');
    expect(formatWorkModel('in_person', 'table')).toBe('In-person');
    expect(formatWorkModel(null, 'table')).toBe(EMPTY_VALUE);
    expect(formatWorkModel(null, 'detail')).toBe('Not specified');
  });

  it('formats job types with unified empty values in table mode', () => {
    expect(formatJobType('full_time', 'table')).toBe('Full-time');
    expect(formatJobType('contract', 'table')).toBe('Contract');
    expect(formatJobType(null, 'table')).toBe(EMPTY_VALUE);
    expect(formatJobType(null, 'detail')).toBe('Not specified');
  });

  it('formats relative time accurately', () => {
    const now = Date.now();
    expect(formatRelativeTime(now - 10000)).toBe('just now');
    expect(formatRelativeTime(now - 3600000 * 2)).toBe('2h ago');
    expect(formatRelativeTime(now - 86400000 * 3)).toBe('3d ago');
  });

  it('extracts host domain cleanly', () => {
    expect(extractDomain('https://boards.greenhouse.io/acme/jobs/123')).toBe('boards.greenhouse.io');
    expect(extractDomain('https://www.jobberman.com/listings/123')).toBe('jobberman.com');
    expect(extractDomain('')).toBe('');
  });

  it('normalizes full job listing with fallbacks and clean text', () => {
    const raw: JobListing = {
      id: 'test:1',
      provider: 'greenhouse',
      title: '  Senior Platform Architect  ',
      company: 'Acme Corp',
      location: ' Lagos, Nigeria ',
      salary: null,
      work_model: 'remote',
      employment_type: 'full_time',
      posted_at: '2026-09-15T12:00:00Z',
      apply_url: 'https://example.com/apply',
      source_url: 'https://example.com/job',
      data_source: 'ats',
    };

    const norm = normalizeJob(raw, new Date('2026-09-15T14:00:00Z').getTime());
    expect(norm.displayTitle).toBe('Senior Platform Architect');
    expect(norm.displayLocation).toBe('Lagos, Nigeria');
    expect(norm.displaySalary).toBe(EMPTY_VALUE);
    expect(norm.displayEmployment).toBe('Full-time');
    expect(norm.displayLocationType).toBe('Remote');
    expect(norm.displayWorkModel).toBe('Remote');
    expect(norm.displayCompany).toBe('Acme Corp');
    expect(norm.relativePostedDate).toBe('Today');
  });

  it('safely formats company names without mutating raw data', () => {
    expect(formatCompanyDisplayName('HugeInc')).toEqual({
      display: 'Huge Inc',
      isModified: true,
      raw: 'HugeInc',
    });
    expect(formatCompanyDisplayName('cloud-nine')).toEqual({
      display: 'Cloud Nine',
      isModified: true,
      raw: 'cloud-nine',
    });
    expect(formatCompanyDisplayName('acme_labs')).toEqual({
      display: 'Acme Labs',
      isModified: true,
      raw: 'acme_labs',
    });
    expect(formatCompanyDisplayName('Apple')).toEqual({
      display: 'Apple',
      isModified: false,
      raw: 'Apple',
    });
    expect(formatCompanyDisplayName('Acme Corporation')).toEqual({
      display: 'Acme Corporation',
      isModified: false,
      raw: 'Acme Corporation',
    });
    expect(formatCompanyDisplayName(null)).toEqual({
      display: EMPTY_VALUE,
      isModified: false,
      raw: '',
    });
  });

  it('formats posting dates into relative and ISO labels with a fixed clock', () => {
    const fixedNow = new Date('2026-09-18T12:00:00Z').getTime();
    expect(formatPostingDate('2026-09-18T08:00:00Z', fixedNow).relative).toBe('Today');
    expect(formatPostingDate('2026-09-15T12:00:00Z', fixedNow).relative).toBe('3d ago');
    expect(formatPostingDate('2026-08-10T12:00:00Z', fixedNow).relative).toBe('Aug 10');
    expect(formatPostingDate('2025-10-01T12:00:00Z', fixedNow).relative).toBe('Oct 1, 2025');
    expect(formatPostingDate(null, fixedNow).relative).toBe(EMPTY_VALUE);
  });
});
