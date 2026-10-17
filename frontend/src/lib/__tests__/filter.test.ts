import { describe, it, expect } from 'vitest';
import { filterJobs } from '../filter';
import { normalizeJob } from '../normalize';
import type { JobListing } from '../../types';

describe('filterJobs', () => {
  const sampleJobs: JobListing[] = [
    {
      id: '1',
      provider: 'greenhouse',
      title: 'Senior Backend Engineer',
      company: 'Acme Global',
      location: 'Lagos, Nigeria',
      work_model: 'remote',
      employment_type: 'full_time',
      salary: { minimum: 120000, maximum: 150000 },
      description: 'Go, Kubernetes, microservices.',
      apply_url: 'https://example.com/apply/1',
      source_url: 'https://example.com/job/1',
      data_source: 'ats',
    },
    {
      id: '2',
      provider: 'lever',
      title: 'Product Designer',
      company: 'Orbit Design',
      location: 'London, UK',
      work_model: 'in_person',
      employment_type: 'contract',
      salary: null,
      description: 'Figma, UI systems, user research.',
      apply_url: 'https://example.com/apply/2',
      source_url: 'https://example.com/job/2',
      data_source: 'ats',
    },
    {
      id: '3',
      provider: 'jobberman',
      title: 'DevOps Intern',
      company: 'Cloud Nine Tech',
      location: 'Abuja, Nigeria',
      work_model: 'hybrid',
      employment_type: 'internship',
      salary: 'NGN 200,000 / month',
      description: 'Linux, Docker, CI/CD pipelines.',
      apply_url: 'https://example.com/apply/3',
      source_url: 'https://example.com/job/3',
      data_source: 'ats',
    },
  ];

  const normalized = sampleJobs.map(normalizeJob);

  it('returns all jobs when no filters are set', () => {
    expect(filterJobs(normalized, {})).toHaveLength(3);
  });

  it('filters by search query matching title, company, or description', () => {
    const byTitle = filterJobs(normalized, { searchQuery: 'backend' });
    expect(byTitle).toHaveLength(1);
    expect(byTitle[0].displayTitle).toBe('Senior Backend Engineer');

    const byDesc = filterJobs(normalized, { searchQuery: 'Figma' });
    expect(byDesc).toHaveLength(1);
    expect(byDesc[0].company).toBe('Orbit Design');
  });

  it('filters by provider', () => {
    const greenhouseJobs = filterJobs(normalized, { provider: 'greenhouse' });
    expect(greenhouseJobs).toHaveLength(1);
    expect(greenhouseJobs[0].provider).toBe('greenhouse');
  });

  it('filters by work model', () => {
    const remote = filterJobs(normalized, { workModel: 'remote' });
    expect(remote).toHaveLength(1);
    expect(remote[0].work_model).toBe('remote');

    const hybrid = filterJobs(normalized, { workModel: 'hybrid' });
    expect(hybrid).toHaveLength(1);
    expect(hybrid[0].work_model).toBe('hybrid');
  });

  it('filters by salary only', () => {
    const withSalary = filterJobs(normalized, { salaryOnly: true });
    expect(withSalary).toHaveLength(2);
    expect(withSalary.map((j) => j.id)).toEqual(['1', '3']);
  });

  it('filters by Nigerian boards only', () => {
    const nigerian = filterJobs(normalized, { nigerianOnly: true });
    expect(nigerian).toHaveLength(1);
    expect(nigerian[0].provider).toBe('jobberman');
  });
});
