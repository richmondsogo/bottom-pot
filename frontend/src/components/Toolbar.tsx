import React, { type RefObject } from 'react';
import { Search, SlidersHorizontal, X } from 'lucide-react';
import type { EligibilityFilterMode } from '../types';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Kbd } from './ui/kbd';
import { CountryCombobox } from './CountryCombobox';
import { Popover, PopoverTrigger, PopoverContent } from './ui/popover';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from './ui/select';

interface ToolbarProps {
  tableSearch: string;
  setTableSearch: (val: string) => void;
  providerFilter: string;
  setProviderFilter: (val: string) => void;
  remoteFilter: string;
  setRemoteFilter: (val: string) => void;
  employmentFilter: string;
  setEmploymentFilter: (val: string) => void;
  applicantCountry?: string;
  onChangeApplicantCountry?: (code: string) => void;
  eligibilityFilter?: EligibilityFilterMode;
  setEligibilityFilter?: (val: EligibilityFilterMode) => void;
  onlySalaryListed: boolean;
  setOnlySalaryListed: (val: boolean) => void;
  onlySavedJobs?: boolean;
  setOnlySavedJobs?: (val: boolean) => void;
  savedCount?: number;
  availableProviders: string[];
  availableEmploymentTypes: string[];
  totalResults: number;
  filteredCount: number;
  onClearFilters: () => void;
  searchInputRef: RefObject<HTMLInputElement | null>;
  onDownloadCsv?: () => void;
  onDownloadJson?: () => void;
}

const ELIGIBILITY_FILTER_LABELS: Record<EligibilityFilterMode, string> = {
  '': 'All eligibility',
  eligible_and_unknown: 'Eligible + unverified',
  eligible: 'Eligible only',
  unknown: 'Unverified only',
  restricted: 'Restricted only',
};

export const Toolbar: React.FC<ToolbarProps> = ({
  tableSearch,
  setTableSearch,
  providerFilter,
  setProviderFilter,
  remoteFilter,
  setRemoteFilter,
  employmentFilter,
  setEmploymentFilter,
  applicantCountry = '',
  onChangeApplicantCountry,
  eligibilityFilter = '',
  setEligibilityFilter,
  onlySalaryListed,
  setOnlySalaryListed,
  onlySavedJobs = false,
  setOnlySavedJobs,
  savedCount = 0,
  availableProviders,
  availableEmploymentTypes,
  onClearFilters,
  searchInputRef,
}) => {
  const secondaryCount =
    (providerFilter ? 1 : 0) +
    (employmentFilter ? 1 : 0) +
    (onlySalaryListed ? 1 : 0);

  const hasActiveFilters = Boolean(
    tableSearch ||
    providerFilter ||
    remoteFilter ||
    employmentFilter ||
    (applicantCountry && eligibilityFilter) ||
    onlySalaryListed ||
    onlySavedJobs
  );

  return (
    <div className="w-full border-b border-[var(--border)] bg-[var(--bg)] py-3">
      <div className="page-shell flex flex-col gap-2.5">
        {/* Single calm horizontal filter strip on desktop; balanced 2-column grid below search on mobile */}
        <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-2 sm:gap-2.5">
          {/* Keyword filter input */}
          <div className="relative w-full sm:flex-1 sm:min-w-[220px] sm:max-w-xs">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--ink-muted)] pointer-events-none"
              aria-hidden="true"
            />
            <Input
              ref={searchInputRef}
              id="table-search-input"
              name="tableSearch"
              type="text"
              className="h-9 !pl-9 !pr-8 text-sm bg-[var(--surface)] border-[var(--border)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus-visible:border-[var(--accent)] shadow-none"
              placeholder="Filter results..."
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
              aria-label="Filter results table"
            />
            {tableSearch ? (
              <button
                type="button"
                onClick={() => setTableSearch('')}
                aria-label="Clear filter text"
                className="absolute right-2 top-1/2 -translate-y-1/2 size-6 inline-flex items-center justify-center text-[var(--ink-subtle)] hover:text-[var(--ink)] cursor-pointer"
              >
                <X className="size-3.5" aria-hidden="true" />
              </button>
            ) : (
              <Kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] pointer-events-none px-1.5 py-0.5 text-[var(--ink-subtle)] border border-[var(--border-subtle)] bg-[var(--surface-subtle)]">
                /
              </Kbd>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 w-full sm:contents">
          {/* Work model selector */}
          <div className="relative">
            <Select
              value={remoteFilter || 'all'}
              onValueChange={(val) => setRemoteFilter(val === 'all' || !val ? '' : val)}
            >
              <SelectTrigger
                id="workmodel-filter-trigger"
                aria-label="Select work model"
                className="h-9 px-3 text-sm w-full sm:w-auto sm:min-w-[144px]"
              >
                <SelectValue placeholder="All work models">
                  {remoteFilter === 'remote'
                    ? 'Remote'
                    : remoteFilter === 'hybrid'
                    ? 'Hybrid'
                    : remoteFilter === 'in_person'
                    ? 'In-person'
                    : 'All work models'}
                </SelectValue>
              </SelectTrigger>
              <SelectContent align="start">
                <SelectItem value="all">All work models</SelectItem>
                <SelectItem value="remote">Remote</SelectItem>
                <SelectItem value="hybrid">Hybrid</SelectItem>
                <SelectItem value="in_person">In-person</SelectItem>
              </SelectContent>
            </Select>
            <select
              id="workmodel-filter-select"
              name="workModelFilter"
              value={remoteFilter}
              onChange={(e) => setRemoteFilter(e.target.value)}
              aria-label="Filter by work model"
              className="sr-only"
              tabIndex={-1}
            >
              <option value="">All work models</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="in_person">In-person</option>
            </select>
          </div>

          {/* Applicant country selector ("Where can you work from?") */}
          {onChangeApplicantCountry && (
            <CountryCombobox
              compact
              value={applicantCountry}
              onChange={onChangeApplicantCountry}
              idPrefix="toolbar-applicant-country"
              className="col-span-2 -order-1 sm:order-none sm:col-span-1 sm:w-auto"
            />
          )}

          {/* Eligibility filter (visible when applicant country is selected) */}
          {applicantCountry && setEligibilityFilter && (
            <div className="relative">
              <Select
                value={eligibilityFilter || 'all'}
                onValueChange={(val) =>
                  setEligibilityFilter(
                    val === 'all' || !val ? '' : (val as EligibilityFilterMode)
                  )
                }
              >
                <SelectTrigger
                  id="eligibility-filter-trigger"
                  aria-label="Filter by applicant eligibility"
                  className="h-9 px-3 text-sm w-full sm:w-auto sm:min-w-[160px]"
                >
                  <SelectValue placeholder="All eligibility">
                    {ELIGIBILITY_FILTER_LABELS[eligibilityFilter]}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent align="start">
                  <SelectItem value="all">All eligibility</SelectItem>
                  <SelectItem value="eligible_and_unknown">Eligible + unverified</SelectItem>
                  <SelectItem value="eligible">Eligible only</SelectItem>
                  <SelectItem value="unknown">Unverified only</SelectItem>
                  <SelectItem value="restricted">Restricted only</SelectItem>
                </SelectContent>
              </Select>
              <select
                id="eligibility-filter-select"
                name="eligibilityFilter"
                value={eligibilityFilter}
                onChange={(e) =>
                  setEligibilityFilter(e.target.value as EligibilityFilterMode)
                }
                aria-label="Filter by eligibility"
                className="sr-only"
                tabIndex={-1}
              >
                <option value="">All eligibility</option>
                <option value="eligible_and_unknown">Eligible + unverified</option>
                <option value="eligible">Eligible only</option>
                <option value="unknown">Unverified only</option>
                <option value="restricted">Restricted only</option>
              </select>
            </div>
          )}

          {/* Saved shortlist toggle */}
          {setOnlySavedJobs && (
            <button
              type="button"
              role="switch"
              aria-checked={onlySavedJobs}
              onClick={() => setOnlySavedJobs(!onlySavedJobs)}
              className={`h-9 px-3 text-sm border inline-flex items-center justify-center sm:justify-start gap-2 w-full sm:w-auto transition-[background-color,border-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none cursor-pointer select-none ${
                onlySavedJobs
                  ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium ring-1 ring-[var(--ink)]'
                  : 'border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
              }`}
            >
              <span
                className={`size-2 inline-block ${
                  onlySavedJobs ? 'bg-[var(--ink)]' : 'bg-[var(--border-strong)]'
                }`}
              />
              <span>{savedCount > 0 ? `Saved (${savedCount})` : 'Saved'}</span>
            </button>
          )}

          {/* Secondary Filters Popover (Source, Job type, Salary listed) */}
          <Popover>
            <PopoverTrigger
              type="button"
              id="more-filters-trigger"
              aria-label="More filters"
              className={`h-9 px-3 text-sm border inline-flex items-center justify-center sm:justify-start gap-2 w-full sm:w-auto transition-[background-color,border-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none cursor-pointer select-none whitespace-nowrap ${
                secondaryCount > 0
                  ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                  : 'border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)]'
              }`}
              style={{ borderRadius: 0 }}
            >
              <SlidersHorizontal className="size-3.5" aria-hidden="true" />
              <span>More filters</span>
              {secondaryCount > 0 && (
                <span className="px-1.5 py-0 text-[11px] font-mono bg-[var(--bg)] border border-[var(--border)] text-[var(--ink)]">
                  {secondaryCount}
                </span>
              )}
            </PopoverTrigger>
            <PopoverContent align="start" className="w-72 p-4 flex flex-col gap-3.5">
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-[var(--ink)]">Source</span>
                <Select
                  value={providerFilter || 'all'}
                  onValueChange={(val) => setProviderFilter(val === 'all' || !val ? '' : val)}
                >
                  <SelectTrigger
                    id="platform-filter-trigger"
                    aria-label="Select source"
                    className="h-9 px-3 text-sm w-full"
                  >
                    <SelectValue placeholder="All sources">
                      {providerFilter
                        ? providerFilter.charAt(0).toUpperCase() + providerFilter.slice(1)
                        : 'All sources'}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent align="start">
                    <SelectItem value="all">All sources</SelectItem>
                    {availableProviders.map((p) => (
                      <SelectItem key={p} value={p}>
                        {p.charAt(0).toUpperCase() + p.slice(1)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {availableEmploymentTypes.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-[var(--ink)]">Job type</span>
                  <Select
                    value={employmentFilter || 'all'}
                    onValueChange={(val) => setEmploymentFilter(val === 'all' || !val ? '' : val)}
                  >
                    <SelectTrigger
                      id="employment-filter-trigger"
                      aria-label="Select employment type"
                      className="h-9 px-3 text-sm w-full"
                    >
                      <SelectValue placeholder="All job types">
                        {employmentFilter
                          ? employmentFilter.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                          : 'All job types'}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent align="start">
                      <SelectItem value="all">All job types</SelectItem>
                      {availableEmploymentTypes.map((et) => (
                        <SelectItem key={et} value={et}>
                          {et.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="pt-1 border-t border-[var(--border-subtle)] flex items-center justify-between">
                <span className="text-xs font-medium text-[var(--ink)]">Salary listed only</span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={onlySalaryListed}
                  onClick={() => setOnlySalaryListed(!onlySalaryListed)}
                  className={`h-8 px-3 text-xs border inline-flex items-center gap-2 transition-colors cursor-pointer select-none ${
                    onlySalaryListed
                      ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                      : 'border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
                  }`}
                >
                  <span
                    className={`size-2 inline-block ${
                      onlySalaryListed ? 'bg-[var(--accent)]' : 'bg-[var(--border-strong)]'
                    }`}
                  />
                  <span>{onlySalaryListed ? 'On' : 'Off'}</span>
                </button>
              </div>
            </PopoverContent>
          </Popover>

          {/* Keep sr-only selects mounted outside popover for assistive tech */}
          <select
            id="platform-filter-select"
            name="platformFilter"
            value={providerFilter}
            onChange={(e) => setProviderFilter(e.target.value)}
            aria-label="Filter by source"
            className="sr-only"
            tabIndex={-1}
          >
            <option value="">All sources</option>
            {availableProviders.map((p) => (
              <option key={p} value={p}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>

          {availableEmploymentTypes.length > 0 && (
            <select
              id="employment-filter-select"
              name="employmentFilter"
              value={employmentFilter}
              onChange={(e) => setEmploymentFilter(e.target.value)}
              aria-label="Filter by employment type"
              className="sr-only"
              tabIndex={-1}
            >
              <option value="">All job types</option>
              {availableEmploymentTypes.map((et) => (
                <option key={et} value={et}>
                  {et.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </option>
              ))}
            </select>
          )}

          {/* Clear active filters button */}
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearFilters}
              aria-label="Clear filters"
              className="h-9 text-sm px-3 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] cursor-pointer col-span-2 sm:col-span-1 w-full sm:w-auto"
            >
              <X className="size-3.5 mr-1.5" aria-hidden="true" />
              <span>Clear filters</span>
            </Button>
          )}
          </div>
        </div>

        {/* Removable active pills for secondary filters tucked in More filters */}
        {secondaryCount > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            {providerFilter && (
              <button
                type="button"
                onClick={() => setProviderFilter('')}
                className="h-7 px-2.5 inline-flex items-center gap-1.5 border border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--ink)] hover:bg-[var(--surface-hover)] cursor-pointer"
              >
                <span>Source: {providerFilter}</span>
                <X className="size-3 text-[var(--ink-muted)]" aria-hidden="true" />
              </button>
            )}
            {employmentFilter && (
              <button
                type="button"
                onClick={() => setEmploymentFilter('')}
                className="h-7 px-2.5 inline-flex items-center gap-1.5 border border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--ink)] hover:bg-[var(--surface-hover)] cursor-pointer"
              >
                <span>Job type: {employmentFilter.replace(/_/g, ' ')}</span>
                <X className="size-3 text-[var(--ink-muted)]" aria-hidden="true" />
              </button>
            )}
            {onlySalaryListed && (
              <button
                type="button"
                onClick={() => setOnlySalaryListed(false)}
                className="h-7 px-2.5 inline-flex items-center gap-1.5 border border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--ink)] hover:bg-[var(--surface-hover)] cursor-pointer"
              >
                <span>Salary listed</span>
                <X className="size-3 text-[var(--ink-muted)]" aria-hidden="true" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
