import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { Copy, Check } from 'lucide-react';
import type { NormalizedJob } from '../types';
import { formatFreshness } from '../lib/normalize';

interface DetailsPanelProps {
  job: NormalizedJob;
  visibleWrapWidth: number;
  modelClass: string;
  tooltip?: string;
  copiedId: string | null;
  onCopyApplyUrl: (url: string, id: string) => void;
}

export const DetailsPanel = React.forwardRef<HTMLDivElement, DetailsPanelProps>(
  (
    {
      job,
      visibleWrapWidth,
      tooltip,
      copiedId,
      onCopyApplyUrl,
    },
    ref
  ) => {
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

    return (
      <article
        ref={ref}
        className="job-detail-panel"
        aria-label={`${job.displayTitle} details`}
        style={{
          width: visibleWrapWidth ? `${visibleWrapWidth}px` : '100%',
        }}
      >
        <header className="detail-panel-header">
          <div className="detail-panel-title-area">
            <h3 className="detail-panel-title">{job.displayTitle}</h3>
            <div className="detail-panel-sub">
              <span className="detail-panel-company">{job.company}</span>
              {job.displayLocation && (
                <>
                  <span className="detail-panel-sep">·</span>
                  <span>{job.displayLocation}</span>
                </>
              )}
              {hasWorkModel ? (
                <span className={`badge ${modelBadgeClass}`} title={tooltip}>
                  {modelBadgeText}
                </span>
              ) : (
                <span className="cell-muted" title="Not specified in the posting">
                  —
                </span>
              )}
              {job.scraped_at && (
                <span className="detail-freshness mono">
                  {formatFreshness(job.scraped_at)}
                </span>
              )}
            </div>
          </div>
          <div className="detail-panel-actions">
            <a
              href={job.apply_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary detail-apply-btn"
            >
              Apply -&gt;
            </a>
            <button
              type="button"
              className="btn btn-secondary copy-btn"
              onClick={() => onCopyApplyUrl(job.apply_url, job.id)}
              aria-label="Copy application link"
            >
              {copiedId === job.id ? (
                <>
                  <Check className="w-3.5 h-3.5" strokeWidth={1.5} />
                  <span>Link Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" strokeWidth={1.5} />
                  <span>Copy Link</span>
                </>
              )}
            </button>
            <a
              href={job.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-text"
            >
              Open source posting ↗
            </a>
          </div>
        </header>

        <div className="detail-panel-body">
          <div className="detail-panel-main">
            <section className="detail-section">
              <h4>Job Description</h4>
              <div className="markdown-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize]}
                >
                  {job.description ||
                    job.summary ||
                    'No description was returned for this posting.'}
                </ReactMarkdown>
              </div>
            </section>
            {job.requirements && (
              <section className="detail-section">
                <h4>Requirements</h4>
                <div className="markdown-content">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeSanitize]}
                  >
                    {job.requirements}
                  </ReactMarkdown>
                </div>
              </section>
            )}
          </div>

          <aside className="detail-panel-aside">
            <div className="aside-group">
              <span className="aside-label">Salary</span>
              <strong
                className={`cell-tabular ${
                  job.displaySalary !== 'Not listed' ? 'salary-listed' : ''
                }`}
              >
                {job.displaySalary}
              </strong>
            </div>
            <div className="aside-group">
              <span className="aside-label">Job type</span>
              <strong>{job.displayEmployment}</strong>
            </div>
            <div className="aside-group">
              <span className="aside-label">Posted date</span>
              <strong className="cell-tabular">{job.displayPostedDate}</strong>
            </div>
            <div className="aside-group">
              <span className="aside-label">Provider / Data source</span>
              <strong>
                {job.provider}
                {job.data_source ? ` - ${job.data_source}` : ''}
              </strong>
            </div>
            <div className="aside-group">
              <span className="aside-label">Work model</span>
              <div className="aside-work-model">
                {hasWorkModel ? (
                  <span className={`badge ${modelBadgeClass}`}>
                    {modelBadgeText}
                  </span>
                ) : (
                  <span className="cell-muted" title="Not specified in the posting">
                    —
                  </span>
                )}
                {job.work_model_source && (
                  <div className="aside-evidence">
                    <span className="evidence-source">
                      Source: {job.work_model_source}
                    </span>
                    {job.work_model_evidence && (
                      <span className="evidence-snippet">
                        &quot;{job.work_model_evidence}&quot;
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </aside>
        </div>
      </article>
    );
  }
);

DetailsPanel.displayName = 'DetailsPanel';
