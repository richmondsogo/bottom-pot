import React, { useState } from 'react';
import type { DoneMetrics } from '../types';
import { ChevronDown, ChevronUp, RefreshCw, Trash2 } from 'lucide-react';

function formatSavedAgo(savedTimestamp: number | null): string {
  if (!savedTimestamp) return '';
  const now = Date.now();
  const elapsedMinutes = Math.floor((now - savedTimestamp) / (1000 * 60));
  if (elapsedMinutes < 60) return `Saved ${Math.max(1, elapsedMinutes)}m ago`;
  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) return `Saved ${elapsedHours}h ago`;
  const elapsedDays = Math.floor(elapsedHours / 24);
  return `Saved ${elapsedDays}d ago`;
}

interface StatusStripProps {
  totalResults: number;
  metrics: DoneMetrics | null;
  savedTimestamp: number | null;
  onRunAgain: () => void;
  onClearSaved: () => void;
}

export const StatusStrip: React.FC<StatusStripProps> = ({
  totalResults,
  metrics,
  savedTimestamp,
  onRunAgain,
  onClearSaved,
}) => {
  const [detailsOpen, setDetailsOpen] = useState(false);

  // Formatting duration
  const durationSec = metrics ? (metrics.search_time_ms / 1000).toFixed(1) + 's' : null;
  const platformCount = metrics?.providers_searched?.length || 18;
  const savedAgo = formatSavedAgo(savedTimestamp);

  return (
    <div style={{ marginBottom: 'var(--space-4)' }}>
      <div className="status-strip">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, color: 'var(--ink)' }}>
            {totalResults} {totalResults === 1 ? 'posting' : 'postings'} from {platformCount} platforms
          </span>

          {durationSec && <span>· {durationSec}</span>}
          {savedAgo && <span style={{ color: 'var(--ink-subtle)' }}>· {savedAgo}</span>}

          <button
            type="button"
            className="btn-text"
            onClick={() => setDetailsOpen(!detailsOpen)}
            style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '2px', textDecoration: 'none' }}
            aria-expanded={detailsOpen}
          >
            <span>Search details</span>
            {detailsOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <button
            type="button"
            className="btn btn-sm"
            onClick={onRunAgain}
            style={{ height: '28px', fontSize: '11px' }}
          >
            <RefreshCw size={11} aria-hidden="true" />
            <span>Run again</span>
          </button>

          {savedTimestamp && (
            <button
              type="button"
              className="btn btn-sm"
              onClick={onClearSaved}
              style={{ height: '28px', fontSize: '11px' }}
            >
              <Trash2 size={11} aria-hidden="true" />
              <span>Clear saved</span>
            </button>
          )}
        </div>
      </div>

      {/* Collapsible search details disclosure (Plain language, zero developer jargon) */}
      {detailsOpen && metrics && (
        <div
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderTop: 'none',
            padding: 'var(--space-4)',
            marginTop: 'calc(-1 * var(--space-4))',
            marginBottom: 'var(--space-4)',
            fontSize: 'var(--text-xs)',
            color: 'var(--ink-muted)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--space-3)' }}>
            <div>
              <span style={{ display: 'block', color: 'var(--ink-subtle)' }}>SEARCH SOURCE</span>
              <span style={{ fontWeight: 600, color: 'var(--ink)' }}>
                {metrics.cached ? 'Loaded from local cache' : 'Live queries completed'}
              </span>
            </div>

            <div>
              <span style={{ display: 'block', color: 'var(--ink-subtle)' }}>PAGES INSPECTED</span>
              <span style={{ fontWeight: 600, color: 'var(--ink)' }}>
                {metrics.pages_fetched ?? metrics.total} job postings
              </span>
            </div>

            <div>
              <span style={{ display: 'block', color: 'var(--ink-subtle)' }}>EXECUTION DURATION</span>
              <span style={{ fontWeight: 600, color: 'var(--ink)' }}>
                {(metrics.search_time_ms / 1000).toFixed(2)} seconds
              </span>
            </div>

            <div>
              <span style={{ display: 'block', color: 'var(--ink-subtle)' }}>PLATFORMS REACHED</span>
              <span style={{ fontWeight: 600, color: 'var(--ink)' }}>
                {metrics.providers_searched?.join(', ') || 'All standard ATS'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
