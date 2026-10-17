import type { JobListing, JobSalary, NormalizedJob } from '../types';

export const EMPTY_VALUE = '—';

/** Check if a job has disclosed compensation */
export function hasSalary(salary?: JobSalary | null): boolean {
  if (!salary) return false;
  if (typeof salary === 'string') {
    const trimmed = salary.trim().toLowerCase();
    return trimmed !== '' && trimmed !== 'not listed' && trimmed !== 'unknown' && trimmed !== '—';
  }
  return salary.minimum != null || salary.maximum != null;
}

/** Check if any job in a list has disclosed compensation (used to auto-hide salary column) */
export function hasAnySalary(jobs: (JobListing | NormalizedJob)[]): boolean {
  return jobs.some((job) => hasSalary(job.salary));
}

export function formatJobType(value?: string | null, mode: 'table' | 'detail' = 'table'): string {
  if (!value) return mode === 'table' ? EMPTY_VALUE : 'Not specified';
  const map: Record<string, string> = {
    full_time: 'Full-time',
    part_time: 'Part-time',
    internship: 'Internship',
    contract: 'Contract',
    temporary: 'Temporary',
  };
  return map[value] || value.replace(/_/g, ' ');
}

export function formatWorkModel(value?: string | null, mode: 'table' | 'detail' = 'table'): string {
  if (!value) return mode === 'table' ? EMPTY_VALUE : 'Not specified';
  const map: Record<string, string> = {
    remote: 'Remote',
    hybrid: 'Hybrid',
    in_person: 'In-person',
  };
  return map[value] || value.replace(/_/g, ' ');
}

export function formatPostedDate(value?: string | null, mode: 'table' | 'detail' = 'table'): string {
  if (!value) return mode === 'table' ? EMPTY_VALUE : 'Date not listed';
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? mode === 'table'
      ? EMPTY_VALUE
      : 'Date not listed'
    : date.toISOString().slice(0, 10);
}

export function formatSalary(salary?: JobSalary | null, mode: 'table' | 'detail' = 'table'): string {
  if (!salary) return mode === 'table' ? EMPTY_VALUE : 'Not disclosed';
  if (typeof salary === 'string') {
    const trimmed = salary.trim();
    if (!trimmed || trimmed === 'Not listed' || trimmed === 'Unknown') {
      return mode === 'table' ? EMPTY_VALUE : 'Not disclosed';
    }
    return trimmed;
  }
  const currency = salary.currency ? `${salary.currency} ` : '';
  const period = salary.period ? ` / ${salary.period}` : '';

  if (salary.minimum != null && salary.maximum != null) {
    return `${currency}${Number(salary.minimum).toLocaleString()} – ${Number(salary.maximum).toLocaleString()}${period}`;
  }
  if (salary.minimum != null) {
    return `${currency}${Number(salary.minimum).toLocaleString()}+${period}`;
  }
  if (salary.maximum != null) {
    return `Up to ${currency}${Number(salary.maximum).toLocaleString()}${period}`;
  }
  return mode === 'table' ? EMPTY_VALUE : 'Not disclosed';
}

export function formatRelativeTime(value?: string | number | null): string {
  if (!value) return '';
  const date = typeof value === 'number' ? new Date(value) : new Date(value);
  const time = date.getTime();
  if (Number.isNaN(time)) return '';

  const now = Date.now();
  const diffSec = Math.max(0, Math.floor((now - time) / 1000));

  if (diffSec < 60) return 'just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  const diffWeeks = Math.floor(diffDays / 7);
  if (diffWeeks < 5) return `${diffWeeks}w ago`;
  const diffMonths = Math.floor(diffDays / 30);
  if (diffMonths < 12) return `${diffMonths}mo ago`;
  const diffYears = Math.floor(diffDays / 365);
  return `${diffYears}y ago`;
}

export function formatFreshness(scrapedAt?: string | null): string {
  if (!scrapedAt) return 'Checked recently';
  const rel = formatRelativeTime(scrapedAt);
  return rel ? `Checked ${rel}` : 'Checked recently';
}

export function extractDomain(url?: string | null): string {
  if (!url) return '';
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

export function normalizeJob(job: JobListing): NormalizedJob {
  const displayTitle = job.title?.trim() || 'Untitled role';
  const displayLocation = job.location?.trim() || EMPTY_VALUE;
  const displaySalary = formatSalary(job.salary, 'table');
  const displayEmployment = formatJobType(job.employment_type, 'table');
  const displayLocationType = formatWorkModel(job.work_model, 'table');
  const displayPostedDate = formatPostedDate(job.posted_at, 'table');
  const relativePostedDate = formatRelativeTime(job.posted_at) || displayPostedDate;

  return {
    ...job,
    displayTitle,
    displayLocation,
    displaySalary,
    displayEmployment,
    displayLocationType,
    displayPostedDate,
    relativePostedDate,
  };
}
