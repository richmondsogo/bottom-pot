import React from 'react';
import type { NormalizedJob, SortField } from '../types';
import { isVisited } from '../lib/visited';
import { formatSalaryParts, formatWorkModelLabel, normalizeWorkModelKind } from '../lib/normalize';
import { buildMobileCardMeta, handleMobileQuickSaveClick } from '../lib/mobileCardMeta';
import { CompanyMark } from './CompanyMark';
import { STAGE_LABELS, findSavedJobEntry, type SavedJobEntry } from '../lib/savedJobs';
import { matchesJobIdentity } from '../lib/identity';
import { Bookmark } from 'lucide-react';

interface ResultsCardsProps {
  jobs: NormalizedJob[];
  sortField?: SortField;
  selectedJobId: string | null;
  onSelectJob: (job: NormalizedJob) => void;
  savedJobsMap?: Record<string, SavedJobEntry>;
  onToggleSave?: (job: NormalizedJob) => void;
  mode?: 'user' | 'admin';
}

export const ResultsCards: React.FC<ResultsCardsProps> = ({
  jobs,
  sortField = null,
  selectedJobId,
  onSelectJob,
  savedJobsMap,
  onToggleSave,
  mode = 'user',
}) => {
  const showOlderDivider = !sortField;
  const firstStaleIndex = showOlderDivider
    ? jobs.findIndex((j) => j.freshnessTier === 'stale')
    : -1;
  const staleCount =
    showOlderDivider && firstStaleIndex !== -1
      ? jobs.filter((j) => j.freshnessTier === 'stale').length
      : 0;
  const renderWorkModelTag = (model: string | null | undefined) => {
    const kind = normalizeWorkModelKind(model);
    const label = formatWorkModelLabel(model);
    if (!kind || !label) {
      return (
        <span
          data-testid="work-model-not-stated"
          className="text-[11px] text-[var(--ink-subtle)]"
        >
          Not stated
        </span>
      );
    }

    let bg = 'var(--tag-inperson-bg)';
    let text = 'var(--tag-inperson-text)';
    let border = 'var(--tag-inperson-border)';
    let marker = 'var(--tag-inperson-marker)';

    if (kind === 'remote') {
      bg = 'var(--tag-remote-bg)';
      text = 'var(--tag-remote-text)';
      border = 'var(--tag-remote-border)';
      marker = 'var(--tag-remote-marker)';
    } else if (kind === 'hybrid') {
      bg = 'var(--tag-hybrid-bg)';
      text = 'var(--tag-hybrid-text)';
      border = 'var(--tag-hybrid-border)';
      marker = 'var(--tag-hybrid-marker)';
    }

    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[11px] font-medium border shrink-0"
        style={{ backgroundColor: bg, color: text, borderColor: border }}
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
      {jobs.map((job, index) => {
          const visited = isVisited(job.apply_url || job.id);
          const isSelected = selectedJobId ? matchesJobIdentity(job, selectedJobId) : false;
          const savedEntry = savedJobsMap ? findSavedJobEntry(job, savedJobsMap) : null;
          const workModelTag = renderWorkModelTag(job.work_model);
          const salaryParts = formatSalaryParts(job.salary);
          const meta = buildMobileCardMeta(job);

          return (
            <React.Fragment key={job.id}>
              {index === firstStaleIndex && staleCount > 0 && (
                <div
                  data-testid="older-postings-divider"
                  role="separator"
                  className="older-postings-divider px-3 py-2 text-[11px] font-medium text-[var(--ink-muted)] bg-[var(--surface-subtle)] uppercase tracking-wider"
                >
                  Older postings ({staleCount}) · Posted over 90 days ago
                </div>
              )}
              <div
                role="listitem"
                data-freshness-tier={job.freshnessTier}
                className={`mobile-job-card py-3 px-1 flex flex-col gap-1.5 cursor-pointer transition-colors ${
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
                {/* Line 1: Company + freshness + 44x44px quick-save toggle */}
                <div className="flex items-center justify-between gap-2 min-w-0">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <CompanyMark
                      company={job.company}
                      logoUrl={job.company_logo_url}
                      companyDomain={job.company_domain}
                      size="sm"
                    />
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span
                        className={`font-medium text-[13px] text-[var(--ink)] truncate ${
                          job.companyIsModified
                            ? 'underline decoration-dotted decoration-[var(--ink-subtle)] underline-offset-2'
                            : ''
                        }`}
                        title={job.companyIsModified ? `Listed as: ${job.rawCompany}` : job.company}
                      >
                        {job.displayCompany}
                      </span>
                      <span className="text-[var(--border-strong)] shrink-0" aria-hidden="true">
                        ·
                      </span>
                      <time
                        data-testid="job-age-badge"
                        data-freshness-tier={job.freshnessTier}
                        dateTime={job.postingDateIso}
                        className={`inline-flex items-center rounded-sm font-mono text-[11px] font-medium tabular-nums shrink-0 ${
                          job.freshnessTier === 'evergreen' || job.freshnessTier === 'stale'
                            ? 'px-1.5 py-0.5'
                            : 'px-0 py-0'
                        }`}
                        style={
                          job.freshnessTier === 'evergreen'
                            ? {
                                backgroundColor: 'var(--tag-remote-bg)',
                                color: 'var(--tag-remote-text)',
                              }
                            : job.freshnessTier === 'stale'
                              ? {
                                  backgroundColor: 'var(--tag-hybrid-bg)',
                                  color: 'var(--tag-hybrid-text)',
                                }
                              : {
                                  color: 'var(--ink-muted)',
                                }
                        }
                      >
                        {job.ageBadgeLabel}
                      </time>
                    </div>
                  </div>

                  <button
                    type="button"
                    data-testid="mobile-save-toggle"
                    aria-label={savedEntry ? 'Remove from shortlist' : 'Save to shortlist'}
                    aria-pressed={Boolean(savedEntry)}
                    title={savedEntry ? 'Remove from shortlist' : 'Save to shortlist'}
                    onClick={(e) => handleMobileQuickSaveClick(e, job, onToggleSave)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.stopPropagation();
                      }
                    }}
                    className={`size-11 -mr-2 -my-1.5 rounded-md inline-flex items-center justify-center shrink-0 transition-colors cursor-pointer ${
                      savedEntry
                        ? 'text-[var(--ink)] bg-[var(--surface-subtle)]'
                        : 'text-[var(--ink-subtle)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)]'
                    }`}
                  >
                    <Bookmark
                      className={`size-4 ${savedEntry ? 'fill-[var(--ink)] text-[var(--ink)]' : ''}`}
                      aria-hidden="true"
                    />
                  </button>
                </div>

                {/* Line 2: Full-width job title (2-line clamp, zero trailing icon) */}
                <div
                  className={`line-clamp-2 text-[15px] font-medium leading-snug break-words ${
                    visited ? 'title-visited' : 'text-[var(--ink)]'
                  }`}
                  title={job.title}
                >
                  {job.displayTitle}
                </div>

                {/* Line 3: Dedicated full-width salary line (rendered only if salary exists) */}
                {salaryParts && (
                  <div
                    data-testid="mobile-salary-line"
                    className="text-[13px] font-mono tabular-nums font-medium text-[var(--ink)] leading-snug break-words"
                    title={salaryParts.full}
                  >
                    <span>{salaryParts.range}</span>
                    {salaryParts.period && (
                      <span className="text-[12px] font-normal text-[var(--ink-muted)] ml-1">
                        {salaryParts.period}
                      </span>
                    )}
                  </div>
                )}

                {/* Line 4: Deduplicated metadata strip */}
                <div
                  data-testid="mobile-meta-strip"
                  className="flex flex-wrap items-center gap-x-1 gap-y-1 text-xs leading-snug pt-0.5 text-[var(--ink-muted)]"
                >
                  {workModelTag}
                  {meta.combinedMetaParts.map((part, idx) => (
                    <React.Fragment key={`${job.id}-meta-${idx}`}>
                      <span className="text-[var(--border-strong)]" aria-hidden="true">
                        ·
                      </span>
                      <span className={`break-words ${part.toneClass}`}>{part.text}</span>
                    </React.Fragment>
                  ))}
                  {mode === 'admin' && (
                    <>
                      <span className="text-[var(--border-strong)]" aria-hidden="true">
                        ·
                      </span>
                      <span className="font-mono text-[11px] lowercase text-[var(--ink-subtle)]">
                        {job.provider || 'ats'}
                      </span>
                    </>
                  )}
                  {savedEntry && savedEntry.stage !== 'saved' && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-[11px] font-medium border border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--ink)] shrink-0">
                      {STAGE_LABELS[savedEntry.stage]}
                    </span>
                  )}
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
  );
};
