import React from 'react';
import type { NormalizedJob, SortField } from '../types';
import { isVisited } from '../lib/visited';
import { buildObjectiveScopeLabel } from '../lib/eligibility';
import { formatSalaryParts } from '../lib/normalize';
import { CompanyMark } from './CompanyMark';
import { STAGE_LABELS, findSavedJobEntry, type SavedJobEntry } from '../lib/savedJobs';
import { matchesJobIdentity } from '../lib/identity';
import { ArrowUpRight } from 'lucide-react';

interface ResultsCardsProps {
  jobs: NormalizedJob[];
  sortField?: SortField;
  selectedJobId: string | null;
  onSelectJob: (job: NormalizedJob) => void;
  savedJobsMap?: Record<string, SavedJobEntry>;
}

export const ResultsCards: React.FC<ResultsCardsProps> = ({
  jobs,
  sortField = null,
  selectedJobId,
  onSelectJob,
  savedJobsMap,
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
    const normalized = (model || '').toLowerCase().replace(/[\s-]/g, '_');
    if (!['remote', 'hybrid', 'in_person', 'onsite'].includes(normalized)) {
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
    let label = 'In-person';

    if (normalized === 'remote') {
      bg = 'var(--tag-remote-bg)';
      text = 'var(--tag-remote-text)';
      border = 'var(--tag-remote-border)';
      marker = 'var(--tag-remote-marker)';
      label = 'Remote';
    } else if (normalized === 'hybrid') {
      bg = 'var(--tag-hybrid-bg)';
      text = 'var(--tag-hybrid-text)';
      border = 'var(--tag-hybrid-border)';
      marker = 'var(--tag-hybrid-marker)';
      label = 'Hybrid';
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
          const elig = job.displayEligibility;
          const cardEligibilityText = elig
            ? elig.status === 'restricted'
              ? (elig.scopeLabel && !elig.scopeLabel.toLowerCase().includes('not eligible')
                  ? `Restricted · ${elig.scopeLabel}`
                  : elig.statusLabel || 'Restricted')
              : elig.status === 'eligible'
                ? (elig.combinedLabel?.replace(/^(Remote|Hybrid|Onsite)\s*·\s*/i, '') ||
                    elig.scopeLabel ||
                    elig.statusLabel ||
                    null)
                : (elig.scopeLabel || elig.statusLabel || null)
            : buildObjectiveScopeLabel(job.eligibility, job.work_model, job.location);
          const cardEligibilityTone =
            elig?.status === 'restricted'
              ? 'text-[var(--danger-text)]'
              : elig?.status === 'eligible'
                ? 'text-[var(--ink)] font-medium'
                : 'text-[var(--ink-muted)]';

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

              {/* Line 2: Monogram/Logo + Company (2-line clamp + slug) · Location */}
              <div className="flex items-start gap-2 text-small text-[var(--ink-muted)] min-w-0">
                <CompanyMark company={job.company} logoUrl={job.company_logo_url} companyDomain={job.company_domain} size="sm" />
                <div className="min-w-0 flex-1">
                  <div
                    className={`font-medium text-[var(--ink)] leading-snug line-clamp-2 break-words ${
                      job.companyIsModified ? 'underline decoration-dotted decoration-[var(--ink-subtle)] underline-offset-2 cursor-help' : ''
                    }`}
                    title={job.companyIsModified ? `Listed as: ${job.rawCompany}` : job.company}
                  >
                    {job.displayCompany}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-[var(--ink-subtle)] min-w-0">
                    <span className="font-mono lowercase shrink-0">{job.provider || 'ats'}</span>
                    {job.displayLocation && job.displayLocation !== '—' && (
                      <>
                        <span className="text-[var(--border-strong)]">·</span>
                        <span className="truncate">{job.displayLocation}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Line 3: Meta tags: Work & eligibility, Saved, Salary, Date */}
              <div className="flex items-end justify-between text-caption text-[var(--ink-muted)] pt-1 gap-2">
                <div className="flex flex-wrap items-start gap-2.5 min-w-0">
                  <div className="flex flex-col items-start gap-0.5 min-w-0">
                    {workModelTag}
                    {cardEligibilityText && (
                      <span className={`text-[11px] leading-tight line-clamp-1 ${cardEligibilityTone}`}>
                        {cardEligibilityText}
                      </span>
                    )}
                  </div>
                  {savedEntry && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-[11px] font-medium border border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--ink)] shrink-0">
                      {STAGE_LABELS[savedEntry.stage]}
                    </span>
                  )}
                  {salaryParts && (
                    salaryParts.period ? (
                      <div className="flex flex-col min-w-0" title={salaryParts.full}>
                        <span className="text-[11.5px] font-mono tabular-nums font-medium text-[var(--ink)] leading-snug break-words">
                          {salaryParts.range}
                        </span>
                        <span className="text-[10.5px] font-mono text-[var(--ink-subtle)] leading-tight">
                          {salaryParts.period}
                        </span>
                      </div>
                    ) : (
                      <span
                        className="text-[11.5px] font-mono tabular-nums font-medium text-[var(--ink)] leading-snug line-clamp-2 break-words"
                        title={salaryParts.full}
                      >
                        {salaryParts.range}
                      </span>
                    )
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <time
                    data-testid="job-age-badge"
                    data-freshness-tier={job.freshnessTier}
                    dateTime={job.postingDateIso}
                    className="inline-flex items-center px-1.5 py-0.5 rounded-sm font-mono text-[11px] font-medium tabular-nums"
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
            </div>
            </React.Fragment>
          );
        })}
      </div>
  );
};
