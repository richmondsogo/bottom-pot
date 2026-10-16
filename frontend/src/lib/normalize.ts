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

export function normalizeJob(job: JobListing): NormalizedJob {
  return {
    ...job,
    displayTitle: job.title || 'Untitled role',
    displayLocation: job.location || 'Unknown',
    displaySalary: formatSalary(job.salary),
    displayEmployment: formatJobType(job.employment_type),
    displayLocationType: formatWorkModel(job.work_model),
    displayPostedDate: formatPostedDate(job.posted_at),
    relativePostedDate: formatRelativeTime(job.posted_at) || formatPostedDate(job.posted_at),
  };
}
