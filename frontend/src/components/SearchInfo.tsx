import React, { useState } from 'react';
import type { DoneMetrics } from '../types';

interface SearchInfoProps {
  metrics: DoneMetrics | null;
  totalRawResults: number;
}

export const SearchInfo: React.FC<SearchInfoProps> = ({
  metrics,
  totalRawResults,
}) => {
  const [expanded, setExpanded] = useState(false);

  if (!metrics) return null;

  const serperCalls = metrics.serper_calls ?? metrics.serper_queries_used ?? 0;
  const cacheHits = metrics.serper_cache_hits ?? 0;
  const timeSec = (metrics.search_time_ms / 1000).toFixed(1);

  return (
    <div id="metrics" className="search-info-container">
      <button
        type="button"
        id="searchInfoToggle"
        className="search-info-line"
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
      >
        <span>
          SEARCH INFO · {serperCalls} SERPER CALLS · {cacheHits} CACHED · {timeSec}S
        </span>
        <span className="search-info-chevron" aria-hidden="true">
          {expanded ? '▾' : '▸'}
        </span>
      </button>

      {expanded && (
        <div id="searchInfoDetails" className="search-info-expanded">
          <div className="search-info-grid">
            <div>
              <span className="label">Providers searched:</span>{' '}
              <span className="mono">{metrics.providers_searched.join(', ') || 'None'}</span>
            </div>
            {metrics.providers_skipped && metrics.providers_skipped.length > 0 && (
              <div>
                <span className="label">Skipped:</span>{' '}
                <span className="mono">{metrics.providers_skipped.join(', ')}</span>
              </div>
            )}
            {metrics.pages_fetched !== undefined && (
              <div>
                <span className="label">Pages fetched:</span>{' '}
                <span className="mono">{metrics.pages_fetched}</span>
              </div>
            )}
            {metrics.dropped_count && Object.keys(metrics.dropped_count).length > 0 && (
              <div>
                <span className="label">Dropped items:</span>{' '}
                <span className="mono">
                  {Object.entries(metrics.dropped_count)
                    .map(([k, v]) => `${k} (${v})`)
                    .join(', ')}
                </span>
              </div>
            )}
            <div>
              <span className="label">Total results:</span>{' '}
              <span className="mono">{metrics.total ?? totalRawResults}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
