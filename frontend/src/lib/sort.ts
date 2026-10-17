import type { NormalizedJob, SortField } from '../types';

function extractNumericSalary(job: NormalizedJob): number {
  if (!job.salary) return -1;
  if (typeof job.salary === 'object') {
    if (job.salary.minimum != null) return Number(job.salary.minimum);
    if (job.salary.maximum != null) return Number(job.salary.maximum);
  }
  if (typeof job.salary === 'string') {
    const match = job.salary.replace(/,/g, '').match(/\d+/);
    if (match) return Number(match[0]);
  }
  return -1;
}

function extractDateValue(job: NormalizedJob): number {
  if (!job.posted_at) return 0;
  const t = new Date(job.posted_at).getTime();
  return Number.isNaN(t) ? 0 : t;
}

/**
 * Pure job sorting function.
 * Supports sorting by role title, company, salary, and date.
 */
export function sortJobs(
  jobs: NormalizedJob[],
  field: SortField,
  asc: boolean = true
): NormalizedJob[] {
  if (!field) return jobs;

  return [...jobs].sort((a, b) => {
    let comparison = 0;

    switch (field) {
      case 'title':
        comparison = a.displayTitle.localeCompare(b.displayTitle, undefined, {
          sensitivity: 'base',
        });
        break;

      case 'company':
        comparison = (a.company || '').localeCompare(b.company || '', undefined, {
          sensitivity: 'base',
        });
        break;

      case 'salary': {
        const valA = extractNumericSalary(a);
        const valB = extractNumericSalary(b);
        comparison = valA - valB;
        break;
      }

      case 'date': {
        const dateA = extractDateValue(a);
        const dateB = extractDateValue(b);
        comparison = dateA - dateB;
        break;
      }

      default:
        comparison = 0;
    }

    return asc ? comparison : -comparison;
  });
}
