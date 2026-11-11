import { describe, it, expect } from 'vitest';
import { sortJobs } from '../sort';
import type { NormalizedJob } from '../../types';

function createJob(id: string, salary: any, overrides: Partial<NormalizedJob> = {}): NormalizedJob {
  return {
    id,
    title: `Role ${id}`,
    displayTitle: `Role ${id}`,
    company: 'Acme',
    displayCompany: 'Acme',
    rawCompany: 'Acme',
    location: 'Remote',
    displayLocation: 'Remote',
    displaySalary: '—',
    displayEmployment: 'Full-time',
    displayLocationType: 'Remote',
    displayWorkModel: 'remote',
    displayEligibility: null,
    displayPostedDate: 'Today',
    relativePostedDate: 'Today',
    postingDateIso: new Date().toISOString(),
    postingDateFull: 'Today',
    apply_url: `https://example.com/${id}`,
    source_url: `https://example.com/${id}`,
    provider: 'greenhouse',
    data_source: 'api',
    salary,
    ...overrides,
  };
}

describe('sortJobs - Structured Salary Sorting', () => {
  it('sorts within same currency and period ascending and descending', () => {
    const jobs = [
      createJob('1', { minimum: 100000, currency: 'USD', period: 'yearly' }),
      createJob('2', { minimum: 50000, currency: 'USD', period: 'yearly' }),
      createJob('3', { minimum: 150000, currency: 'USD', period: 'yearly' }),
    ];

    const asc = sortJobs(jobs, 'salary', true);
    expect(asc.map((j) => j.id)).toEqual(['2', '1', '3']);

    const desc = sortJobs(jobs, 'salary', false);
    expect(desc.map((j) => j.id)).toEqual(['3', '1', '2']);
  });

  it('places unknown, null, and legacy string salaries last in stable order, both asc and desc', () => {
    const jobs = [
      createJob('legacy-str', '$120,000 / yr'), // Old cached string shape
      createJob('valid-1', { minimum: 100000, currency: 'USD', period: 'yearly' }),
      createJob('null-sal', null),
      createJob('valid-2', { minimum: 60000, currency: 'USD', period: 'yearly' }),
      createJob('empty-obj', {}),
    ];

    // Ascending: valid sorted by amount, others last in original relative order
    const asc = sortJobs(jobs, 'salary', true);
    expect(asc.map((j) => j.id)).toEqual(['valid-2', 'valid-1', 'legacy-str', 'null-sal', 'empty-obj']);

    // Descending: valid sorted by amount descending, others STILL last in original relative order
    const desc = sortJobs(jobs, 'salary', false);
    expect(desc.map((j) => j.id)).toEqual(['valid-1', 'valid-2', 'legacy-str', 'null-sal', 'empty-obj']);
  });

  it('never mixes currencies or periods: mixed-group rows sort last in stable order', () => {
    const jobs = [
      createJob('usd-1', { minimum: 100000, currency: 'USD', period: 'yearly' }),
      createJob('ngn-1', { minimum: 5000000, currency: 'NGN', period: 'yearly' }), // Mixed currency
      createJob('usd-hourly', { minimum: 80, currency: 'USD', period: 'hourly' }), // Mixed period
      createJob('usd-2', { minimum: 120000, currency: 'USD', period: 'yearly' }),
      createJob('eur-1', { minimum: 90000, currency: 'EUR', period: 'yearly' }), // Mixed currency
    ];

    // Primary dominant group is USD:yearly (count 2).
    // Mixed rows (ngn-1, usd-hourly, eur-1) are not converted or compared numerically; they go last in stable order.
    const asc = sortJobs(jobs, 'salary', true);
    expect(asc.map((j) => j.id)).toEqual(['usd-1', 'usd-2', 'ngn-1', 'usd-hourly', 'eur-1']);

    const desc = sortJobs(jobs, 'salary', false);
    expect(desc.map((j) => j.id)).toEqual(['usd-2', 'usd-1', 'ngn-1', 'usd-hourly', 'eur-1']);
  });

  it('handles dataset with zero structured salaries without crashing', () => {
    const jobs = [
      createJob('str-1', '$50k'),
      createJob('null-1', null),
      createJob('str-2', 'Competitive'),
    ];

    const asc = sortJobs(jobs, 'salary', true);
    expect(asc.map((j) => j.id)).toEqual(['str-1', 'null-1', 'str-2']);
  });
});
