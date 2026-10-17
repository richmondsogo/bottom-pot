import React from 'react';
import type { NormalizedJob } from '../types';
import { getCompanyInitials, getCompanyTileColor } from '../lib/storage';
import { isVisited } from '../lib/visited';

interface ResultsCardsProps {
  jobs: NormalizedJob[];
  selectedJobId: string | null;
  onSelectJob: (job: NormalizedJob) => void;
}

export const ResultsCards: React.FC<ResultsCardsProps> = ({
  jobs,
  selectedJobId,
  onSelectJob,
}) => {
  return (
    <div className="cards-mobile-view" role="list" aria-label="Job postings list">
      {jobs.map((job) => {
        const visited = isVisited(job.apply_url || job.id);
        const isSelected = selectedJobId === job.id;
        const initials = getCompanyInitials(job.company);
        const tileColor = getCompanyTileColor(job.company);

        return (
          <div
            key={job.id}
            role="listitem"
            className="mobile-job-card"
            style={{
              borderColor: isSelected ? 'var(--accent)' : 'var(--border)',
              background: isSelected ? 'var(--surface-selected)' : 'var(--surface)',
            }}
            onClick={() => onSelectJob(job)}
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelectJob(job);
              }
            }}
          >
            {/* Top row: Monogram + Company + Provider */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
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
                <div>
                  <span style={{ fontWeight: 600, color: 'var(--ink)', fontSize: 'var(--text-ui)' }}>
                    {job.company || '—'}
                  </span>
                  <span
                    className="mono"
                    style={{ fontSize: '11px', color: 'var(--ink-subtle)', marginLeft: '6px' }}
                  >
                    via {job.provider}
                  </span>
                </div>
              </div>

              {job.posted_at && (
                <span
                  className="mono tabular"
                  style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-subtle)' }}
                >
                  {job.displayPostedDate}
                </span>
              )}
            </div>

            {/* Role Title */}
            <div
              className={`line-clamp-2 ${visited ? 'title-visited' : ''}`}
              style={{
                fontSize: '15px',
                fontWeight: 700,
                color: visited ? 'var(--ink-muted)' : 'var(--ink)',
                lineHeight: 1.3,
                marginTop: 'var(--space-1)',
              }}
            >
              {job.displayTitle}
            </div>

            {/* Location & Tags row */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 'var(--space-2)',
                marginTop: 'var(--space-2)',
                paddingTop: 'var(--space-2)',
                borderTop: '1px solid var(--border-subtle)',
              }}
            >
              <span style={{ color: 'var(--ink-muted)', fontSize: 'var(--text-xs)' }}>
                {job.displayLocation}
              </span>

              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                {job.displaySalary !== '—' && (
                  <span
                    className="mono tabular"
                    style={{
                      fontSize: '11px',
                      background: 'var(--surface-subtle)',
                      padding: '2px 6px',
                      border: '1px solid var(--border)',
                    }}
                  >
                    {job.displaySalary}
                  </span>
                )}

                {job.work_model && (
                  <span
                    className="mono"
                    style={{
                      fontSize: '11px',
                      padding: '2px 6px',
                      background:
                        job.work_model === 'remote' ? 'var(--tag-remote-bg)' : 'var(--surface-subtle)',
                      color:
                        job.work_model === 'remote' ? 'var(--tag-remote-text)' : 'var(--ink)',
                      border: '1px solid var(--border)',
                      textTransform: 'capitalize',
                    }}
                  >
                    {job.work_model.replace('_', ' ')}
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
