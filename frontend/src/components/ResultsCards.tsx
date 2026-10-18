import React from 'react';
import type { NormalizedJob } from '../types';
import { getCompanyInitials, getCompanyTileColor } from '../lib/storage';
import { isVisited } from '../lib/visited';
import { ArrowUpRight } from 'lucide-react';

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
  const renderWorkModelTag = (model: string | null | undefined) => {
    if (!model) return null;
    const normalized = model.toLowerCase().replace(/[\s-]/g, '_');
    if (!['remote', 'hybrid', 'in_person', 'onsite'].includes(normalized)) {
      return null;
    }

    let bg = 'var(--tag-inperson-bg)';
    let text = 'var(--tag-inperson-text)';
    let marker = 'var(--tag-inperson-marker)';
    let label = 'In-person';

    if (normalized === 'remote') {
      bg = 'var(--tag-remote-bg)';
      text = 'var(--tag-remote-text)';
      marker = 'var(--tag-remote-marker)';
      label = 'Remote';
    } else if (normalized === 'hybrid') {
      bg = 'var(--tag-hybrid-bg)';
      text = 'var(--tag-hybrid-text)';
      marker = 'var(--tag-hybrid-marker)';
      label = 'Hybrid';
    }

    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] font-medium border border-transparent shrink-0"
        style={{ backgroundColor: bg, color: text }}
      >
        <span
          className="size-1.5 shrink-0"
          style={{ backgroundColor: marker }}
          aria-hidden="true"
        />
        <span>{label}</span>
      </span>
    );
  };

  return (
    <div className="cards-mobile-view flex flex-col divide-y divide-[var(--border-subtle)] pb-16" role="list" aria-label="Job postings list">
      {jobs.map((job) => {
          const visited = isVisited(job.apply_url || job.id);
          const isSelected = selectedJobId === job.id;
          const initials = getCompanyInitials(job.company);
          const tileColor = getCompanyTileColor(job.company);
          const workModelTag = renderWorkModelTag(job.work_model);

          return (
            <div
              key={job.id}
              role="listitem"
              className={`mobile-job-card py-3 px-1 flex flex-col gap-1 cursor-pointer transition-colors ${
                isSelected ? 'bg-[var(--surface-selected)]' : 'active:bg-[var(--surface-hover)]'
              }`}
              onClick={() => onSelectJob(job)}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectJob(job);
                }
              }}
              style={{
                borderLeft: isSelected ? '3px solid var(--accent)' : '3px solid transparent',
              }}
            >
              {/* Line 1: Role Title */}
              <div className="flex items-start justify-between gap-2 min-w-0">
                <span
                  className={`line-clamp-2 text-body font-medium leading-tight ${
                    visited ? 'title-visited' : 'text-[var(--ink)]'
                  }`}
                >
                  {job.displayTitle}
                </span>
                <ArrowUpRight className="size-3.5 text-[var(--ink-muted)] shrink-0 mt-0.5" aria-hidden="true" />
              </div>

              {/* Line 2: Monogram + Company · Location */}
              <div className="flex items-center gap-1.5 text-small text-[var(--ink-muted)] min-w-0">
                <div
                  className="size-4 flex items-center justify-center font-bold text-[8.5px] shrink-0 border"
                  style={{
                    backgroundColor: tileColor.bg,
                    color: tileColor.color,
                    borderColor: tileColor.border,
                  }}
                  aria-hidden="true"
                >
                  {initials}
                </div>
                <span className="font-medium text-[var(--ink)] truncate max-w-[140px]">
                  {job.displayCompany}
                </span>
                <span className="text-[var(--border-strong)]">·</span>
                <span className="truncate flex-1">
                  {job.displayLocation}
                </span>
              </div>

              {/* Line 3: Meta tags: Work model, Salary, Date */}
              <div className="flex items-center justify-between text-caption text-[var(--ink-muted)] pt-1">
                <div className="flex items-center gap-2">
                  {workModelTag}
                  {job.displaySalary && job.displaySalary !== '—' && (
                    <span className="text-[var(--ink)] font-medium text-[11.5px]">
                      {job.displaySalary}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <time dateTime={job.postingDateIso} className="font-mono text-xs tabular-nums text-[var(--ink-muted)]">
                    {job.relativePostedDate}
                  </time>
                  <span className="font-mono text-xs text-[var(--ink-subtle)] lowercase">
                    {job.provider}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
  );
};
