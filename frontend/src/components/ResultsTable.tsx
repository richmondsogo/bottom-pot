import React from 'react';
import type { NormalizedJob, SortField } from '../types';
import { getCompanyInitials, getCompanyTileColor } from '../lib/storage';
import { isVisited } from '../lib/visited';
import { ArrowUp, ArrowDown, ArrowUpDown, ArrowUpRight } from 'lucide-react';
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from './ui/tooltip';

interface ResultsTableProps {
  jobs: NormalizedJob[];
  sortField: SortField;
  sortAsc: boolean;
  onSort: (field: SortField) => void;
  selectedJobId: string | null;
  onSelectJob: (job: NormalizedJob) => void;
  activeRowIndex: number;
}

export const ResultsTable: React.FC<ResultsTableProps> = ({
  jobs,
  sortField,
  sortAsc,
  onSort,
  selectedJobId,
  onSelectJob,
  activeRowIndex,
}) => {
  const showSalary = jobs.some((j) => j.displaySalary && j.displaySalary !== '—');

  const getSortIndicator = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="size-3 opacity-30 ml-1 inline shrink-0" aria-hidden="true" />;
    }
    return sortAsc ? (
      <ArrowUp className="size-3 text-[var(--accent)] ml-1 inline shrink-0" aria-hidden="true" />
    ) : (
      <ArrowDown className="size-3 text-[var(--accent)] ml-1 inline shrink-0" aria-hidden="true" />
    );
  };

  const getAriaSort = (field: SortField): 'ascending' | 'descending' | 'none' => {
    if (sortField !== field) return 'none';
    return sortAsc ? 'ascending' : 'descending';
  };

  const renderWorkModelTag = (model: string | null | undefined) => {
    if (!model) return null;
    const normalized = model.toLowerCase().replace(/[\s-]/g, '_');
    if (!['remote', 'hybrid', 'in_person', 'onsite'].includes(normalized)) {
      return null;
    }

    if (normalized === 'remote') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium border border-[var(--accent)] bg-[var(--accent-tint)] text-[var(--ink)]">
          <span className="size-1.5 inline-block bg-[var(--accent)]" aria-hidden="true" />
          Remote
        </span>
      );
    }
    if (normalized === 'hybrid') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium border border-[#F59E0B] bg-[#FEF3C7] text-[#92400E] dark:border-[#B45309] dark:bg-[#78350F]/30 dark:text-[#FCD34D]">
          <span className="size-1.5 inline-block bg-[#D97706]" aria-hidden="true" />
          Hybrid
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium border border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--ink-muted)]">
        <span className="size-1.5 inline-block bg-[var(--ink-muted)]" aria-hidden="true" />
        In-person
      </span>
    );
  };

  return (
    <TooltipProvider delay={200}>
      <div className="w-full pb-20 overflow-x-auto">
        {/* Hidden accessible sort select for assistive tech */}
        <select
          id="sort-select"
          name="sortField"
          value={sortField || 'default'}
          onChange={(e) => {
            const val = e.target.value;
            onSort(val === 'default' ? null : (val as SortField));
          }}
          aria-label="Sort job results"
          className="sr-only"
        >
          <option value="default">Default order</option>
          <option value="date">Date posted</option>
          <option value="title">Role title</option>
          <option value="company">Company</option>
          <option value="salary">Salary</option>
        </select>

        {/* Semantic fixed-layout table with rigorous column alignment */}
        <table
          className="results-table w-full border-collapse"
          style={{ tableLayout: 'fixed' }}
          aria-label="Job search results"
        >
          <colgroup>
            <col style={{ width: 'auto', minWidth: '260px' }} />
            <col style={{ width: '240px' }} />
            <col style={{ width: '220px' }} />
            {showSalary && <col style={{ width: '130px' }} />}
            <col style={{ width: '120px' }} />
            <col style={{ width: '100px' }} />
          </colgroup>

          <thead>
            <tr className="border-b border-[var(--border)] text-left text-xs font-medium text-[var(--ink-muted)]">
              <th
                scope="col"
                className="py-3 px-3.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] transition-colors"
                onClick={() => onSort('title')}
                aria-sort={getAriaSort('title')}
              >
                <div className="inline-flex items-center gap-1">
                  <span>Role</span>
                  {getSortIndicator('title')}
                </div>
              </th>

              <th
                scope="col"
                className="py-3 px-3.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] transition-colors"
                onClick={() => onSort('company')}
                aria-sort={getAriaSort('company')}
              >
                <div className="inline-flex items-center gap-1">
                  <span>Company</span>
                  {getSortIndicator('company')}
                </div>
              </th>

              <th scope="col" className="py-3 px-3.5 font-medium select-none">
                <span>Location</span>
              </th>

              {showSalary && (
                <th
                  scope="col"
                  className="py-3 px-3.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] transition-colors"
                  onClick={() => onSort('salary')}
                  aria-sort={getAriaSort('salary')}
                >
                  <div className="inline-flex items-center gap-1">
                    <span>Salary</span>
                    {getSortIndicator('salary')}
                  </div>
                </th>
              )}

              <th scope="col" className="py-3 px-3.5 font-medium select-none">
                <span>Work model</span>
              </th>

              <th
                scope="col"
                className="py-3 px-3.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] transition-colors"
                onClick={() => onSort('date')}
                aria-sort={getAriaSort('date')}
              >
                <div className="inline-flex items-center gap-1">
                  <span>Posted</span>
                  {getSortIndicator('date')}
                </div>
              </th>
            </tr>
          </thead>

          <tbody>
            {jobs.map((job, index) => {
              const visited = isVisited(job.apply_url || job.id);
              const isSelected = selectedJobId === job.id;
              const isKeyboardActive = activeRowIndex === index;
              const initials = getCompanyInitials(job.company);
              const tileColor = getCompanyTileColor(job.company);
              const workModelTag = renderWorkModelTag(job.work_model);

              return (
                <tr
                  key={job.id}
                  className={`job-row group cursor-pointer border-b border-[var(--border-subtle)] transition-colors ${
                    isSelected ? 'bg-[var(--surface-selected)]' : 'hover:bg-[var(--surface-hover)]'
                  } ${isKeyboardActive ? 'keyboard-active outline-2 outline-[var(--accent)] outline-offset-[-2px]' : ''}`}
                  onClick={() => onSelectJob(job)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectJob(job);
                    }
                  }}
                  style={{
                    borderLeft: isSelected || isKeyboardActive
                      ? '2px solid var(--accent)'
                      : '2px solid transparent',
                  }}
                >
                  {/* Role Column (flexible, clamped to 2 lines, Tooltip for full title) */}
                  <td className="py-3.5 px-3.5 align-middle">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <Tooltip>
                        <TooltipTrigger render={<span className="text-left min-w-0 inline-block cursor-default" />}>
                          <span
                            className={`line-clamp-2 text-sm font-medium leading-snug transition-colors ${
                              visited ? 'title-visited' : 'text-[var(--ink)]'
                            }`}
                            title={job.title}
                          >
                            {job.displayTitle}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>
                          {job.title}
                        </TooltipContent>
                      </Tooltip>
                      <ArrowUpRight
                        className="size-3.5 text-[var(--ink-muted)] opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity shrink-0"
                        aria-hidden="true"
                      />
                    </div>
                  </td>

                  {/* Company Column: Square 28px Monogram tile on left, company name + lowercase mono ATS slug */}
                  <td className="py-3.5 px-3.5 align-middle">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div
                        className="size-7 flex items-center justify-center font-bold text-xs shrink-0 border"
                        style={{
                          backgroundColor: tileColor.bg,
                          color: tileColor.color,
                          borderColor: tileColor.border,
                        }}
                        aria-hidden="true"
                      >
                        {initials}
                      </div>

                      <div className="min-w-0 flex-1">
                        {job.companyIsModified ? (
                          <Tooltip>
                            <TooltipTrigger render={<span className="text-left font-medium text-sm text-[var(--ink)] truncate block cursor-help border-b border-dotted border-[var(--ink-subtle)]" />}>
                              {job.displayCompany}
                            </TooltipTrigger>
                            <TooltipContent>
                              Raw ATS source: {job.rawCompany}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <div
                            className="font-medium text-sm text-[var(--ink)] truncate"
                            title={job.company}
                          >
                            {job.displayCompany}
                          </div>
                        )}
                        <div
                          className="font-mono text-xs text-[var(--ink-subtle)] lowercase truncate"
                          title={`Source ATS: ${job.provider}`}
                        >
                          {job.provider || 'ats'}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Location Column */}
                  <td className="py-3.5 px-3.5 text-sm text-[var(--ink-muted)] truncate align-middle">
                    <span className="truncate block" title={job.location || undefined}>
                      {job.displayLocation === '—' ? '' : job.displayLocation}
                    </span>
                  </td>

                  {/* Salary Column (Auto-hidden if whole dataset lacks salary) */}
                  {showSalary && (
                    <td className="py-3.5 px-3.5 text-sm font-mono tabular-nums text-[var(--ink)] truncate align-middle">
                      {job.displaySalary && job.displaySalary !== '—' ? job.displaySalary : ''}
                    </td>
                  )}

                  {/* Work Model Column: empty when unknown */}
                  <td className="py-3.5 px-3.5 text-sm align-middle">
                    {workModelTag}
                  </td>

                  {/* Posted Date Column: Tabular numerals, left-aligned, consistent across rows */}
                  <td className="py-3.5 px-3.5 text-left text-sm text-[var(--ink-muted)] whitespace-nowrap align-middle">
                    <Tooltip>
                      <TooltipTrigger render={<span className="font-mono tabular-nums text-xs cursor-help inline-block" />}>
                        {job.relativePostedDate}
                      </TooltipTrigger>
                      <TooltipContent>
                        Posted: {job.postingDateFull || job.displayPostedDate}
                      </TooltipContent>
                    </Tooltip>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </TooltipProvider>
  );
};
