import React from 'react';
import { Globe, Banknote, MapPin } from 'lucide-react';

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
  onResetColumns: () => void;
  totalRawCount: number;
  filteredCount: number;
  currentPage: number;
  totalPages: number;
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
  onResetColumns,
  totalRawCount,
  filteredCount,
  currentPage,
  totalPages,
  setCurrentPage,
}) => {
  return (
    <>
      {/* Standard Filter Controls */}
      <div className="table-controls" aria-label="Filter controls">
        <label className="filter-field filter-search">
          <span>Filter results (Press / to focus)</span>
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
          <span>Provider</span>
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
          <span>Work model</span>
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
            <option value="onsite">On-site / unspecified</option>
          </select>
        </label>
        <label className="filter-field">
          <span>Job type</span>
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
        <button
          id="clearFiltersBtn"
          className="text-button"
          type="button"
          onClick={onClearFilters}
        >
          Clear filters
        </button>
        <button
          id="resetColsBtn"
          className="text-button"
          type="button"
          onClick={onResetColumns}
          title="Reset column widths to default"
        >
          Reset columns
        </button>
      </div>

      {/* Quick Filter Badges Bar */}
      <div className="quick-filters-bar">
        <button
          type="button"
          className={`quick-filter-pill ${remoteFilter === 'remote' ? 'active' : ''}`}
          onClick={() => {
            setRemoteFilter(remoteFilter === 'remote' ? '' : 'remote');
            setCurrentPage(1);
          }}
        >
          <Globe className="w-3.5 h-3.5 inline mr-1" /> Remote Only
        </button>
        <button
          type="button"
          className={`quick-filter-pill ${onlySalaryListed ? 'active' : ''}`}
          onClick={() => {
            setOnlySalaryListed(!onlySalaryListed);
            setCurrentPage(1);
          }}
        >
          <Banknote className="w-3.5 h-3.5 inline mr-1" /> Salary Disclosed
        </button>
        <button
          type="button"
          className={`quick-filter-pill ${onlyNigerianBoards ? 'active' : ''}`}
          onClick={() => {
            setOnlyNigerianBoards(!onlyNigerianBoards);
            setCurrentPage(1);
          }}
        >
          <MapPin className="w-3.5 h-3.5 inline mr-1" /> Nigerian Boards
        </button>
      </div>

      <div className="filter-summary">
        <p id="filterSummary" aria-live="polite" style={{ margin: 0 }}>
          {totalRawCount === filteredCount
            ? `${totalRawCount} result${totalRawCount === 1 ? '' : 's'}`
            : `Showing ${filteredCount} of ${totalRawCount} results`}
        </p>
        {totalPages > 1 && (
          <span className="page-info">
            Page {currentPage} of {totalPages}
          </span>
        )}
      </div>
    </>
  );
};
