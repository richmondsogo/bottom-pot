import type { NormalizedJob } from '../types';
import { hasSalary } from './normalize';

export interface FilterOptions {
  search?: string;
  searchQuery?: string;
  provider?: string;
  workModel?: string;
  remote?: string;
  employmentType?: string;
  employment?: string;
  salaryOnly?: boolean;
  nigerianOnly?: boolean;
}

const NIGERIAN_SOURCES = new Set(['jobberman', 'myjobmag', 'hotnigerianjobs', 'ngcareers']);

/**
 * Pure job filtering function.
 * Matches keywords across title, company, location, salary, provider, and description.
 */
export function filterJobs(jobs: NormalizedJob[], options: FilterOptions): NormalizedJob[] {
  const query = (options.search || options.searchQuery || '').trim().toLowerCase();
  const provider = options.provider?.trim().toLowerCase() || '';
  const workModel = options.workModel || options.remote || '';
  const employment = options.employment || options.employmentType || '';
  const salaryOnly = !!options.salaryOnly;
  const nigerianOnly = !!options.nigerianOnly;

  if (!query && !provider && !workModel && !employment && !salaryOnly && !nigerianOnly) {
    return jobs;
  }

  return jobs.filter((job) => {
    // 1. Text Search
    if (query) {
      const searchable = [
        job.displayTitle,
        job.company,
        job.displayLocation,
        job.displaySalary,
        job.displayEmployment,
        job.displayLocationType,
        job.provider,
        job.description || '',
      ]
        .join(' ')
        .toLowerCase();

      if (!searchable.includes(query)) {
        return false;
      }
    }

    // 2. Provider Filter
    if (provider && job.provider?.toLowerCase() !== provider) {
      return false;
    }

    // 3. Work Model Filter
    if (workModel) {
      if (workModel === 'remote' && job.work_model !== 'remote') return false;
      if (workModel === 'hybrid' && job.work_model !== 'hybrid') return false;
      if (workModel === 'in_person' && job.work_model !== 'in_person') return false;
      if (workModel === 'onsite' && job.work_model === 'remote') return false;
      if (workModel === 'not_specified' && job.work_model) return false;
    }

    // 4. Employment Type Filter
    if (employment && job.displayEmployment !== employment && job.employment_type !== employment) {
      return false;
    }

    // 5. Salary Filter
    if (salaryOnly && !hasSalary(job.salary)) {
      return false;
    }

    // 6. Nigerian Sources Filter
    if (nigerianOnly) {
      const p = job.provider?.toLowerCase() || '';
      if (!NIGERIAN_SOURCES.has(p)) {
        return false;
      }
    }

    return true;
  });
}
