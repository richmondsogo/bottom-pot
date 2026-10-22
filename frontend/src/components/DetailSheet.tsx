import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import type { NormalizedJob } from '../types';
import { getCompanyInitials, getCompanyTileColor } from '../lib/storage';
import { extractDomain } from '../lib/normalize';
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

interface DetailSheetProps {
  job: NormalizedJob | null;
  onClose: () => void;
  onMarkVisited: (urlOrId: string) => void;
  isSaved?: boolean;
  savedStage?: ApplicationStage | null;
  onToggleSave?: (job: NormalizedJob) => void;
  onChangeStage?: (job: NormalizedJob, stage: ApplicationStage) => void;
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
}) => {
  const [copied, setCopied] = useState(false);
  const sheetRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (job) {
      sheetRef.current?.focus();
    }
  }, [job]);

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

  const initials = getCompanyInitials(job.company);
  const tileColor = getCompanyTileColor(job.company);
  const domain = extractDomain(job.apply_url || job.source_url);

  const handleOpenPosting = () => {
    const targetUrl = job.apply_url || job.source_url;
    if (targetUrl) {
      onMarkVisited(targetUrl);
      window.open(targetUrl, '_blank', 'noopener,noreferrer');
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
        className="detail-sheet w-full max-w-[500px] h-full overflow-y-auto p-6 sm:p-8 flex flex-col gap-6 bg-[var(--surface)] border-l border-[var(--border)] text-[var(--ink)] focus:outline-none"
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
      >
        {/* Header: Company Monogram + Title + Close */}
        <div className="flex items-start justify-between gap-4 border-b border-[var(--border-subtle)] pb-5">
          <div className="flex items-center gap-3">
            <div
              className="size-9 flex items-center justify-center font-bold text-xs shrink-0 border"
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
              <div className="text-body font-semibold text-[var(--ink)]">
                {job.displayCompany}
              </div>
              <div className="text-data text-[11px] text-[var(--ink-muted)]">
                via {job.provider} {domain && `· ${domain}`}
              </div>
            </div>
          </div>

          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close detail panel"
            className="text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-transparent hover:border-[var(--border)]"
          >
            <X className="size-4" />
          </Button>
        </div>

        {/* Role Title */}
        <div className="flex flex-col gap-2">
          <h2 id="detail-title" className="text-title">
            {job.displayTitle}
          </h2>

          <div className="flex flex-wrap items-center gap-2 pt-1 text-small text-[var(--ink-muted)]">
            <span className="flex items-center gap-1">
              <MapPin className="size-3.5 text-[var(--ink-subtle)]" aria-hidden="true" />
              <span>{job.displayLocation}</span>
            </span>

            {job.displayWorkModel && (
              <>
                <span className="text-[var(--border-strong)]">·</span>
                <span className="font-medium text-[var(--ink)]">{job.displayWorkModel}</span>
              </>
            )}

            {job.displaySalary && job.displaySalary !== '—' && (
              <>
                <span className="text-[var(--border-strong)]">·</span>
                <span className="font-medium text-[var(--ink)]">{job.displaySalary}</span>
              </>
            )}

            {job.displayEmployment && job.displayEmployment !== '—' && (
              <>
                <span className="text-[var(--border-strong)]">·</span>
                <span>{job.displayEmployment}</span>
              </>
            )}
          </div>
        </div>

        {/* Action Buttons: Apply, Save to Shortlist, & Copy */}
        <div className="flex flex-col gap-3 pt-1 pb-4 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-2">
            <Button
              onClick={handleOpenPosting}
              className="flex-1 h-10 font-medium text-small text-white transition-opacity hover:opacity-95"
              style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
            >
              <span style={{ color: '#FFFFFF' }}>Open application</span>
              <ExternalLink className="size-4 ml-2" style={{ color: '#FFFFFF' }} aria-hidden="true" />
            </Button>

            {onToggleSave && (
              <Button
                variant="outline"
                onClick={() => onToggleSave(job)}
                aria-pressed={isSaved}
                aria-label={isSaved ? 'Remove from saved jobs' : 'Save job to shortlist'}
                title={isSaved ? 'Remove from saved shortlist (s)' : 'Save to shortlist (s)'}
                className={`h-10 px-3 border transition-colors ${
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
                <span>{isSaved ? 'Saved' : 'Save'}</span>
              </Button>
            )}

            <Button
              variant="outline"
              onClick={handleCopyLink}
              className="h-10 px-3 border-[var(--border)] hover:bg-[var(--surface-hover)] text-[var(--ink)]"
              title="Copy job link"
              aria-label="Copy job link"
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
                Pipeline stage:
              </span>
              <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Application pipeline stage">
                {APPLICATION_STAGES.map((stage) => {
                  const active = (savedStage || 'saved') === stage;
                  return (
                    <button
                      key={stage}
                      type="button"
                      onClick={() => onChangeStage(job, stage)}
                      aria-pressed={active}
                      className={`h-8 px-3 text-xs border transition-colors cursor-pointer select-none ${
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
                Overview
              </h3>
              <div className="markdown-preview text-[var(--ink-muted)]">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize]}
                  components={markdownComponents}
                >
                  {job.description}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {job.requirements && (
            <div className="flex flex-col gap-2">
              <h3 className="font-semibold text-small text-[var(--ink)]">
                Key Requirements
              </h3>
              <div className="markdown-preview text-[var(--ink-muted)]">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize]}
                  components={markdownComponents}
                >
                  {job.requirements}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {!job.description && !job.requirements && (
            <div className="p-3.5 border border-[var(--border-subtle)] bg-[var(--surface-subtle)] text-small text-[var(--ink-muted)]">
              Full job description is hosted directly on the employer's application page. Use{' '}
              <strong className="font-semibold text-[var(--ink)]">Open application</strong> above to
              view the complete posting.
            </div>
          )}

          {job.work_model_evidence && (
            <div className="flex flex-col gap-1.5 p-3 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]">
              <div className="flex items-center gap-1.5 text-caption font-semibold text-[var(--ink)]">
                <ShieldCheck className="size-3.5 text-[var(--accent)]" />
                <span>Work Model Verification</span>
              </div>
              <p className="text-caption text-[var(--ink-muted)] font-mono text-[11px]">
                "{job.work_model_evidence}"
              </p>
            </div>
          )}
        </div>

        {/* Timestamp Footer */}
        <div className="mt-auto pt-6 border-t border-[var(--border-subtle)] flex items-center justify-between text-caption text-[var(--ink-subtle)]">
          <span className="flex items-center gap-1">
            <Clock className="size-3" aria-hidden="true" />
            <span>Posted: {job.postingDateFull || job.displayPostedDate}</span>
          </span>
          <span className="text-data text-[11px] uppercase">
            {job.data_source}
          </span>
        </div>
      </div>
    </div>
  );
};
