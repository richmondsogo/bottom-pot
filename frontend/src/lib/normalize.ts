import type { JobListing, JobSalary, NormalizedJob } from '../types';

export function formatJobType(value?: string | null): string {
  if (!value) return 'Unknown';
  const map: Record<string, string> = {
    full_time: 'Full time',
    part_time: 'Part time',
    internship: 'Internship',
    contract: 'Contract',
  };
  return map[value] || value.replace(/_/g, ' ');
}

export function formatWorkModel(value?: string | null): string {
  if (!value) return 'Not specified';
  const map: Record<string, string> = {
    remote: 'Remote',
    hybrid: 'Hybrid',
    in_person: 'In-person',
  };
  return map[value] || value.replace(/_/g, ' ');
}

export function formatPostedDate(value?: string | null): string {
  if (!value) return 'Date unavailable';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? 'Date unavailable' : date.toISOString().slice(0, 10);
}

export function formatSalary(salary?: JobSalary): string {
  if (!salary) return 'Not listed';
  if (typeof salary === 'string') return salary.trim() || 'Not listed';
  const currency = salary.currency ? `${salary.currency} ` : '';
  const period = salary.period ? ` / ${salary.period}` : '';
  if (salary.minimum != null && salary.maximum != null) {
    return `${currency}${Number(salary.minimum).toLocaleString()}-${Number(salary.maximum).toLocaleString()}${period}`;
  }
  if (salary.minimum != null) {
    return `${currency}${Number(salary.minimum).toLocaleString()}+${period}`;
  }
  if (salary.maximum != null) {
    return `Up to ${currency}${Number(salary.maximum).toLocaleString()}${period}`;
  }
  return 'Not listed';
}

export function normalizeJob(job: JobListing): NormalizedJob {
  return {
    ...job,
    displayTitle: job.title || 'Untitled role',
    displayLocation: job.location || 'Unknown',
    displaySalary: formatSalary(job.salary),
    displayEmployment: formatJobType(job.employment_type),
    displayLocationType: formatWorkModel(job.work_model),
    displayPostedDate: formatPostedDate(job.posted_at),
  };
}
