import React from 'react';
import type { DoneMetrics } from '../types';

interface SearchInfoProps {
  metrics: DoneMetrics | null;
  totalRawResults: number;
}

export const SearchInfo: React.FC<SearchInfoProps> = ({
  metrics,
  totalRawResults,
}) => {
  return (
    <>
      <div id="metrics" className="metrics">
        <div className="metric">
          <strong>{metrics?.total ?? totalRawResults}</strong>
          <span>Results</span>
        </div>
        <div className="metric">
          <strong>{metrics ? `${metrics.search_time_ms} ms` : '-'}</strong>
          <span>Search time</span>
        </div>
        <div className="metric">
          <strong>{metrics?.providers_searched.length ?? 0}</strong>
          <span>Providers</span>
        </div>
        <div className="metric">
          <strong>{metrics?.serper_queries_used ?? metrics?.serper_calls ?? 0}</strong>
          <span>Serper queries</span>
        </div>
      </div>

      {metrics && (
        <details className="search-info-disclosure">
          <summary className="search-info-summary">
            <span>Search info &amp; telemetry</span>
            <span className="search-info-pills">
              <span>{metrics.serper_calls ?? metrics.serper_queries_used ?? 0} Serper calls</span>
              <span>{metrics.serper_cache_hits ?? 0} cache hits</span>
              <span>{metrics.pages_fetched ?? 0} pages fetched</span>
              <span>{metrics.search_time_ms} ms</span>
            </span>
          </summary>
          <div className="search-info-content">
            <div className="search-info-grid">
              <div>
                <strong>Searched:</strong> {metrics.providers_searched.join(', ') || 'None'}
              </div>
              {metrics.providers_skipped && metrics.providers_skipped.length > 0 && (
                <div>
                  <strong>Skipped:</strong> {metrics.providers_skipped.join(', ')}
                </div>
              )}
              {metrics.dropped_count && Object.keys(metrics.dropped_count).length > 0 && (
                <div>
                  <strong>Dropped items:</strong>{' '}
                  {Object.entries(metrics.dropped_count)
                    .map(([k, v]) => `${k} (${v})`)
                    .join(', ')}
                </div>
              )}
            </div>
          </div>
        </details>
      )}
    </>
  );
};
