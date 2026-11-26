import React from 'react';
import type { NormalizedJob, SortField } from '../types';
import { isVisited } from '../lib/visited';
import { buildObjectiveScopeLabel } from '../lib/eligibility';
import { formatSalaryParts } from '../lib/normalize';
import { CompanyMark } from './CompanyMark';
import { STAGE_LABELS, findSavedJobEntry, type SavedJobEntry } from '../lib/savedJobs';
import { matchesJobIdentity } from '../lib/identity';
import { ArrowUp, ArrowDown, ArrowUpDown, ArrowUpRight } from 'lucide-react';

interface ResultsTableProps {
  jobs: NormalizedJob[];
  sortField: SortField;
  sortAsc: boolean;
  onSort: (field: SortField) => void;
  selectedJobId: string | null;
  onSelectJob: (job: NormalizedJob) => void;
  activeRowIndex: number;
  savedJobsMap?: Record<string, SavedJobEntry>;
}

function renderWorkModelTag(model: string | null | undefined) {
  const normalized = (model || '').toLowerCase().replace(/[\s-]/g, '_');
  if (!['remote', 'hybrid', 'in_person', 'onsite'].includes(normalized)) {
    return (
      <span
        data-testid="work-model-not-stated"
        className="text-xs text-[var(--ink-subtle)]"
      >
        Not stated
      </span>
    );
  }

  if (normalized === 'remote') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-xs font-medium border border-[var(--tag-remote-border)] bg-[var(--tag-remote-bg)] text-[var(--tag-remote-text)]">
        <span className="size-1.5 inline-block bg-[var(--tag-remote-marker)]" aria-hidden="true" />
        Remote
      </span>
    );
  }
  if (normalized === 'hybrid') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-xs font-medium border border-[var(--tag-hybrid-border)] bg-[var(--tag-hybrid-bg)] text-[var(--tag-hybrid-text)]">
        <span className="size-1.5 inline-block bg-[var(--tag-hybrid-marker)]" aria-hidden="true" />
        Hybrid
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-xs font-medium border border-[var(--tag-inperson-border)] bg-[var(--tag-inperson-bg)] text-[var(--tag-inperson-text)]">
      <span className="size-1.5 inline-block bg-[var(--tag-inperson-marker)]" aria-hidden="true" />
      In-person
    </span>
  );
}

function getEligibilityLine(job: NormalizedJob): {
  text: string;
  toneClass: string;
  tooltip: string | null;
} | null {
  const elig = job.displayEligibility;
  if (!elig) {
    const objective = buildObjectiveScopeLabel(job.eligibility, job.work_model, job.location);
    if (!objective) return null;
    return {
      text: objective,
      toneClass: 'text-[var(--ink-muted)]',
      tooltip: null,
    };
  }

  if (elig.status === 'restricted') {
    const text =
      elig.scopeLabel && !elig.scopeLabel.toLowerCase().includes('not eligible')
        ? `Restricted · ${elig.scopeLabel}`
        : elig.statusLabel || 'Restricted';
    return {
      text,
      toneClass: 'text-[var(--danger-text)]',
      tooltip: elig.reason || elig.statusLabel,
    };
  }

  if (elig.status === 'eligible') {
    const stripped =
      elig.combinedLabel?.replace(/^(Remote|Hybrid|Onsite)\s*·\s*/i, '') ||
      elig.scopeLabel ||
      elig.statusLabel ||
      '';
    if (!stripped) return null;
    return {
      text: stripped,
      toneClass: 'text-[var(--ink)] font-medium',
      tooltip: elig.reason || elig.statusLabel,
    };
  }

  const fallback = elig.scopeLabel || elig.statusLabel || '';
  if (!fallback) return null;
  return {
    text: fallback,
    toneClass: 'text-[var(--ink-muted)]',
    tooltip: elig.reason || elig.statusLabel || null,
  };
}

interface ResultRowProps {
  job: NormalizedJob;
  visited: boolean;
  isSelected: boolean;
  savedEntry: SavedJobEntry | null;
  isKeyboardActive: boolean;
  showSalary: boolean;
  onSelectJob: (job: NormalizedJob) => void;
}

const ResultRow = React.memo<ResultRowProps>(
  ({ job, visited, isSelected, savedEntry, isKeyboardActive, showSalary, onSelectJob }) => {
    const workModelTag = renderWorkModelTag(job.work_model);
    const eligibilityLine = getEligibilityLine(job);
    const salaryParts = formatSalaryParts(job.salary);
    const verifiedDate =
      job.last_verified_at && !Number.isNaN(Date.parse(job.last_verified_at))
        ? new Date(job.last_verified_at).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          })
        : null;
    const ageTooltip = verifiedDate
      ? `Posted: ${job.postingDateFull || job.displayPostedDate} · Verified: ${verifiedDate}`
      : `Posted: ${job.postingDateFull || job.displayPostedDate}`;

    return (
      <tr
        data-freshness-tier={job.freshnessTier}
        className={`job-row bp-row-virtual group cursor-pointer border-b border-[var(--border-subtle)] transition-[background-color,box-shadow] duration-120 ease-out active:bg-[var(--surface-raised)] hover:shadow-[inset_2px_0_0_0_var(--accent)] ${
          isSelected
            ? 'bg-[var(--surface-selected)] shadow-[inset_2px_0_0_0_var(--accent)]'
            : 'hover:bg-[var(--surface-hover)]'
        } ${
          isKeyboardActive
            ? 'keyboard-active shadow-[inset_2px_0_0_0_var(--accent)] outline-2 outline-[var(--accent)] outline-offset-[-2px]'
            : ''
        }`}
        onClick={() => onSelectJob(job)}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelectJob(job);
          }
        }}
      >
        {/* Role Column */}
        <td className="py-3.5 px-3.5 align-middle">
          <div className="flex items-center gap-1.5 min-w-0">
            <span
              className={`line-clamp-2 text-sm font-medium leading-snug transition-colors ${
                visited ? 'title-visited' : 'text-[var(--ink)]'
              }`}
              title={job.title}
            >
              {job.displayTitle}
            </span>
            {savedEntry && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-[11px] font-medium border border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--ink)] shrink-0">
                {STAGE_LABELS[savedEntry.stage]}
              </span>
            )}
            <ArrowUpRight
              className="size-3.5 text-[var(--ink-muted)] opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 group-hover:translate-x-0.5 transition-[opacity,transform] duration-140 ease-out shrink-0"
              aria-hidden="true"
            />
          </div>
        </td>

        {/* Company Column */}
        <td className="py-3.5 px-3.5 align-middle">
          <div className="flex items-center gap-2.5 min-w-0">
            <CompanyMark
              company={job.company}
              logoUrl={job.company_logo_url}
              companyDomain={job.company_domain}
              size="md"
            />

            <div className="min-w-0 flex-1">
              <div
                className={`font-medium text-sm text-[var(--ink)] leading-snug line-clamp-2 break-words ${
                  job.companyIsModified ? 'underline decoration-dotted decoration-[var(--ink-subtle)] underline-offset-2 cursor-help' : ''
                }`}
                title={job.companyIsModified ? `Listed as: ${job.rawCompany}` : job.company}
              >
                {job.displayCompany}
              </div>
              <div
                className="font-mono text-xs text-[var(--ink-subtle)] lowercase truncate"
                title={`Source: ${job.provider}`}
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

        {/* Salary Column */}
        {showSalary && (
          <td data-testid="salary-cell" className="py-3.5 px-3.5 align-middle">
            {salaryParts ? (
              salaryParts.period ? (
                <div className="flex flex-col min-w-0" title={salaryParts.full}>
                  <span className="text-[13px] font-mono tabular-nums text-[var(--ink)] leading-snug break-words">
                    {salaryParts.range}
                  </span>
                  <span className="text-[11px] font-mono text-[var(--ink-subtle)] leading-tight">
                    {salaryParts.period}
                  </span>
                </div>
              ) : (
                <span
                  className="text-[13px] font-mono tabular-nums text-[var(--ink)] leading-snug line-clamp-2 break-words block"
                  title={salaryParts.full}
                >
                  {salaryParts.range}
                </span>
              )
            ) : null}
          </td>
        )}

        {/* Work & eligibility Column */}
        <td className="py-3.5 px-3.5 text-sm align-middle">
          <div className="flex flex-col items-start gap-1 min-w-0">
            {workModelTag}
            {eligibilityLine && (
              <span
                className={`text-xs leading-tight line-clamp-1 ${
                  eligibilityLine.tooltip ? 'cursor-help ' : ''
                }${eligibilityLine.toneClass}`}
                title={eligibilityLine.tooltip || undefined}
              >
                {eligibilityLine.text}
              </span>
            )}
          </div>
        </td>

        {/* Posted Date & Age Column */}
        <td className="py-3.5 px-3.5 text-left text-sm text-[var(--ink-muted)] whitespace-nowrap align-middle">
          <span
            data-testid="job-age-badge"
            data-freshness-tier={job.freshnessTier}
            title={ageTooltip}
            className="inline-flex items-center px-1.5 py-0.5 rounded-sm font-mono tabular-nums text-[11px] font-medium border cursor-help"
            style={
              job.freshnessTier === 'evergreen'
                ? {
                    backgroundColor: 'var(--tag-remote-bg)',
                    color: 'var(--tag-remote-text)',
                    borderColor: 'transparent',
                  }
                : job.freshnessTier === 'stale'
                  ? {
                      backgroundColor: 'var(--tag-hybrid-bg)',
                      color: 'var(--tag-hybrid-text)',
                      borderColor: 'transparent',
                    }
                  : {
                      backgroundColor: 'transparent',
                      color: 'var(--ink-muted)',
                      borderColor: 'transparent',
                    }
            }
          >
            {job.ageBadgeLabel}
          </span>
        </td>
      </tr>
    );
  }
);

ResultRow.displayName = 'ResultRow';

export const ResultsTable: React.FC<ResultsTableProps> = ({
  jobs,
  sortField,
  sortAsc,
  onSort,
  selectedJobId,
  onSelectJob,
  activeRowIndex,
  savedJobsMap,
}) => {
  const showSalary = jobs.some((j) => j.displaySalary && j.displaySalary !== '—');
  const showOlderDivider = sortField === null;
  const firstStaleIndex = showOlderDivider
    ? jobs.findIndex((j) => j.freshnessTier === 'stale')
    : -1;
  const staleCount =
    showOlderDivider && firstStaleIndex !== -1
      ? jobs.filter((j) => j.freshnessTier === 'stale').length
      : 0;

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

  return (
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
          <col style={{ width: 'auto', minWidth: '220px' }} />
          <col style={{ width: '195px' }} />
          <col style={{ width: '165px' }} />
          {showSalary && <col style={{ width: '195px' }} />}
          <col style={{ width: '195px' }} />
          <col style={{ width: '90px' }} />
        </colgroup>

        <thead>
          <tr className="border-b border-[var(--border)] text-left text-xs font-medium text-[var(--ink-muted)]">
            <th
              scope="col"
              className="py-3.5 px-3.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] transition-colors"
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
              className="py-3.5 px-3.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] transition-colors"
              onClick={() => onSort('company')}
              aria-sort={getAriaSort('company')}
            >
              <div className="inline-flex items-center gap-1">
                <span>Company</span>
                {getSortIndicator('company')}
              </div>
            </th>

            <th scope="col" className="py-3.5 px-3.5 font-medium select-none">
              <span>Location</span>
            </th>

            {showSalary && (
              <th
                scope="col"
                className="py-3.5 px-3.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] transition-colors"
                onClick={() => onSort('salary')}
                aria-sort={getAriaSort('salary')}
              >
                <div className="inline-flex items-center gap-1">
                  <span>Salary</span>
                  {getSortIndicator('salary')}
                </div>
              </th>
            )}

            <th scope="col" className="py-3.5 px-3.5 font-medium select-none">
              <span>Work &amp; eligibility</span>
            </th>

            <th
              scope="col"
              className="py-3.5 px-3.5 font-medium cursor-pointer select-none hover:text-[var(--ink)] transition-colors"
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
            const isSelected = selectedJobId ? matchesJobIdentity(job, selectedJobId) : false;
            const savedEntry = savedJobsMap ? findSavedJobEntry(job, savedJobsMap) : null;
            const isKeyboardActive = activeRowIndex === index;

            return (
              <React.Fragment key={job.id}>
                {index === firstStaleIndex && staleCount > 0 && (
                  <tr
                    data-testid="older-postings-divider"
                    className="older-postings-divider bg-[var(--surface-subtle)] border-b border-[var(--border)]"
                  >
                    <td
                      colSpan={showSalary ? 6 : 5}
                      className="py-2 px-3.5 text-[11px] font-medium text-[var(--ink-muted)] uppercase tracking-wider"
                    >
                      Older postings ({staleCount}) · Posted over 90 days ago
                    </td>
                  </tr>
                )}
                <ResultRow
                  job={job}
                  visited={visited}
                  isSelected={isSelected}
                  savedEntry={savedEntry}
                  isKeyboardActive={isKeyboardActive}
                  showSalary={showSalary}
                  onSelectJob={onSelectJob}
                />
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
