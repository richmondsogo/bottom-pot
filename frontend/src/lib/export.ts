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
    'Posted date',
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
    job.displayPostedDate,
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
    ({ displayTitle, displayLocation, displayEmployment, displayLocationType, displayPostedDate, ...job }) => job
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
