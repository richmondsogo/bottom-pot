import React, { useState, useEffect } from 'react';
import { AlertCircle, AlertTriangle, RefreshCw, Filter, Calendar } from 'lucide-react';

interface LoadingStateProps {
  onCancel: () => void;
  statusMessage?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({ onCancel, statusMessage }) => {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div style={{ maxWidth: '1080px', margin: '0 auto', width: '100%' }}>
      {/* Editorial Status Line with Honest Timer */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: 'var(--space-4)',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          marginBottom: 'var(--space-4)',
        }}
      >
        <div>
          <div style={{ fontWeight: 700, fontSize: 'var(--text-body)', color: 'var(--ink)' }}>
            Searching ATS platforms directly
          </div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-muted)', marginTop: '2px' }}>
            {statusMessage || 'Querying Google indexes for public ATS company boards. This can take 20–30 seconds.'}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <span className="mono tabular" style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--accent)' }}>
            {seconds}s elapsed
          </span>
          <button type="button" className="btn btn-sm" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>

      {/* Honest skeleton table matching real column layout */}
      <div className="table-container">
        <table className="results-table" aria-label="Loading job listings">
          <thead>
            <tr>
              <th scope="col" style={{ width: '38%' }}>Role</th>
              <th scope="col" style={{ width: '22%' }}>Company</th>
              <th scope="col" style={{ width: '16%' }}>Location</th>
              <th scope="col" style={{ width: '12%' }}>Salary</th>
              <th scope="col" style={{ width: '12%' }}>Work model</th>
            </tr>
          </thead>
          <tbody>
            {[...Array(6)].map((_, i) => (
              <tr key={i} style={{ cursor: 'default' }}>
                <td>
                  <div className="skeleton-box" style={{ width: `${60 + (i % 3) * 15}%` }} />
                </td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <div className="skeleton-box" style={{ width: '28px', height: '28px', flexShrink: 0 }} />
                    <div className="skeleton-box" style={{ width: '70%' }} />
                  </div>
                </td>
                <td>
                  <div className="skeleton-box" style={{ width: '50%' }} />
                </td>
                <td>
                  <div className="skeleton-box" style={{ width: '40%' }} />
                </td>
                <td>
                  <div className="skeleton-box" style={{ width: '60px' }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

interface NoResultsStateProps {
  onWidenDateRange: () => void;
  onClearFilters: () => void;
  onNewSearch: () => void;
}

export const NoResultsState: React.FC<NoResultsStateProps> = ({
  onWidenDateRange,
  onClearFilters,
  onNewSearch,
}) => {
  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        padding: 'var(--space-8) var(--space-6)',
        textAlign: 'center',
        maxWidth: '640px',
        margin: 'var(--space-8) auto',
      }}
    >
      <div
        style={{
          width: '40px',
          height: '40px',
          background: 'var(--surface-subtle)',
          border: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto var(--space-4)',
          color: 'var(--ink-muted)',
        }}
      >
        <Filter size={20} aria-hidden="true" />
      </div>

      <h3 style={{ fontSize: 'var(--text-h2)', fontWeight: 700, marginBottom: 'var(--space-2)' }}>
        No job postings matched your criteria
      </h3>

      <p style={{ color: 'var(--ink-muted)', fontSize: 'var(--text-body)', lineHeight: 1.6, marginBottom: 'var(--space-6)' }}>
        We searched the selected ATS platforms but couldn&apos;t find matching postings within this timeframe and filter set.
        Try widening your date range or clearing active filters.
      </p>

      <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-primary" onClick={onWidenDateRange}>
          <Calendar size={14} aria-hidden="true" />
          <span>Widen date window to 30 days</span>
        </button>

        <button type="button" className="btn" onClick={onClearFilters}>
          <span>Clear all filters</span>
        </button>

        <button type="button" className="btn" onClick={onNewSearch}>
          <span>Start new search</span>
        </button>
      </div>
    </div>
  );
};

interface ErrorStateProps {
  message: string;
  isRateLimited?: boolean;
  onRetry: () => void;
  onEditSearch: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  message,
  isRateLimited,
  onRetry,
  onEditSearch,
}) => {
  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--status-error-text)',
        padding: 'var(--space-8) var(--space-6)',
        maxWidth: '640px',
        margin: 'var(--space-8) auto',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <div
          style={{
            width: '40px',
            height: '40px',
            background: 'var(--status-error-bg)',
            border: '1px solid var(--status-error-text)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--status-error-text)',
            flexShrink: 0,
          }}
        >
          {isRateLimited ? <AlertTriangle size={20} /> : <AlertCircle size={20} />}
        </div>

        <div style={{ flex: 1 }}>
          <h3
            style={{
              fontSize: 'var(--text-h3)',
              fontWeight: 700,
              color: 'var(--status-error-text)',
              marginBottom: 'var(--space-2)',
            }}
          >
            {isRateLimited ? 'Search rate limit reached' : 'Search request could not be completed'}
          </h3>

          <p style={{ color: 'var(--ink)', fontSize: 'var(--text-ui)', lineHeight: 1.6, marginBottom: 'var(--space-4)' }}>
            {message || 'An unexpected error occurred while communicating with the ATS search pipeline.'}
          </p>

          <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
            <button type="button" className="btn btn-primary" onClick={onRetry}>
              <RefreshCw size={13} aria-hidden="true" />
              <span>Retry search</span>
            </button>

            <button type="button" className="btn" onClick={onEditSearch}>
              <span>Edit parameters</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
