import React from 'react';

interface FilterBarProps {
  tableSearchInputRef: React.RefObject<HTMLInputElement | null>;
  tableSearch: string;
  setTableSearch: (val: string) => void;
  providerFilter: string;
  setProviderFilter: (val: string) => void;
  availableProviders: string[];
  remoteFilter: string;
  setRemoteFilter: (val: string) => void;
  employmentFilter: string;
  setEmploymentFilter: (val: string) => void;
  availableEmploymentTypes: string[];
  onlySalaryListed: boolean;
  setOnlySalaryListed: (val: boolean) => void;
  onlyNigerianBoards: boolean;
  setOnlyNigerianBoards: (val: boolean) => void;
  onClearFilters: () => void;
  setCurrentPage: React.Dispatch<React.SetStateAction<number>>;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  tableSearchInputRef,
  tableSearch,
  setTableSearch,
  providerFilter,
  setProviderFilter,
  availableProviders,
  remoteFilter,
  setRemoteFilter,
  employmentFilter,
  setEmploymentFilter,
  availableEmploymentTypes,
  onlySalaryListed,
  setOnlySalaryListed,
  onlyNigerianBoards,
  setOnlyNigerianBoards,
  onClearFilters,
  setCurrentPage,
}) => {
  return (
    <div className="filter-section">
      {/* Standard Filter Controls */}
      <div className="table-controls" aria-label="Filter controls">
        <label className="filter-field filter-search">
          <span className="label">Filter results (Press / to focus)</span>
          <input
            id="tableSearch"
            ref={tableSearchInputRef}
            type="search"
            placeholder="Role, company, location..."
            autoComplete="off"
            value={tableSearch}
            onChange={(e) => {
              setTableSearch(e.target.value);
              setCurrentPage(1);
            }}
          />
        </label>
        <label className="filter-field">
          <span className="label">Provider</span>
          <select
            id="providerFilter"
            value={providerFilter}
            onChange={(e) => {
              setProviderFilter(e.target.value);
              setCurrentPage(1);
            }}
          >
            <option value="">All providers</option>
            {availableProviders.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="filter-field">
          <span className="label">Work model</span>
          <select
            id="remoteFilter"
            value={remoteFilter}
            onChange={(e) => {
              setRemoteFilter(e.target.value);
              setCurrentPage(1);
            }}
          >
            <option value="">Any model</option>
            <option value="remote">Remote</option>
            <option value="hybrid">Hybrid</option>
            <option value="in_person">In-person</option>
            <option value="onsite">On-site</option>
            <option value="not_specified">Not specified</option>
          </select>
        </label>
        <label className="filter-field">
          <span className="label">Job type</span>
          <select
            id="employmentFilter"
            value={employmentFilter}
            onChange={(e) => {
              setEmploymentFilter(e.target.value);
              setCurrentPage(1);
            }}
          >
            <option value="">All types</option>
            {availableEmploymentTypes.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <div className="filter-clear-wrap">
          <button
            id="clearFiltersBtn"
            className="btn btn-text"
            type="button"
            onClick={onClearFilters}
          >
            Clear filters
          </button>
        </div>
      </div>

      {/* Quick Filter Square Chips: small squares, not pills, no icons, aria-pressed */}
      <div className="quick-filters-bar" role="group" aria-label="Quick filters">
        <button
          type="button"
          aria-pressed={remoteFilter === 'remote'}
          className={`chip quick-filter-pill ${remoteFilter === 'remote' ? 'active' : ''}`}
          onClick={() => {
            setRemoteFilter(remoteFilter === 'remote' ? '' : 'remote');
            setCurrentPage(1);
          }}
        >
          Remote Only
        </button>
        <button
          type="button"
          aria-pressed={onlySalaryListed}
          className={`chip quick-filter-pill ${onlySalaryListed ? 'active' : ''}`}
          onClick={() => {
            setOnlySalaryListed(!onlySalaryListed);
            setCurrentPage(1);
          }}
        >
          Salary Disclosed
        </button>
        <button
          type="button"
          aria-pressed={onlyNigerianBoards}
          className={`chip quick-filter-pill ${onlyNigerianBoards ? 'active' : ''}`}
          onClick={() => {
            setOnlyNigerianBoards(!onlyNigerianBoards);
            setCurrentPage(1);
          }}
        >
          Nigerian Boards
        </button>
      </div>
    </div>
  );
};
