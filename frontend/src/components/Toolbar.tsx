import React, { type RefObject } from 'react';
import { Search, X } from 'lucide-react';

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
    <div className="toolbar-sticky">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        {/* Controls row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 'var(--space-2)',
            alignItems: 'center',
          }}
        >
          {/* Text filter with '/' keyboard focus indicator */}
          <div style={{ position: 'relative', minWidth: '220px', gridColumn: 'span 2' }}>
            <Search
              size={14}
              style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--ink-subtle)',
              }}
              aria-hidden="true"
            />
            <input
              ref={searchInputRef}
              type="text"
              className="control-input"
              style={{ paddingLeft: '34px', paddingRight: '44px' }}
              placeholder="Filter by role, company, location..."
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
              aria-label="Filter results table"
            />
            <span
              className="mono"
              style={{
                position: 'absolute',
                right: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                fontSize: '11px',
                padding: '1px 5px',
                background: 'var(--surface-subtle)',
                border: '1px solid var(--border)',
                color: 'var(--ink-muted)',
                pointerEvents: 'none',
              }}
            >
              /
            </span>
          </div>

          {/* Provider / Platform Selector */}
          <div>
            <select
              className="control-select"
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
              aria-label="Filter by ATS provider"
            >
              <option value="">All platforms</option>
              {availableProviders.map((prov) => (
                <option key={prov} value={prov}>
                  {prov}
                </option>
              ))}
            </select>
          </div>

          {/* Work Model Selector */}
          <div>
            <select
              className="control-select"
              value={remoteFilter}
              onChange={(e) => setRemoteFilter(e.target.value)}
              aria-label="Filter by work model"
            >
              <option value="">All work models</option>
              <option value="remote">Remote only</option>
              <option value="hybrid">Hybrid</option>
              <option value="in_person">In-person</option>
            </select>
          </div>

          {/* Employment Type Selector */}
          {availableEmploymentTypes.length > 0 && (
            <div>
              <select
                className="control-select"
                value={employmentFilter}
                onChange={(e) => setEmploymentFilter(e.target.value)}
                aria-label="Filter by employment type"
              >
                <option value="">All employment types</option>
                {availableEmploymentTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Status count and quick filter chips row */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 'var(--space-2)',
            paddingTop: 'var(--space-1)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
            <span
              className="mono tabular"
              style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-muted)', fontWeight: 600 }}
            >
              Showing {filteredCount} of {totalResults} postings
            </span>

            <button
              type="button"
              className={`chip ${onlySalaryListed ? 'active' : ''}`}
              onClick={() => setOnlySalaryListed(!onlySalaryListed)}
              aria-pressed={onlySalaryListed}
            >
              Salary listed
            </button>

            <button
              type="button"
              className={`chip ${remoteFilter === 'remote' ? 'active' : ''}`}
              onClick={() => setRemoteFilter(remoteFilter === 'remote' ? '' : 'remote')}
              aria-pressed={remoteFilter === 'remote'}
            >
              Remote only
            </button>
          </div>

          {hasActiveFilters && (
            <button
              type="button"
              className="btn btn-sm"
              onClick={onClearFilters}
              style={{ height: '28px', fontSize: '11px', color: 'var(--accent)' }}
            >
              <X size={11} aria-hidden="true" />
              <span>Clear filters</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
