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
  const getSortIndicator = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="size-3 opacity-30 ml-1 inline" aria-hidden="true" />;
    }
    return sortAsc ? (
      <ArrowUp className="size-3 text-[var(--accent)] ml-1 inline" aria-hidden="true" />
    ) : (
      <ArrowDown className="size-3 text-[var(--accent)] ml-1 inline" aria-hidden="true" />
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

    let bg = 'var(--tag-inperson-bg)';
    let text = 'var(--tag-inperson-text)';
    let marker = 'var(--tag-inperson-marker)';
    let label = 'In-person';

    if (normalized === 'remote') {
      bg = 'var(--tag-remote-bg)';
      text = 'var(--tag-remote-text)';
      marker = 'var(--tag-remote-marker)';
      label = 'Remote';
    } else if (normalized === 'hybrid') {
      bg = 'var(--tag-hybrid-bg)';
      text = 'var(--tag-hybrid-text)';
      marker = 'var(--tag-hybrid-marker)';
      label = 'Hybrid';
    }

    return (
      <span
        className="inline-flex items-center gap-1.5 px-2 py-0.5 text-caption font-medium border border-transparent shrink-0"
        style={{ backgroundColor: bg, color: text }}
      >
        <span
          className="size-1.5 shrink-0"
          style={{ backgroundColor: marker }}
          aria-hidden="true"
        />
        <span>{label}</span>
      </span>
    );
  };

  return (
    <TooltipProvider delay={200}>
      <div className="w-full pb-16">
        {/* Dedicated Sort Control Row */}
        <div className="flex items-center justify-between py-2 border-b border-[var(--border)] text-caption text-[var(--ink-muted)]">
          <span className="font-medium text-[var(--ink)]">
            Job Opportunities
          </span>

          <div className="flex items-center gap-2">
            <span className="text-[var(--ink-subtle)]">Sort:</span>
            <select
              id="sort-select"
              name="sortField"
              value={sortField || 'default'}
              onChange={(e) => {
                const val = e.target.value;
                onSort(val === 'default' ? null : (val as SortField));
              }}
              aria-label="Sort job results"
              className="h-7 px-2 text-caption bg-transparent border border-[var(--border)] text-[var(--ink)] outline-none focus-visible:border-[var(--accent)] cursor-pointer"
            >
              <option value="default">Default order</option>
              <option value="date">Date posted</option>
              <option value="title">Role title</option>
              <option value="company">Company</option>
              <option value="salary">Salary</option>
            </select>
          </div>
        </div>

        {/* Two-Line Clean List Structure with accessible table semantics */}
        <table className="results-table w-full border-collapse" aria-label="Job search results">
          {/* Header row is visually quiet but accessible for sorting & tests */}
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-caption text-[var(--ink-muted)]">
              <th
                scope="col"
                className="py-2.5 font-medium cursor-pointer select-none hover:text-[var(--ink)]"
                onClick={() => onSort('title')}
                aria-sort={getAriaSort('title')}
              >
                <span>Role</span>
                {getSortIndicator('title')}
              </th>
              <th
                scope="col"
                className="py-2.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] hidden sm:table-cell"
                onClick={() => onSort('company')}
                aria-sort={getAriaSort('company')}
              >
                <span>Company</span>
                {getSortIndicator('company')}
              </th>
              <th
                scope="col"
                className="py-2.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] hidden md:table-cell"
                onClick={() => onSort('salary')}
                aria-sort={getAriaSort('salary')}
              >
                <span>Salary</span>
                {getSortIndicator('salary')}
              </th>
              <th
                scope="col"
                className="py-2.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] text-right"
                onClick={() => onSort('date')}
                aria-sort={getAriaSort('date')}
              >
                <span>Posted</span>
                {getSortIndicator('date')}
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
                  } ${isKeyboardActive ? 'keyboard-active outline-2 outline-[var(--accent)]' : ''}`}
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
                      ? '3px solid var(--accent)'
                      : '3px solid transparent',
                  }}
                >
                  {/* Main Role & Details Column */}
                  <td className="py-3 px-2 sm:px-3" colSpan={2}>
                    <div className="flex flex-col gap-1 min-w-0">
                      {/* Line 1: Job Title */}
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span
                          className={`line-clamp-2 text-body font-medium transition-colors ${
                            visited ? 'title-visited' : 'text-[var(--ink)]'
                          }`}
                          title={job.title}
                        >
                          {job.displayTitle}
                        </span>
                        <ArrowUpRight
                          className="size-3.5 text-[var(--ink-muted)] opacity-0 group-hover:opacity-100 transition-opacity shrink-0 hidden sm:inline"
                          aria-hidden="true"
                        />
                      </div>

                      {/* Line 2: Company & Location */}
                      <div className="flex items-center gap-2 text-small text-[var(--ink-muted)] min-w-0">
                        <div
                          className="size-4.5 flex items-center justify-center font-bold text-[9px] shrink-0 border"
                          style={{
                            backgroundColor: tileColor.bg,
                            color: tileColor.color,
                            borderColor: tileColor.border,
                          }}
                          aria-hidden="true"
                        >
                          {initials}
                        </div>

                        {job.companyIsModified ? (
                          <Tooltip>
                            <TooltipTrigger className="font-medium text-[var(--ink)] truncate max-w-[200px] cursor-help border-b border-dotted border-[var(--ink-subtle)]">
                              {job.displayCompany}
                            </TooltipTrigger>
                            <TooltipContent>
                              Raw ATS source: {job.rawCompany}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="font-medium text-[var(--ink)] truncate max-w-[200px]">
                            {job.displayCompany}
                          </span>
                        )}

                        <span className="text-[var(--border-strong)]">·</span>
                        <span className="truncate max-w-[220px]">
                          {job.displayLocation}
                        </span>
                      </div>
                    </div>
                  </td>

                  {/* Salary Column (or metadata on smaller screens) */}
                  <td className="py-3 px-2 sm:px-3 hidden md:table-cell align-middle">
                    {job.displaySalary && job.displaySalary !== '—' && (
                      <span className="text-small text-[var(--ink)] font-medium">
                        {job.displaySalary}
                      </span>
                    )}
                  </td>

                  {/* Right Metadata Column: Work model, Date, Platform */}
                  <td className="py-3 px-2 sm:px-3 text-right align-middle shrink-0">
                    <div className="flex items-center justify-end gap-2.5">
                      {workModelTag}

                      <Tooltip>
                        <TooltipTrigger className="text-small text-[var(--ink-muted)] whitespace-nowrap cursor-help">
                          {job.relativePostedDate}
                        </TooltipTrigger>
                        <TooltipContent>
                          Posted: {job.postingDateFull || job.displayPostedDate}
                        </TooltipContent>
                      </Tooltip>

                      <span
                        className="text-data text-[11px] text-[var(--ink-subtle)] uppercase tracking-wider hidden sm:inline"
                        title={`Source ATS: ${job.provider}`}
                      >
                        {job.provider}
                      </span>
                    </div>
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
