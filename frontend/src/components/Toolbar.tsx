import React, { type RefObject } from 'react';
import { Search, X } from 'lucide-react';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Kbd } from './ui/kbd';
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

export const Toolbar: React.FC<ToolbarProps> = ({
  tableSearch,
  setTableSearch,
  providerFilter,
  setProviderFilter,
  remoteFilter,
  setRemoteFilter,
  employmentFilter,
  setEmploymentFilter,
  onlySalaryListed,
  setOnlySalaryListed,
  onlySavedJobs = false,
  setOnlySavedJobs,
  savedCount = 0,
  availableProviders,
  availableEmploymentTypes,
  totalResults,
  filteredCount,
  onClearFilters,
  searchInputRef,
}) => {
  const hasActiveFilters = Boolean(
    tableSearch ||
    providerFilter ||
    remoteFilter ||
    employmentFilter ||
    onlySalaryListed ||
    onlySavedJobs
  );

  return (
    <div className="w-full border-b border-[var(--border)] bg-[var(--bg)] py-4 sm:py-5">
      <div className="page-shell flex flex-col gap-3.5">
        {/* Filter controls row with generous breathing space */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Keyword filter input */}
          <div className="relative flex-1 min-w-[240px] max-w-sm">
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
              placeholder="Filter by role, company, location..."
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
              aria-label="Filter results table"
            />
            <Kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] pointer-events-none px-1.5 py-0.5 text-[var(--ink-subtle)] border border-[var(--border-subtle)] bg-[var(--surface-subtle)]">
              /
            </Kbd>
          </div>

          {/* Platform selector */}
          <div className="relative">
            <Select
              value={providerFilter || 'all'}
              onValueChange={(val) => setProviderFilter(val === 'all' || !val ? '' : val)}
            >
              <SelectTrigger
                id="platform-filter-trigger"
                aria-label="Select ATS provider"
                className="h-9 px-3 text-sm min-w-[144px]"
              >
                <SelectValue placeholder="All platforms">
                  {providerFilter
                    ? providerFilter.charAt(0).toUpperCase() + providerFilter.slice(1)
                    : 'All platforms'}
                </SelectValue>
              </SelectTrigger>
              <SelectContent align="start">
                <SelectItem value="all">All platforms</SelectItem>
                {availableProviders.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <select
              id="platform-filter-select"
              name="platformFilter"
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
              aria-label="Filter by ATS provider"
              className="sr-only"
              tabIndex={-1}
            >
              <option value="">All platforms</option>
              {availableProviders.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {/* Work model selector */}
          <div className="relative">
            <Select
              value={remoteFilter || 'all'}
              onValueChange={(val) => setRemoteFilter(val === 'all' || !val ? '' : val)}
            >
              <SelectTrigger
                id="workmodel-filter-trigger"
                aria-label="Select work model"
                className="h-9 px-3 text-sm min-w-[150px]"
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

          {/* Employment type selector */}
          {availableEmploymentTypes.length > 0 && (
            <div className="relative">
              <Select
                value={employmentFilter || 'all'}
                onValueChange={(val) => setEmploymentFilter(val === 'all' || !val ? '' : val)}
              >
                <SelectTrigger
                  id="employment-filter-trigger"
                  aria-label="Select employment type"
                  className="h-9 px-3 text-sm min-w-[140px]"
                >
                  <SelectValue placeholder="All job types">
                    {employmentFilter
                      ? employmentFilter.charAt(0).toUpperCase() + employmentFilter.slice(1)
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
            </div>
          )}

          {/* Proper Toggle 1: Remote only */}
          <button
            type="button"
            role="switch"
            aria-checked={remoteFilter === 'remote'}
            onClick={() => setRemoteFilter(remoteFilter === 'remote' ? '' : 'remote')}
            className={`h-9 px-3 text-sm border inline-flex items-center gap-2 transition-colors cursor-pointer select-none ${
              remoteFilter === 'remote'
                ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium ring-1 ring-[var(--ink)]'
                : 'border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
            }`}
          >
            <span
              className={`size-2 inline-block ${
                remoteFilter === 'remote' ? 'bg-[var(--accent)]' : 'bg-[var(--border-strong)]'
              }`}
            />
            <span>Remote only</span>
          </button>

          {/* Proper Toggle 2: Salary listed */}
          <button
            type="button"
            role="switch"
            aria-checked={onlySalaryListed}
            onClick={() => setOnlySalaryListed(!onlySalaryListed)}
            className={`h-9 px-3 text-sm border inline-flex items-center gap-2 transition-colors cursor-pointer select-none ${
              onlySalaryListed
                ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium ring-1 ring-[var(--ink)]'
                : 'border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
            }`}
          >
            <span
              className={`size-2 inline-block ${
                onlySalaryListed ? 'bg-[var(--accent)]' : 'bg-[var(--border-strong)]'
              }`}
            />
            <span>Salary listed</span>
          </button>

          {/* Proper Toggle 3: Saved shortlist */}
          {setOnlySavedJobs && (
            <button
              type="button"
              role="switch"
              aria-checked={onlySavedJobs}
              onClick={() => setOnlySavedJobs(!onlySavedJobs)}
              className={`h-9 px-3 text-sm border inline-flex items-center gap-2 transition-colors cursor-pointer select-none ${
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

          {/* Clear active filters button */}
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearFilters}
              aria-label="Clear filters"
              className="h-9 text-sm px-3 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] cursor-pointer"
            >
              <X className="size-3.5 mr-1.5" aria-hidden="true" />
              <span>Clear filters</span>
            </Button>
          )}
        </div>

        {/* Counter & Keyboard hint row */}
        <div className="flex items-center justify-between text-caption text-[var(--ink-muted)] pt-1">
          <span className="font-medium text-[var(--ink)]">
            {hasActiveFilters
              ? `Showing ${filteredCount} of ${totalResults} postings`
              : `${totalResults} ${totalResults === 1 ? 'posting' : 'postings'} available`}
          </span>
          <span className="text-[var(--ink-subtle)] hidden sm:inline">
            Use j/k to navigate · s to save · Enter or click to open posting
          </span>
        </div>
      </div>
    </div>
  );
};
