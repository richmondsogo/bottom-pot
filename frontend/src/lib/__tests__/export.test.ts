import { describe, it, expect } from 'vitest';
import { buildCsv, buildJson } from '../export';
import type { NormalizedJob } from '../../types';

// Literal copy of the old pre-step-14 export logic to prove admin parity
function oldCsvValue(value: unknown): string {
  const escaped = String(value ?? '').replaceAll('"', '""');
  return `"${escaped}"`;
}

function oldBuildCsv(jobs: NormalizedJob[]): string {
  const header = [
    'Job title',
    'Company',
    'Location',
    'Salary',
    'Job type',
    'Work model',
    'Work model source',
    'Work model evidence',
    'Raw workplace type',
    'Posted date',
    'Scraped at',
    'Description OK',
    'Provider',
    'Apply URL',
  ];
  const rows = jobs.map((job) => [
    job.displayTitle,
    job.company,
    job.displayLocation,
    job.displaySalary,
    job.displayEmployment,
    job.displayLocationType,
    job.work_model_source ?? '',
    job.work_model_evidence ?? '',
    job.raw_workplace_type ?? '',
    job.displayPostedDate,
    job.scraped_at ?? '',
    job.description_ok != null ? (job.description_ok ? 'true' : 'false') : '',
    job.provider,
    job.apply_url,
  ]);
  return [header, ...rows].map((row) => row.map(oldCsvValue).join(',')).join('\n');
}

function oldBuildJson(jobs: NormalizedJob[]): string {
  const cleanJobs = jobs.map(
    ({
      displayTitle: _displayTitle,
      displayLocation: _displayLocation,
      displayEmployment: _displayEmployment,
      displayLocationType: _displayLocationType,
      displayPostedDate: _displayPostedDate,
      relativePostedDate: _relativePostedDate,
      ...job
    }) => ({
      ...job,
      work_model_source: job.work_model_source ?? null,
      work_model_evidence: job.work_model_evidence ?? null,
      raw_workplace_type: job.raw_workplace_type ?? null,
      description_ok: job.description_ok ?? null,
      scraped_at: job.scraped_at ?? null,
    })
  );
  return JSON.stringify(cleanJobs, null, 2);
}

const mockJob: NormalizedJob = {
  id: 'greenhouse:acme:1',
  provider: 'greenhouse',
  data_source: 'api',
  title: 'Lead Architect',
  company: 'Acme Corp',
  company_slug: 'acme-corp',
  displayTitle: 'Lead Architect',
  displayCompany: 'Acme Corp',
  companyIsModified: false,
  rawCompany: 'Acme Corp',
  location: 'Lagos, Nigeria',
  displayLocation: 'Lagos, Nigeria',
  salary: { minimum: 120000, maximum: 150000, currency: 'USD', period: 'year' },
  displaySalary: 'USD 120,000 – 150,000 / year',
  employment_type: 'full_time',
  displayEmployment: 'Full-time',
  work_model: 'remote',
  displayLocationType: 'Remote',
  displayWorkModel: 'Remote',
  work_model_source: 'jsonld',
  work_model_evidence: '100% remote position',
  raw_workplace_type: 'TELECOMMUTE',
  posted_at: '2026-10-15T00:00:00Z',
  displayPostedDate: 'Thu, Oct 15, 2026',
  relativePostedDate: 'Oct 15',
  postingDateIso: '2026-10-15T00:00:00.000Z',
  postingDateFull: 'Thu, Oct 15, 2026',
  scraped_at: '2026-10-20T10:00:00Z',
  description: 'Role overview',
  description_ok: true,
  apply_url: 'https://boards.greenhouse.io/acme/jobs/1',
  source_url: 'https://serper.dev/search/1',
  query_used: 'site:boards.greenhouse.io Lead Architect',
  ats_source: 'greenhouse',
};

describe('export builders', () => {
  it('buildCsv in admin mode is byte-identical to pre-step-14 logic', () => {
    const adminOutput = buildCsv([mockJob], 'admin');
    const oldOutput = oldBuildCsv([mockJob]);
    expect(adminOutput).toBe(oldOutput);
  });

  it('buildJson in admin mode is byte-identical to pre-step-14 logic', () => {
    const adminOutput = buildJson([mockJob], 'admin');
    const oldOutput = oldBuildJson([mockJob]);
    expect(adminOutput).toBe(oldOutput);
  });

  it('buildCsv in user mode contains exactly 9 columns and preserves apply_url', () => {
    const userOutput = buildCsv([mockJob], 'user');
    const lines = userOutput.split('\n');
    expect(lines.length).toBe(2);

    const headerCols = JSON.parse('[' + lines[0] + ']');
    expect(headerCols).toEqual([
      'Job title',
      'Company',
      'Location',
      'Salary',
      'Job type',
      'Work model',
      'Posted date',
      'Provider',
      'Apply URL',
    ]);

    const dataCols = JSON.parse('[' + lines[1] + ']');
    expect(dataCols).toEqual([
      'Lead Architect',
      'Acme Corp',
      'Lagos, Nigeria',
      'USD 120,000 – 150,000 / year',
      'Full-time',
      'Remote',
      'Thu, Oct 15, 2026',
      'greenhouse',
      'https://boards.greenhouse.io/acme/jobs/1',
    ]);
  });

  it('buildJson in user mode strips internal debug keys and preserves apply_url', () => {
    const userJson = buildJson([mockJob], 'user');
    const parsed = JSON.parse(userJson);
    expect(parsed.length).toBe(1);
    const job = parsed[0];

    // Preserved fields
    expect(job.id).toBe('greenhouse:acme:1');
    expect(job.title).toBe('Lead Architect');
    expect(job.company).toBe('Acme Corp');
    expect(job.apply_url).toBe('https://boards.greenhouse.io/acme/jobs/1');
    expect(job.location).toBe('Lagos, Nigeria');
    expect(job.work_model).toBe('remote');

    // Stripped fields must not exist on user JSON
    expect(job.work_model_source).toBeUndefined();
    expect(job.work_model_evidence).toBeUndefined();
    expect(job.raw_workplace_type).toBeUndefined();
    expect(job.data_source).toBeUndefined();
    expect(job.source_url).toBeUndefined();
    expect(job.query_used).toBeUndefined();
    expect(job.scraped_at).toBeUndefined();
    expect(job.description_ok).toBeUndefined();
  });
});
