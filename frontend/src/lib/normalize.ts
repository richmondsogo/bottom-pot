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
  if (!value) return 'Unknown';
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
  if (job.data_source !== 'snippet') {
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

  const rawTitle = job.title || 'Untitled role';
  const labels = ['Location', 'Employment Type', 'Job Type', 'Location Type'];
  const labelPattern = new RegExp(`(?:${labels.join('|')})\\s*[.:]\\s*`, 'gi');
  const matches = [...rawTitle.matchAll(labelPattern)];
  const details: Record<string, string> = {};

  matches.forEach((match, index) => {
    const lowerLabel = match[0].toLowerCase();
    const label =
      lowerLabel.startsWith('employment') || lowerLabel.startsWith('job type')
        ? 'employmentType'
        : lowerLabel.startsWith('location type')
          ? 'locationType'
          : 'location';
    const nextStart = matches[index + 1]?.index ?? rawTitle.length;
    details[label] = rawTitle.slice((match.index ?? 0) + match[0].length, nextStart).replace(/\.{3,}$/, '').trim();
  });

  const title = matches.length
    ? rawTitle.slice(0, matches[0].index).replace(/[.\s]+$/, '').trim()
    : rawTitle;
  const location = job.location || details.location || 'Unknown';
  const rawWorkModel = job.work_model || details.locationType || '';
  const workModelText = `${rawWorkModel} ${location} ${rawTitle}`.toLowerCase();
  const workModel =
    job.is_remote === true || /remote|work from home/.test(workModelText)
      ? 'Remote'
      : /hybrid/.test(workModelText)
        ? 'Hybrid'
        : job.is_remote === false || /in.?person|on.?site|onsite|office/.test(workModelText)
          ? 'In-person'
          : 'Unknown';
  const rawJobType = job.employment_type || details.employmentType || '';
  const jobTypeText = rawJobType.toLowerCase().replace(/[- ]/g, '_');
  const jobType = /intern/.test(jobTypeText)
    ? 'Internship'
    : /part/.test(jobTypeText)
      ? 'Part time'
      : /contract/.test(jobTypeText)
        ? 'Contract'
        : /full/.test(jobTypeText)
          ? 'Full time'
          : 'Unknown';

  return {
    ...job,
    displayTitle: title || rawTitle,
    displayLocation: location,
    displaySalary: formatSalary(job.salary),
    displayEmployment: jobType,
    displayLocationType: workModel,
    displayPostedDate: formatPostedDate(job.posted_at),
  };
}
