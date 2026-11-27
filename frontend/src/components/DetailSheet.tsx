import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import type { NormalizedJob } from '../types';
import {
  EMPTY_VALUE,
  extractDomain,
  formatWorkModelLabel,
  openPosting,
  preserveMarkdownLineBreaks,
} from '../lib/normalize';
import { buildReportProblemUrl } from '../lib/reportLink';
import { CompanyMark } from './CompanyMark';
import {
  APPLICATION_STAGES,
  STAGE_LABELS,
  type ApplicationStage,
} from '../lib/savedJobs';
import {
  X,
  ExternalLink,
  Copy,
  Check,
  MapPin,
  Clock,
  ShieldCheck,
  Bookmark,
} from 'lucide-react';
import { Button } from './ui/button';
import { Steps, StepsItem, StepsTrigger, StepsContent } from './prompt-kit/steps';
import { Source, SourceTrigger, SourceContent } from './prompt-kit/source';

interface DetailSheetProps {
  job: NormalizedJob | null;
  onClose: () => void;
  onMarkVisited: (urlOrId: string) => void;
  isSaved?: boolean;
  savedStage?: ApplicationStage | null;
  onToggleSave?: (job: NormalizedJob) => void;
  onChangeStage?: (job: NormalizedJob, stage: ApplicationStage) => void;
  applicantCountry?: string;
  mode?: 'user' | 'admin';
}

const renderMarkdownHeading = ({ children }: { children?: React.ReactNode }) => (
  <h4 className="font-semibold text-xs text-[var(--ink)] mt-4 mb-1.5 first:mt-0">
    {children}
  </h4>
);

const markdownComponents: Components = {
  h1: renderMarkdownHeading,
  h2: renderMarkdownHeading,
  h3: renderMarkdownHeading,
  h4: renderMarkdownHeading,
  p: ({ children }) => (
    <p className="text-small text-[var(--ink-muted)] leading-relaxed mb-2.5 last:mb-0 [text-wrap:pretty]">
      {children}
    </p>
  ),
  ul: ({ children }) => (
    <ul className="list-disc pl-4 mb-3 space-y-1 text-small text-[var(--ink-muted)] leading-relaxed">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-4 mb-3 space-y-1 text-small text-[var(--ink-muted)] leading-relaxed">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li className="pl-0.5 text-[var(--ink-muted)] leading-relaxed">{children}</li>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-[var(--ink)]">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-[var(--ink-muted)]">{children}</em>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="underline text-[var(--ink)] hover:text-[var(--ink-muted)]"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-3 border-[var(--border-subtle)]" />,
};

export const DetailSheet: React.FC<DetailSheetProps> = ({
  job,
  onClose,
  onMarkVisited,
  isSaved = false,
  savedStage = null,
  onToggleSave,
  onChangeStage,
  applicantCountry = '',
  mode = 'user',
}) => {
  const [copied, setCopied] = useState(false);
  const sheetRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const isOpen = Boolean(job);

  useEffect(() => {
    if (!isOpen) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    sheetRef.current?.focus();
    return () => {
      const prev = previousFocusRef.current;
      previousFocusRef.current = null;
      if (prev && prev.isConnected) {
        prev.focus();
      }
    };
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && job) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [job, onClose]);

  if (!job) return null;

  const domain = extractDomain(job.apply_url || job.source_url);

  const handleOpenPosting = () => {
    const targetUrl = job.apply_url || job.source_url;
    if (targetUrl) {
      openPosting(targetUrl, onMarkVisited);
    }
  };

  const handleCopyLink = () => {
    const targetUrl = job.apply_url || job.source_url;
    if (targetUrl && navigator.clipboard) {
      navigator.clipboard.writeText(targetUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div
      className="detail-sheet-backdrop fixed inset-0 z-50 flex justify-end"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.45)' }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="detail-title"
    >
      <div
        ref={sheetRef}
        className="detail-sheet w-full max-w-[500px] h-full rounded-none overflow-y-auto p-6 sm:p-8 flex flex-col gap-6 bg-[var(--surface)] border-l border-[var(--border)] text-[var(--ink)] focus:outline-none"
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
      >
        {/* Header: Company Monogram/Logo + Title + Close */}
        <div className="flex items-start justify-between gap-4 border-b border-[var(--border-subtle)] pb-5">
          <div className="flex items-center gap-3 min-w-0">
            <CompanyMark company={job.company} logoUrl={job.company_logo_url} companyDomain={job.company_domain} size="lg" />
            <div className="min-w-0">
              <div className="text-body font-semibold text-[var(--ink)] truncate">
                {job.displayCompany}
              </div>
              {mode === 'admin' && (
                <div className="text-data text-[11px] text-[var(--ink-muted)] truncate">
                  via {job.provider} {domain && `· ${domain}`}
                </div>
              )}
            </div>
          </div>

          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close detail panel"
            className="shrink-0 max-md:size-11 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-transparent hover:border-[var(--border)]"
          >
            <X className="size-4" />
          </Button>
        </div>

        {/* Role Title */}
        <div className="flex flex-col gap-2">
          <h2 id="detail-title" className="text-title">
            {job.displayTitle}
          </h2>

          <div
            data-testid="detail-meta-header"
            className="flex flex-wrap items-center gap-2 pt-1 text-small text-[var(--ink-muted)]"
          >
            {(() => {
              const items: Array<{ key: string; node: React.ReactNode }> = [];
              if (job.displayLocation && job.displayLocation !== EMPTY_VALUE) {
                items.push({
                  key: 'location',
                  node: (
                    <span data-testid="detail-location" className="flex items-center gap-1">
                      <MapPin className="size-3.5 text-[var(--ink-subtle)]" aria-hidden="true" />
                      <span>{job.displayLocation}</span>
                    </span>
                  ),
                });
              }

              const workModelLabel =
                formatWorkModelLabel(job.work_model) ?? formatWorkModelLabel(job.displayWorkModel);
              items.push({
                key: 'work-model',
                node: workModelLabel ? (
                  <span className="font-medium text-[var(--ink)]">{workModelLabel}</span>
                ) : (
                  <span
                    data-testid="detail-work-model-not-stated"
                    className="text-[var(--ink-subtle)]"
                  >
                    Not stated
                  </span>
                ),
              });

              if (job.displaySalary && job.displaySalary !== EMPTY_VALUE) {
                items.push({
                  key: 'salary',
                  node: <span className="font-medium text-[var(--ink)]">{job.displaySalary}</span>,
                });
              }

              if (job.displayEmployment && job.displayEmployment !== EMPTY_VALUE) {
                items.push({
                  key: 'employment',
                  node: <span>{job.displayEmployment}</span>,
                });
              }

              if (job.ageBadgeLabel && job.ageBadgeLabel !== EMPTY_VALUE) {
                items.push({
                  key: 'age',
                  node: (
                    <span
                      data-testid="detail-age-badge"
                      className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-[11px] font-mono tabular-nums font-medium border border-[var(--border)] bg-[var(--surface-subtle)] text-[var(--ink-muted)]"
                    >
                      {job.ageBadgeLabel}
                    </span>
                  ),
                });
              }

              return items.map((item, idx) => (
                <React.Fragment key={item.key}>
                  {idx > 0 && (
                    <span className="text-[var(--border-strong)]" aria-hidden="true">
                      ·
                    </span>
                  )}
                  {item.node}
                </React.Fragment>
              ));
            })()}
          </div>
        </div>

        {/* Action Buttons: Apply, Save to Shortlist, & Copy */}
        <div className="flex flex-col gap-3 pt-1 pb-4 border-b border-[var(--border-subtle)]">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={handleOpenPosting}
              className="flex-1 min-w-[180px] h-10 max-md:h-11 rounded-lg font-medium text-small text-white transition-[opacity,transform] duration-140 ease-out motion-reduce:transform-none hover:opacity-95"
              style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
            >
              <span style={{ color: '#FFFFFF' }}>Open employer listing</span>
              <ExternalLink className="size-4 ml-2" style={{ color: '#FFFFFF' }} aria-hidden="true" />
            </Button>

            {onToggleSave && (
              <Button
                variant="outline"
                onClick={() => onToggleSave(job)}
                aria-pressed={isSaved}
                aria-label={isSaved ? 'Remove from shortlist' : 'Save to shortlist'}
                title={isSaved ? 'Remove from shortlist (s)' : 'Save to shortlist (s)'}
                className={`h-10 max-md:h-11 px-3 rounded-lg border ${
                  isSaved
                    ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                    : 'border-[var(--border)] hover:bg-[var(--surface-hover)] text-[var(--ink)]'
                }`}
              >
                <Bookmark
                  className={`size-4 mr-1.5 ${
                    isSaved ? 'fill-[var(--ink)] text-[var(--ink)]' : 'text-[var(--ink-muted)]'
                  }`}
                  aria-hidden="true"
                />
                <span>{isSaved ? 'Remove from shortlist' : 'Save to shortlist'}</span>
              </Button>
            )}

            <Button
              variant="outline"
              onClick={handleCopyLink}
              className="h-10 max-md:h-11 max-md:min-w-11 px-3 rounded-lg border-[var(--border)] hover:bg-[var(--surface-hover)] text-[var(--ink)]"
              title="Copy listing link"
              aria-label="Copy listing link"
            >
              {copied ? (
                <Check className="size-4 text-[var(--accent)]" />
              ) : (
                <Copy className="size-4 text-[var(--ink-muted)]" />
              )}
            </Button>
          </div>

          {isSaved && onChangeStage && (
            <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
              <span className="text-caption font-medium text-[var(--ink-muted)]">
                Application status
              </span>
              <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Application status">
                {APPLICATION_STAGES.map((stage) => {
                  const active = (savedStage || 'saved') === stage;
                  return (
                    <button
                      key={stage}
                      type="button"
                      onClick={() => onChangeStage(job, stage)}
                      aria-pressed={active}
                      className={`h-8 max-md:h-11 max-md:min-w-11 px-3 rounded-md text-xs border transition-[background-color,border-color,color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none cursor-pointer select-none ${
                        active
                          ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                          : 'border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
                      }`}
                    >
                      {STAGE_LABELS[stage]}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Description & Requirements (Markdown-rendered) */}
        <div className="flex flex-col gap-6 text-small text-[var(--ink)] leading-relaxed">
          {job.description && (
            <div className="flex flex-col gap-2">
              <h3 className="font-semibold text-small text-[var(--ink)]">
                Job overview
              </h3>
              <div className="markdown-preview text-[var(--ink-muted)]">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize]}
                  components={markdownComponents}
                >
                  {preserveMarkdownLineBreaks(job.description)}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {job.requirements && (
            <div className="flex flex-col gap-2">
              <h3 className="font-semibold text-small text-[var(--ink)]">
                Key requirements
              </h3>
              <div className="markdown-preview text-[var(--ink-muted)]">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize]}
                  components={markdownComponents}
                >
                  {preserveMarkdownLineBreaks(job.requirements)}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {!job.description && !job.requirements && (
            <div className="p-3.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-subtle)] text-small text-[var(--ink-muted)]">
              The full job details aren&apos;t available here. Open the employer listing to read the
              complete posting.
            </div>
          )}

          {(job.displayEligibility || applicantCountry) && (
            <section
              aria-label="Country eligibility"
              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-subtle)] p-3.5 flex flex-col gap-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold text-small text-[var(--ink)]">
                  Country eligibility
                </h3>
                {job.displayEligibility?.scopeLabel && (
                  <span className="text-caption font-mono text-[var(--ink-muted)]">
                    {job.displayEligibility.scopeLabel}
                  </span>
                )}
              </div>

              {job.displayEligibility?.statusLabel ? (
                <div className="flex flex-col gap-0.5">
                  <span
                    className={`text-small font-medium ${
                      job.displayEligibility.status === 'restricted'
                        ? 'text-[var(--danger-text)]'
                        : 'text-[var(--ink)]'
                    }`}
                  >
                    {job.displayEligibility.statusLabel}
                  </span>
                  {job.displayEligibility.reason && (
                    <span className="text-caption text-[var(--ink-muted)]">
                      {job.displayEligibility.reason}
                    </span>
                  )}
                </div>
              ) : (
                <div className="flex flex-col gap-0.5">
                  {job.displayEligibility?.reason && (
                    <p className="text-caption text-[var(--ink-muted)]">
                      {job.displayEligibility.reason}
                    </p>
                  )}
                  <p className="text-caption text-[var(--ink-subtle)]">
                    Select &ldquo;Where can you work from?&rdquo; to check eligibility for your country.
                  </p>
                </div>
              )}

              {job.displayEligibility && job.displayEligibility.items.length > 0 && (
                <dl className="grid grid-cols-[minmax(130px,auto)_1fr] max-md:grid-cols-1 gap-x-4 gap-y-1.5 max-md:gap-y-2.5 text-caption pt-1.5 border-t border-[var(--border-subtle)]">
                  {job.displayEligibility.items.map((item) => (
                    <div key={item.label} className="contents max-md:flex max-md:flex-col max-md:gap-0.5">
                      <dt className="text-[var(--ink-subtle)]">{item.label}</dt>
                      <dd className="text-[var(--ink)]">{item.value}</dd>
                    </div>
                  ))}
                </dl>
              )}

              {(job.displayEligibility?.evidenceExcerpt || job.displayEligibility?.evidenceUrl) && (
                <details className="pt-1.5 border-t border-[var(--border-subtle)] text-caption">
                  <summary className="cursor-pointer select-none max-md:min-h-11 max-md:flex max-md:items-center font-medium text-[var(--ink-muted)] hover:text-[var(--ink)]">
                    Why this label?
                  </summary>
                  <div className="mt-1.5 flex flex-col gap-1 text-[var(--ink-muted)]">
                    {job.displayEligibility.evidenceExcerpt && (
                      <blockquote className="border-l-2 border-[var(--border-strong)] pl-2.5 italic text-[var(--ink)]">
                        {job.displayEligibility.evidenceExcerpt}
                      </blockquote>
                    )}
                    {job.displayEligibility.evidenceUrl && (
                      <a
                        href={job.displayEligibility.evidenceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline text-[var(--ink-muted)] hover:text-[var(--ink)] truncate"
                      >
                        View source details
                      </a>
                    )}
                  </div>
                </details>
              )}
            </section>
          )}

          {/* Verification & Provenance Trace (Prompt Kit Steps) (Admin only) */}
          {mode === 'admin' && (
            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-subtle)] p-3 space-y-2">
              <Steps defaultOpen={true}>
                <StepsTrigger leftIcon={<ShieldCheck className="size-3.5 text-[var(--accent)]" />}>
                  <span className="font-semibold text-xs text-[var(--ink)]">5-Stage Verification Pipeline</span>
                </StepsTrigger>
                <StepsContent>
                  <StepsItem>
                    <span className="font-semibold text-[var(--ink)]">1. Discovery:</span> Indexed directly from employer career portal on{' '}
                    <span className="font-mono text-[11px] text-[var(--ink)]">{job.provider}</span>.
                  </StepsItem>
                  <StepsItem>
                    <span className="font-semibold text-[var(--ink)]">2. Fetch:</span> Requisition fetched from{' '}
                    <Source href={job.apply_url || job.source_url}>
                      <SourceTrigger label={extractDomain(job.apply_url || job.source_url)} showFavicon={true} />
                      <SourceContent
                        title={job.displayTitle}
                        description={`Direct job requisition hosted by ${job.displayCompany}. Verified direct to employer.`}
                        evidenceSnippet={job.work_model_evidence || undefined}
                      />
                    </Source>
                  </StepsItem>
                  <StepsItem>
                    <span className="font-semibold text-[var(--ink)]">3. Extraction:</span> {job.work_model_source ? `Derived from ${job.work_model_source}` : 'Structured JSON-LD schema (ADR 0002)'}
                    {job.raw_location && job.raw_location !== job.location && (
                      <span className="block mt-1 text-caption text-[var(--ink-muted)]">
                        Raw location: <span className="text-data text-[11px]">{job.raw_location}</span>
                      </span>
                    )}
                  </StepsItem>
                  <StepsItem>
                    <span className="font-semibold text-[var(--ink)]">4. Remote Policy:</span>{' '}
                    {job.work_model_evidence ? (
                      <span className="font-mono text-[11px] italic text-[var(--ink)]">"{job.work_model_evidence}"</span>
                    ) : (
                      <span>Policy specified by employer requisition.</span>
                    )}
                  </StepsItem>
                  <StepsItem>
                    <span className="font-semibold text-[var(--ink)]">5. Normalization:</span>{' '}
                    {job.displaySalary && job.displaySalary !== '—' ? (
                      <span>Compensation normalized to <strong className="font-mono text-[11px] text-[var(--ink)]">{job.displaySalary}</strong> (ADR 0003).</span>
                    ) : (
                      <span>No salary range published in posting. Missing field preserved as null (ADR 0001).</span>
                    )}
                  </StepsItem>
                </StepsContent>
              </Steps>
            </div>
          )}
        </div>

        {/* Timestamp & Report Link Footer */}
        <div className="mt-auto pt-6 border-t border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-2 text-caption text-[var(--ink-subtle)]">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="flex items-center gap-1">
              <Clock className="size-3" aria-hidden="true" />
              <span>Posted {job.postingDateFull || job.displayPostedDate}</span>
            </span>
            {job.last_verified_at && !Number.isNaN(Date.parse(job.last_verified_at)) && (
              <span>
                Last checked {new Date(job.last_verified_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {(() => {
              const reportHref = buildReportProblemUrl(job);
              const isHttpsReport = reportHref?.startsWith('https://');
              return reportHref ? (
                <a
                  href={reportHref}
                  {...(isHttpsReport ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                  data-testid="report-problem-link"
                  className="py-1 max-md:min-h-11 max-md:inline-flex max-md:items-center text-xs underline underline-offset-2 text-[var(--ink-muted)] hover:text-[var(--ink)] transition-colors"
                >
                  Report a problem with this listing
                </a>
              ) : null;
            })()}
            {mode === 'admin' && (
              <span className="text-data text-[11px] uppercase">
                {job.data_source}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
