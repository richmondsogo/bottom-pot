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

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/**
 * Safe, conservative company display name formatter.
 * Inserts spaces into PascalCase/CamelCase names (e.g., HugeInc -> Huge Inc)
 * or converts slugs with hyphens/underscores to Title Case (cloud-nine -> Cloud Nine).
 * Returns the raw name if ambiguous. Never alters the underlying data model.
 */
export function formatCompanyDisplayName(company?: string | null): {
  display: string;
  isModified: boolean;
  raw: string;
} {
  if (!company) {
    return { display: EMPTY_VALUE, isModified: false, raw: '' };
  }
  const raw = company.trim();
  if (!raw) {
    return { display: EMPTY_VALUE, isModified: false, raw: '' };
  }

  // Already contains spaces
  if (raw.includes(' ')) {
    return { display: raw, isModified: false, raw };
  }

  // Handles slugs like cloud-nine, acme_labs
  if (raw.includes('-') || raw.includes('_')) {
    const cleaned = raw
      .replace(/[-_]+/g, ' ')
      .split(' ')
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
      .join(' ');
    return { display: cleaned, isModified: cleaned !== raw, raw };
  }

  // Handles PascalCase / CamelCase like HugeInc, AcmeLabs, OrbitWorks
  const pascalSplit = raw.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2');
  if (pascalSplit !== raw && pascalSplit.trim().length > 0) {
    return { display: pascalSplit, isModified: true, raw };
  }

  return { display: raw, isModified: false, raw };
}

/**
 * Formats posting date with relative Brian-Lovin-style label ("Today", "3d ago", "Oct 15")
 * along with ISO string and formatted full date for tooltip inspection.
 */
export function formatPostingDate(value?: string | null, nowMs = Date.now()): {
  relative: string;
  full: string;
  iso: string;
} {
  if (!value) {
    return { relative: '—', full: 'Date not listed', iso: '' };
  }
  const date = new Date(value);
  const time = date.getTime();
  if (Number.isNaN(time)) {
    return { relative: '—', full: 'Date not listed', iso: '' };
  }

  const iso = date.toISOString();
  const full = date.toLocaleDateString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });

  const nowDate = new Date(nowMs);
  const diffMs = Math.max(0, nowMs - time);
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  let relative = '';
  if (diffDays === 0) {
    relative = 'Today';
  } else if (diffDays < 7) {
    relative = `${diffDays}d ago`;
  } else if (date.getFullYear() === nowDate.getFullYear()) {
    relative = `${MONTH_NAMES[date.getMonth()]} ${date.getDate()}`;
  } else {
    relative = `${MONTH_NAMES[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
  }

  return { relative, full, iso };
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

export function normalizeJob(job: JobListing, nowMs = Date.now()): NormalizedJob {
  const displayTitle = job.title?.trim() || 'Untitled role';
  const displayLocation = job.location?.trim() || EMPTY_VALUE;
  const displaySalary = formatSalary(job.salary, 'table');
  const displayEmployment = formatJobType(job.employment_type, 'table');
  const displayLocationType = formatWorkModel(job.work_model, 'table');
  const displayWorkModel = job.work_model && ['remote', 'hybrid', 'in_person'].includes(job.work_model.toLowerCase())
    ? formatWorkModel(job.work_model, 'table')
    : null;
  const dateInfo = formatPostingDate(job.posted_at, nowMs);
  const companyInfo = formatCompanyDisplayName(job.company);

  return {
    ...job,
    displayTitle,
    displayCompany: companyInfo.display,
    companyIsModified: companyInfo.isModified,
    rawCompany: companyInfo.raw,
    displayLocation,
    displaySalary,
    displayEmployment,
    displayLocationType,
    displayWorkModel,
    displayPostedDate: dateInfo.full,
    relativePostedDate: dateInfo.relative,
    postingDateIso: dateInfo.iso,
    postingDateFull: dateInfo.full,
  };
}
