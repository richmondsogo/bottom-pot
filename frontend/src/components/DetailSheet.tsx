import React, { useState, useEffect, useRef } from 'react';
import type { NormalizedJob } from '../types';
import { getCompanyInitials, getCompanyTileColor } from '../lib/storage';
import { extractDomain } from '../lib/normalize';
import { X, ExternalLink, Copy, Check, MapPin, Clock, Building2 } from 'lucide-react';

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
    // Focus the sheet when opened
    if (job) {
      sheetRef.current?.focus();
    }
  }, [job]);

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
      className="detail-sheet-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="detail-title"
    >
      <div
        ref={sheetRef}
        className="detail-sheet"
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
      >
        {/* Header with Close button */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <div
              className="company-tile"
              style={{
                backgroundColor: tileColor.bg,
                color: tileColor.color,
                borderColor: tileColor.border,
                width: '36px',
                height: '36px',
                fontSize: '13px',
              }}
              aria-hidden="true"
            >
              {initials}
            </div>
            <div>
              <div style={{ fontSize: 'var(--text-body)', fontWeight: 700, color: 'var(--ink)' }}>
                {job.company || 'Unknown Company'}
              </div>
              <div className="mono" style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-muted)' }}>
                via {job.provider} · {domain}
              </div>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-sm"
            onClick={onClose}
            aria-label="Close detail panel"
            style={{ width: '32px', height: '32px', padding: 0 }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Title */}
        <h2
          id="detail-title"
          style={{
            fontSize: 'var(--text-h2)',
            fontWeight: 800,
            letterSpacing: '-0.02em',
            lineHeight: 1.25,
            marginBottom: 'var(--space-4)',
          }}
        >
          {job.title}
        </h2>

        {/* Metadata Strip */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-2)',
            padding: 'var(--space-4)',
            background: 'var(--surface-subtle)',
            border: '1px solid var(--border)',
            marginBottom: 'var(--space-5)',
            fontSize: 'var(--text-sm)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <MapPin size={14} style={{ color: 'var(--ink-muted)', flexShrink: 0 }} aria-hidden="true" />
            <span style={{ color: 'var(--ink)' }}>
              <strong>Location:</strong> {job.displayLocation === '—' ? 'Not specified' : job.displayLocation}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Building2 size={14} style={{ color: 'var(--ink-muted)', flexShrink: 0 }} aria-hidden="true" />
            <span style={{ color: 'var(--ink)' }}>
              <strong>Work Model:</strong>{' '}
              {job.work_model ? job.work_model.replace('_', ' ') : 'Not specified'}
            </span>
          </div>

          {job.displaySalary !== '—' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <span className="mono" style={{ fontWeight: 700, color: 'var(--accent)', flexShrink: 0 }}>
                $$
              </span>
              <span style={{ color: 'var(--ink)' }}>
                <strong>Compensation:</strong> {job.displaySalary}
              </span>
            </div>
          )}

          {job.posted_at && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <Clock size={14} style={{ color: 'var(--ink-muted)', flexShrink: 0 }} aria-hidden="true" />
              <span style={{ color: 'var(--ink)' }}>
                <strong>Posted:</strong> {job.displayPostedDate}
              </span>
            </div>
          )}
        </div>

        {/* Action Buttons Row */}
        <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleOpenPosting}
            style={{ flex: 1, height: '42px' }}
          >
            <span>Open posting</span>
            <ExternalLink size={14} aria-hidden="true" />
          </button>

          <button
            type="button"
            className="btn"
            onClick={handleCopyLink}
            style={{ height: '42px', padding: '0 16px' }}
            title="Copy posting URL to clipboard"
          >
            {copied ? <Check size={14} style={{ color: 'var(--accent)' }} /> : <Copy size={14} />}
            <span>{copied ? 'Copied' : 'Copy link'}</span>
          </button>
        </div>

        {/* Job Snippet / Description */}
        <div style={{ flex: 1 }}>
          <div
            className="mono"
            style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              textTransform: 'uppercase',
              color: 'var(--ink-muted)',
              marginBottom: 'var(--space-2)',
              letterSpacing: '0.08em',
            }}
          >
            Posting Details & Requirements
          </div>

          <div
            style={{
              fontSize: 'var(--text-ui)',
              lineHeight: 1.65,
              color: 'var(--ink)',
              whiteSpace: 'pre-line',
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              padding: 'var(--space-4)',
            }}
          >
            {job.description && <div>{job.description}</div>}
            {job.requirements && (
              <div style={{ marginTop: job.description ? 'var(--space-3)' : 0, paddingTop: job.description ? 'var(--space-3)' : 0, borderTop: job.description ? '1px dashed var(--border)' : 'none' }}>
                <strong style={{ display: 'block', marginBottom: 'var(--space-1)' }}>Requirements:</strong>
                <div>{job.requirements}</div>
              </div>
            )}
            {!job.description && !job.requirements && (
              <span style={{ color: 'var(--ink-subtle)', fontStyle: 'italic' }}>
                Full posting description is hosted directly on {job.provider}. Click &ldquo;Open posting&rdquo; above to read complete role requirements and apply.
              </span>
            )}
          </div>
        </div>

        {/* Footer info */}
        <div
          className="mono"
          style={{
            fontSize: '11px',
            color: 'var(--ink-subtle)',
            marginTop: 'var(--space-6)',
            paddingTop: 'var(--space-3)',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          Direct link: {job.apply_url || job.source_url}
        </div>
      </div>
    </div>
  );
};
