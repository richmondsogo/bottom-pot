import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { Copy, Check, Clock } from 'lucide-react';
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
      modelClass,
      tooltip,
      copiedId,
      onCopyApplyUrl,
    },
    ref
  ) => {
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
              <span className={`badge-model ${modelClass}`} title={tooltip}>
                {job.displayLocationType}
              </span>
              {job.scraped_at && (
                <span className="detail-freshness">
                  <Clock className="w-3 h-3 inline mr-1" />
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
              className="primary-button detail-apply-btn"
            >
              <span>Apply</span>
              <span aria-hidden="true">&#8599;</span>
            </a>
            <button
              type="button"
              className="copy-btn"
              onClick={() => onCopyApplyUrl(job.apply_url, job.id)}
            >
              {copiedId === job.id ? (
                <>
                  <Check className="w-3.5 h-3.5 inline mr-1" /> Link Copied
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 inline mr-1" /> Copy Link
                </>
              )}
            </button>
            <a
              href={job.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-button"
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
                className={
                  job.displaySalary !== 'Not listed' ? 'salary-listed' : ''
                }
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
              <strong>{job.displayPostedDate}</strong>
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
                <span className={`badge-model ${modelClass}`}>
                  {job.displayLocationType}
                </span>
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
