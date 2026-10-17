import React from 'react';
import type { NormalizedJob, SortField } from '../types';
import { getCompanyInitials, getCompanyTileColor } from '../lib/storage';
import { isVisited } from '../lib/visited';
import { hasAnySalary } from '../lib/normalize';
import { ArrowUp, ArrowDown, ArrowUpDown, ExternalLink } from 'lucide-react';

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
  // Determine if salary column should be displayed
  const showSalary = hasAnySalary(jobs);

  const getSortIndicator = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown size={11} style={{ opacity: 0.35, marginLeft: '4px' }} aria-hidden="true" />;
    }
    return sortAsc ? (
      <ArrowUp size={11} style={{ color: 'var(--accent)', marginLeft: '4px' }} aria-hidden="true" />
    ) : (
      <ArrowDown size={11} style={{ color: 'var(--accent)', marginLeft: '4px' }} aria-hidden="true" />
    );
  };

  const getAriaSort = (field: SortField): 'ascending' | 'descending' | 'none' => {
    if (sortField !== field) return 'none';
    return sortAsc ? 'ascending' : 'descending';
  };

  const renderWorkModelTag = (model: string | null | undefined) => {
    const normalized = (model || '').toLowerCase().replace(/[\s-]/g, '_');
    let className = 'work-model-tag work-model-unknown';
    let label = '—';

    if (normalized === 'remote') {
      className = 'work-model-tag work-model-remote';
      label = 'Remote';
    } else if (normalized === 'hybrid') {
      className = 'work-model-tag work-model-hybrid';
      label = 'Hybrid';
    } else if (normalized === 'in_person' || normalized === 'onsite') {
      className = 'work-model-tag work-model-in_person';
      label = 'In-person';
    }

    return (
      <span className={className}>
        <span className="marker" aria-hidden="true" />
        <span>{label}</span>
      </span>
    );
  };

  return (
    <div className="table-container table-desktop-view">
      <table className="results-table" aria-label="Job search results">
        <thead>
          <tr>
            <th
              scope="col"
              className="sortable"
              onClick={() => onSort('title')}
              aria-sort={getAriaSort('title')}
              style={{ width: '38%' }}
            >
              <div style={{ display: 'inline-flex', alignItems: 'center' }}>
                <span>Role</span>
                {getSortIndicator('title')}
              </div>
            </th>

            <th
              scope="col"
              className="sortable"
              onClick={() => onSort('company')}
              aria-sort={getAriaSort('company')}
              style={{ width: '22%' }}
            >
              <div style={{ display: 'inline-flex', alignItems: 'center' }}>
                <span>Company</span>
                {getSortIndicator('company')}
              </div>
            </th>

            <th scope="col" style={{ width: '16%' }}>
              Location
            </th>

            {showSalary && (
              <th
                scope="col"
                className="sortable"
                onClick={() => onSort('salary')}
                aria-sort={getAriaSort('salary')}
                style={{ width: '12%' }}
              >
                <div style={{ display: 'inline-flex', alignItems: 'center' }}>
                  <span>Salary</span>
                  {getSortIndicator('salary')}
                </div>
              </th>
            )}

            <th scope="col" style={{ width: '12%' }}>
              Work model
            </th>

            <th
              scope="col"
              className="sortable"
              onClick={() => onSort('date')}
              aria-sort={getAriaSort('date')}
              style={{ width: '10%' }}
            >
              <div style={{ display: 'inline-flex', alignItems: 'center' }}>
                <span>Posted</span>
                {getSortIndicator('date')}
              </div>
            </th>

            <th scope="col" style={{ width: '40px', textAlign: 'center' }}>
              <span className="sr-only">Actions</span>
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

            return (
              <tr
                key={job.id}
                className={`${isSelected ? 'selected' : ''} ${isKeyboardActive ? 'keyboard-active' : ''}`}
                onClick={() => onSelectJob(job)}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectJob(job);
                  }
                }}
                style={{
                  outline: isKeyboardActive ? '2px solid var(--accent)' : 'none',
                  outlineOffset: '-2px',
                }}
              >
                {/* Role / Title column */}
                <td>
                  <div
                    className={`line-clamp-2 ${visited ? 'title-visited' : ''}`}
                    title={job.title}
                    style={{
                      fontWeight: 600,
                      color: visited ? 'var(--ink-muted)' : 'var(--ink)',
                      lineHeight: 1.35,
                    }}
                  >
                    {job.displayTitle}
                  </div>
                </td>

                {/* Company & ATS Source column */}
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    {/* Restrained deterministic square monogram tile */}
                    <div
                      className="company-tile"
                      style={{
                        backgroundColor: tileColor.bg,
                        color: tileColor.color,
                        borderColor: tileColor.border,
                      }}
                      aria-hidden="true"
                    >
                      {initials}
                    </div>

                    <div style={{ minWidth: 0, overflow: 'hidden' }}>
                      <div
                        style={{
                          fontWeight: 600,
                          color: 'var(--ink)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                        title={job.company}
                      >
                        {job.company || '—'}
                      </div>
                      <div
                        className="mono"
                        style={{
                          fontSize: '11px',
                          color: 'var(--ink-subtle)',
                          textTransform: 'lowercase',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {job.provider || 'ats'}
                      </div>
                    </div>
                  </div>
                </td>

                {/* Location column */}
                <td>
                  <span
                    style={{
                      color: job.displayLocation === '—' ? 'var(--ink-subtle)' : 'var(--ink)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      display: 'block',
                    }}
                    title={job.location || undefined}
                  >
                    {job.displayLocation}
                  </span>
                </td>

                {/* Salary column (Auto-hidden if whole dataset lacks salary) */}
                {showSalary && (
                  <td>
                    <span
                      className="mono tabular"
                      style={{
                        color: job.displaySalary === '—' ? 'var(--ink-subtle)' : 'var(--ink)',
                        fontSize: 'var(--text-xs)',
                      }}
                    >
                      {job.displaySalary}
                    </span>
                  </td>
                )}

                {/* Work model column */}
                <td>{renderWorkModelTag(job.work_model)}</td>

                {/* Posted date column */}
                <td>
                  <span
                    className="mono tabular"
                    style={{
                      fontSize: 'var(--text-xs)',
                      color: job.displayPostedDate === '—' ? 'var(--ink-subtle)' : 'var(--ink-muted)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {job.displayPostedDate}
                  </span>
                </td>

                {/* Action quick link */}
                <td style={{ textAlign: 'center' }}>
                  <button
                    type="button"
                    className="btn btn-sm"
                    style={{
                      padding: '4px',
                      height: '24px',
                      width: '24px',
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--ink-subtle)',
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectJob(job);
                    }}
                    title="View details"
                    aria-label={`View details for ${job.title}`}
                  >
                    <ExternalLink size={12} />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
