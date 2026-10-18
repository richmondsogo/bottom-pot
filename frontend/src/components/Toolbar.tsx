import React, { type RefObject } from 'react';
import { Search, X } from 'lucide-react';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Kbd } from './ui/kbd';

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
    onlySalaryListed
  );

  return (
    <div className="w-full border-b border-[var(--border)] bg-[var(--bg)] py-3">
      <div className="page-shell flex flex-col gap-3">
        {/* Filter controls row */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Keyword filter input */}
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search
              className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-[var(--ink-muted)] pointer-events-none"
              aria-hidden="true"
            />
            <Input
              ref={searchInputRef}
              id="table-search-input"
              name="tableSearch"
              type="text"
              className="h-8 pl-8 pr-8 text-small bg-transparent border-[var(--border)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus-visible:border-[var(--accent)]"
              placeholder="Filter by role, company, location..."
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
              aria-label="Filter results table"
            />
            <Kbd className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] pointer-events-none px-1 py-0 text-[var(--ink-subtle)]">
              /
            </Kbd>
          </div>

          {/* Platform selector */}
          <select
            id="platform-filter-select"
            name="platformFilter"
            value={providerFilter}
            onChange={(e) => setProviderFilter(e.target.value)}
            aria-label="Filter by ATS provider"
            className="h-8 px-2 text-small bg-transparent border border-[var(--border)] text-[var(--ink)] outline-none focus-visible:border-[var(--accent)] cursor-pointer"
          >
            <option value="">All platforms</option>
            {availableProviders.map((p) => (
              <option key={p} value={p}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>

          {/* Work model selector */}
          <select
            id="workmodel-filter-select"
            name="workModelFilter"
            value={remoteFilter}
            onChange={(e) => setRemoteFilter(e.target.value)}
            aria-label="Filter by work model"
            className="h-8 px-2 text-small bg-transparent border border-[var(--border)] text-[var(--ink)] outline-none focus-visible:border-[var(--accent)] cursor-pointer"
          >
            <option value="">All work models</option>
            <option value="remote">Remote</option>
            <option value="hybrid">Hybrid</option>
            <option value="in_person">In-person</option>
          </select>

          {/* Employment type selector */}
          {availableEmploymentTypes.length > 0 && (
            <select
              id="employment-filter-select"
              name="employmentFilter"
              value={employmentFilter}
              onChange={(e) => setEmploymentFilter(e.target.value)}
              aria-label="Filter by employment type"
              className="h-8 px-2 text-small bg-transparent border border-[var(--border)] text-[var(--ink)] outline-none focus-visible:border-[var(--accent)] cursor-pointer"
            >
              <option value="">All job types</option>
              {availableEmploymentTypes.map((et) => (
                <option key={et} value={et}>
                  {et.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </option>
              ))}
            </select>
          )}

          {/* Proper Toggle 1: Remote only */}
          <button
            type="button"
            role="switch"
            aria-checked={remoteFilter === 'remote'}
            onClick={() => setRemoteFilter(remoteFilter === 'remote' ? '' : 'remote')}
            className={`h-8 px-2.5 text-small border inline-flex items-center gap-1.5 transition-colors cursor-pointer select-none ${
              remoteFilter === 'remote'
                ? 'border-[var(--accent)] bg-[var(--accent-tint)] text-[var(--ink)] font-medium'
                : 'border-[var(--border)] bg-transparent text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
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
            className={`h-8 px-2.5 text-small border inline-flex items-center gap-1.5 transition-colors cursor-pointer select-none ${
              onlySalaryListed
                ? 'border-[var(--accent)] bg-[var(--accent-tint)] text-[var(--ink)] font-medium'
                : 'border-[var(--border)] bg-transparent text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
            }`}
          >
            <span
              className={`size-2 inline-block ${
                onlySalaryListed ? 'bg-[var(--accent)]' : 'bg-[var(--border-strong)]'
              }`}
            />
            <span>Salary listed</span>
          </button>

          {/* Clear active filters button */}
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearFilters}
              aria-label="Clear filters"
              className="h-8 text-small px-2 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)]"
            >
              <X className="size-3.5 mr-1" aria-hidden="true" />
              <span>Clear filters</span>
            </Button>
          )}
        </div>

        {/* Counter & Status */}
        <div className="flex items-center justify-between text-caption text-[var(--ink-muted)] pt-0.5">
          <span>
            {hasActiveFilters
              ? `Showing ${filteredCount} of ${totalResults}`
              : `${totalResults} ${totalResults === 1 ? 'posting' : 'postings'} available`}
          </span>
          <span className="text-[var(--ink-subtle)] hidden sm:inline">
            Use j/k to navigate · Enter or click to open posting
          </span>
        </div>
      </div>
    </div>
  );
};
