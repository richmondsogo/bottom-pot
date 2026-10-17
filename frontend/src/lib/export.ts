import type { NormalizedJob } from '../types';

function csvValue(value: unknown): string {
  const escaped = String(value ?? '').replaceAll('"', '""');
  return `"${escaped}"`;
}

export function downloadCsv(jobs: NormalizedJob[], keywords: string) {
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
  const csv = [header, ...rows].map((row) => row.map(csvValue).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  const slug = keywords.toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'bottom-pot';
  link.download = `${slug}-results.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export function downloadJson(jobs: NormalizedJob[], keywords: string) {
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
  const json = JSON.stringify(cleanJobs, null, 2);
  const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  const slug = keywords.toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'bottom-pot';
  link.download = `${slug}-results.json`;
  link.click();
  URL.revokeObjectURL(url);
}
