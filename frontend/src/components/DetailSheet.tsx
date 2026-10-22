import React, { useState, useEffect, useRef } from 'react';
import type { NormalizedJob } from '../types';
import { getCompanyInitials, getCompanyTileColor } from '../lib/storage';
import { extractDomain } from '../lib/normalize';
import { X, ExternalLink, Copy, Check, MapPin, Clock, ShieldCheck } from 'lucide-react';
import { Button } from './ui/button';

interface DetailSheetProps {
  job: NormalizedJob | null;
  onClose: () => void;
  onMarkVisited: (urlOrId: string) => void;
}

export const DetailSheet: React.FC<DetailSheetProps> = ({
  job,
  onClose,
  onMarkVisited,
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

        {/* Action Buttons: Apply & Copy */}
        <div className="flex items-center gap-2 pt-1 pb-4 border-b border-[var(--border-subtle)]">
          <Button
            onClick={handleOpenPosting}
            className="flex-1 h-10 font-medium text-small text-white transition-opacity hover:opacity-95"
            style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
          >
            <span style={{ color: '#FFFFFF' }}>Open application</span>
            <ExternalLink className="size-4 ml-2" style={{ color: '#FFFFFF' }} aria-hidden="true" />
          </Button>

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

        {/* Description & Requirements */}
        <div className="flex flex-col gap-6 text-small text-[var(--ink)] leading-relaxed">
          {job.description && (
            <div className="flex flex-col gap-2">
              <h3 className="font-semibold text-small text-[var(--ink)]">
                Overview
              </h3>
              <p className="text-[var(--ink-muted)] whitespace-pre-line text-wrap:pretty">
                {job.description}
              </p>
            </div>
          )}

          {job.requirements && (
            <div className="flex flex-col gap-2">
              <h3 className="font-semibold text-small text-[var(--ink)]">
                Key Requirements
              </h3>
              <p className="text-[var(--ink-muted)] whitespace-pre-line text-wrap:pretty">
                {job.requirements}
              </p>
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
