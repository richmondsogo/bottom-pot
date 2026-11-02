import type { NormalizedJob, SortField } from '../types';

interface StructuredSalaryInfo {
  currency: string;
  period: string;
  amount: number;
}

/**
 * Extract structured salary metadata.
 * Returns null for legacy string salaries, null/undefined, or objects missing currency/period/positive numeric amount.
 * Never attempts regex string parsing or currency conversion (ADR 0003).
 */
function getStructuredSalaryInfo(job: NormalizedJob): StructuredSalaryInfo | null {
  const sal = job.salary;
  if (!sal || typeof sal !== 'object') {
    return null;
  }

  const currency = typeof sal.currency === 'string' ? sal.currency.trim().toUpperCase() : null;
  const period = typeof sal.period === 'string' ? sal.period.trim().toLowerCase() : null;

  if (!currency || !period) {
    return null;
  }

  let amount: number | null = null;
  if (sal.minimum != null && Number.isFinite(Number(sal.minimum)) && Number(sal.minimum) > 0) {
    amount = Number(sal.minimum);
  } else if (sal.maximum != null && Number.isFinite(Number(sal.maximum)) && Number(sal.maximum) > 0) {
    amount = Number(sal.maximum);
  }

  if (amount == null) {
    return null;
  }

  return { currency, period, amount };
}

function extractDateValue(job: NormalizedJob): number {
  if (!job.posted_at) return 0;
  const t = new Date(job.posted_at).getTime();
  return Number.isNaN(t) ? 0 : t;
}

/**
 * Pure job sorting function.
 * Supports sorting by role title, company, salary, and date.
 * Salary sorting:
 * - Compares amounts ONLY within the same currency and period.
 * - Never mixes currencies or periods in numeric comparison; no currency conversion.
 * - Unknown, legacy string, and mixed-group rows sort last in original stable order, both ascending and descending.
 */
export function sortJobs(
  jobs: NormalizedJob[],
  field: SortField,
  asc: boolean = true
): NormalizedJob[] {
  if (!field) return jobs;

  if (field === 'salary') {
    // 1. Group structured salaries by currency:period to identify the primary comparable group
    const groupCounts = new Map<string, number>();
    const groupFirstSeenIndex = new Map<string, number>();

    jobs.forEach((job, idx) => {
      const info = getStructuredSalaryInfo(job);
      if (info) {
        const key = `${info.currency}:${info.period}`;
        groupCounts.set(key, (groupCounts.get(key) || 0) + 1);
        if (!groupFirstSeenIndex.has(key)) {
          groupFirstSeenIndex.set(key, idx);
        }
      }
    });

    if (groupCounts.size === 0) {
      // No structured salaries available; preserve stable order
      return [...jobs];
    }

    // Find primary comparable group (highest frequency; tie goes to first seen)
    let dominantGroup = '';
    let maxCount = -1;
    let firstSeen = Number.MAX_SAFE_INTEGER;

    for (const [key, count] of groupCounts.entries()) {
      const seenIdx = groupFirstSeenIndex.get(key) ?? Number.MAX_SAFE_INTEGER;
      if (count > maxCount || (count === maxCount && seenIdx < firstSeen)) {
        dominantGroup = key;
        maxCount = count;
        firstSeen = seenIdx;
      }
    }

    // 2. Partition into comparable (dominant group) vs non-comparable (mixed-group + unknown/legacy)
    const comparable: { job: NormalizedJob; amount: number; index: number }[] = [];
    const lastPartition: NormalizedJob[] = [];

    jobs.forEach((job, index) => {
      const info = getStructuredSalaryInfo(job);
      if (info && `${info.currency}:${info.period}` === dominantGroup) {
        comparable.push({ job, amount: info.amount, index });
      } else {
        lastPartition.push(job);
      }
    });

    // 3. Sort comparable partition by amount (stable tie-breaking by original index)
    comparable.sort((a, b) => {
      const diff = asc ? a.amount - b.amount : b.amount - a.amount;
      return diff !== 0 ? diff : a.index - b.index;
    });

    // 4. Return comparable sorted rows followed by non-comparable rows in stable order
    return [...comparable.map((c) => c.job), ...lastPartition];
  }

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
