import React from 'react';
import { AlertCircle } from 'lucide-react';
import type { DoneMetrics } from '../types';
import { formatRelativeTime } from '../lib/normalize';

interface StatusBannerProps {
  savedTimestamp: number | null;
  metrics: DoneMetrics | null;
  onRunAgain: () => void;
  onClearSaved: () => void;
}

export const StatusBanner: React.FC<StatusBannerProps> = ({
  savedTimestamp,
  metrics,
  onRunAgain,
  onClearSaved,
}) => {
  return (
    <>
      {savedTimestamp && (
        <div className="saved-results-banner" role="status">
          <span className="banner-text">
            Showing saved results from {formatRelativeTime(savedTimestamp)} &mdash;{' '}
            <button
              type="button"
              className="banner-link-btn"
              onClick={onRunAgain}
            >
              Run search again
            </button>
          </span>
          <button
            type="button"
            className="banner-action-btn"
            onClick={onClearSaved}
          >
            Clear saved results
          </button>
        </div>
      )}

      {(metrics?.budget_exhausted || metrics?.message) && (
        <div className="budget-banner" role="alert">
          <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" strokeWidth={1.5} />
          <span>
            {metrics?.message ||
              'Serper daily budget limit reached. Showing available and cached results.'}
          </span>
        </div>
      )}
    </>
  );
};
