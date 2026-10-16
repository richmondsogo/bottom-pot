import React from 'react';
import type { NormalizedJob, ColumnDef, SortField } from '../types';
import { formatFreshness } from '../lib/normalize';
import { getCompanyInitials, getCompanyAvatarColor } from '../lib/storage';
import { DetailsPanel } from './DetailsPanel';

interface ResultsTableProps {
  density: 'comfortable' | 'compact';
  resultsWrapRef: React.RefObject<HTMLDivElement | null>;
  detailPanelRef: React.RefObject<HTMLDivElement | null>;
  totalTableWidth: number;
  columns: ColumnDef[];
  colWidths: Record<string, number>;
  extraRoleWidth: number;
  sortField: SortField;
  sortAsc: boolean;
  onSort: (field: SortField) => void;
  onResizePointerDown: (colId: string, e: React.PointerEvent) => void;
  onResetSingleColumn: (colId: string) => void;
  paginatedResults: NormalizedJob[];
  expandedJobId: string | null;
  onToggleExpand: (id: string) => void;
  activeRowIndex: number;
  onSetActiveRowIndex: (idx: number) => void;
  copiedId: string | null;
  onCopyApplyUrl: (url: string, id: string) => void;
  visibleWrapWidth: number;
  filteredResultsCount: number;
  rawResultsCount: number;
  onClearFilters: () => void;
  totalPages: number;
  currentPage: number;
  onSetCurrentPage: (updater: (prev: number) => number) => void;
  pageSize: number;
  onSetPageSize: (size: number) => void;
  totalSortedCount: number;
}

export const ResultsTable: React.FC<ResultsTableProps> = ({
  density,
  resultsWrapRef,
  detailPanelRef,
  totalTableWidth,
  columns,
  colWidths,
  extraRoleWidth,
  sortField,
  sortAsc,
  onSort,
  onResizePointerDown,
  onResetSingleColumn,
  paginatedResults,
  expandedJobId,
  onToggleExpand,
  activeRowIndex,
  onSetActiveRowIndex,
  copiedId,
  onCopyApplyUrl,
  visibleWrapWidth,
  filteredResultsCount,
  rawResultsCount,
  onClearFilters,
  totalPages,
  currentPage,
  onSetCurrentPage,
  pageSize,
  onSetPageSize,
  totalSortedCount,
}) => {
  return (
    <>
      <div className={`results-wrap density-${density}`} ref={resultsWrapRef}>
        <table style={{ width: `max(100%, ${totalTableWidth}px)` }}>
          <colgroup>
            {columns.map((col) => {
              const width =
                col.id === 'role' ? colWidths[col.id] + extraRoleWidth : colWidths[col.id];
              return <col key={col.id} style={{ width: `${width}px` }} />;
            })}
          </colgroup>
          <thead>
            <tr>
              {columns.map((col) => {
                const isSortable = !!col.sortField;
                const isSorted = isSortable && sortField === col.sortField;
                return (
                  <th
                    key={col.id}
                    className={isSortable ? `sortable ${isSorted ? 'sorted' : ''}` : ''}
                    onClick={isSortable ? () => onSort(col.sortField!) : undefined}
                  >
                    <div className="th-content" title={col.label}>
                      <span>{col.label}</span>
                      {isSortable && (
                        <span className="sort-arrow" aria-hidden="true">
                          {isSorted ? (sortAsc ? '↑' : '↓') : '↕'}
                        </span>
                      )}
                    </div>
                    <div
                      className="col-resize-handle"
                      role="separator"
                      tabIndex={0}
                      aria-orientation="vertical"
                      aria-label={`Resize ${col.id} column`}
                      title="Drag to resize, double-click to reset"
                      onPointerDown={(e) => onResizePointerDown(col.id, e)}
                      onDoubleClick={(e) => {
                        e.stopPropagation();
                        onResetSingleColumn(col.id);
                      }}
                    />
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody id="resultsBody">
            {paginatedResults.map((job, idx) => {
              const isExpanded = expandedJobId === job.id;
              const isActive = activeRowIndex === idx;

              const hasWorkModel =
                job.work_model === 'remote' ||
                job.work_model === 'hybrid' ||
                job.work_model === 'in_person';

              const modelBadgeClass =
                job.work_model === 'remote'
                  ? 'badge-remote'
                  : job.work_model === 'hybrid'
                    ? 'badge-hybrid'
                    : 'badge-onsite';

              const modelBadgeText =
                job.work_model === 'remote'
                  ? 'Remote'
                  : job.work_model === 'hybrid'
                    ? 'Hybrid'
                    : 'In-person';

              const tooltip = job.work_model_source
                ? `Source: ${job.work_model_source}${job.work_model_evidence ? ` (${job.work_model_evidence})` : ''}`
                : undefined;

              const dateTooltip = `${job.displayPostedDate}${
                job.scraped_at ? ` · ${formatFreshness(job.scraped_at)}` : ''
              }`;

              const avatarStyle = getCompanyAvatarColor(job.company);
              const initials = getCompanyInitials(job.company);

              return (
                <React.Fragment key={job.id}>
                  <tr
                    tabIndex={0}
                    role="row"
                    aria-selected={isActive}
                    className={`${isActive ? 'row-active' : ''} ${isExpanded ? 'row-expanded' : ''}`}
                    onFocus={() => onSetActiveRowIndex(idx)}
                    onClick={() => onSetActiveRowIndex(idx)}
                  >
                    <td title={job.displayTitle}>
                      <span className="cell-role">{job.displayTitle}</span>
                    </td>
                    <td title={job.company}>
                      <div className="company-cell">
                        <span className="company-avatar" style={avatarStyle}>
                          {initials}
                        </span>
                        <span className="company-name">{job.company}</span>
                      </div>
                    </td>
                    <td title={job.displayLocation}>
                      <span className="cell-ellipsis">{job.displayLocation}</span>
                    </td>
                    <td title={job.displaySalary} className="cell-tabular">
                      <span className="cell-ellipsis">
                        <span
                          className={`salary-text ${job.displaySalary !== 'Not listed' ? 'salary-listed' : ''}`}
                        >
                          {job.displaySalary}
                        </span>
                      </span>
                    </td>
                    <td title={job.displayEmployment}>
                      <span className="cell-ellipsis">{job.displayEmployment}</span>
                    </td>
                    <td title={tooltip}>
                      <span className="cell-ellipsis">
                        {hasWorkModel ? (
                          <span className={`badge ${modelBadgeClass}`}>
                            {modelBadgeText}
                          </span>
                        ) : (
                          <span className="cell-muted" title="Not specified in the posting">
                            —
                          </span>
                        )}
                      </span>
                    </td>
                    <td title={dateTooltip} className="cell-tabular">
                      <span className="cell-ellipsis">
                        {job.relativePostedDate || job.displayPostedDate}
                      </span>
                    </td>
                    <td title={job.provider}>
                      <span className="cell-ellipsis">
                        <span className="badge badge-source">{job.provider}</span>
                      </span>
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="btn btn-text detail-toggle"
                          type="button"
                          aria-expanded={isExpanded}
                          onClick={(e) => {
                            e.stopPropagation();
                            onToggleExpand(job.id);
                          }}
                        >
                          {isExpanded ? 'Hide details' : 'Details'}
                        </button>
                        <a
                          href={job.apply_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="apply-link"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Apply -&gt;
                        </a>
                      </div>
                    </td>
                  </tr>

                  {isExpanded && (
                    <tr className="detail-row">
                      <td colSpan={columns.length}>
                        <DetailsPanel
                          ref={detailPanelRef}
                          job={job}
                          visibleWrapWidth={visibleWrapWidth}
                          modelClass={modelBadgeClass}
                          tooltip={tooltip}
                          copiedId={copiedId}
                          onCopyApplyUrl={onCopyApplyUrl}
                        />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>

        {/* Empty state */}
        {filteredResultsCount === 0 && (
          <div id="emptyState" className="empty-state">
            <p className="empty-message">
              {rawResultsCount > 0
                ? 'No job listings match your current filters.'
                : 'No matching postings were returned for this search.'}
            </p>
            {rawResultsCount > 0 && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onClearFilters}
              >
                Clear filters
              </button>
            )}
          </div>
        )}
      </div>

      {/* Pagination Bar */}
      {totalPages > 1 && (
        <div className="pagination-bar">
          <div className="pagination-controls">
            <button
              type="button"
              className="btn btn-secondary page-btn"
              disabled={currentPage <= 1}
              onClick={() => onSetCurrentPage((p) => Math.max(1, p - 1))}
            >
              &larr; Previous
            </button>
            <span className="page-info mono">
              Page {currentPage} of {totalPages} ({totalSortedCount} items)
            </span>
            <button
              type="button"
              className="btn btn-secondary page-btn"
              disabled={currentPage >= totalPages}
              onClick={() => onSetCurrentPage((p) => Math.min(totalPages, p + 1))}
            >
              Next &rarr;
            </button>
          </div>
          <div className="pagination-size-wrap">
            <span className="label">Show per page:</span>
            {[20, 50, 100].map((size) => (
              <button
                key={size}
                type="button"
                className={`chip ${pageSize === size ? 'active' : ''}`}
                onClick={() => {
                  onSetPageSize(size);
                  onSetCurrentPage(() => 1);
                }}
              >
                {size}
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
};
