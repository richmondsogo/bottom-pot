import React, { useState, useEffect } from 'react';
import { AlertTriangle, AlertCircle, RefreshCw, Calendar, Edit2 } from 'lucide-react';
import { Button } from './ui/button';
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
  EmptyMedia,
} from './ui/empty';

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
    <div className="w-full pb-16">
      {/* Quiet Status Line with Tabular Timer */}
      <div className="flex items-center justify-between py-3 border-b border-[var(--border)] mb-4">
        <div className="flex flex-col gap-0.5">
          <div className="text-body font-semibold text-[var(--ink)]">
            Searching ATS platforms directly
          </div>
          <div className="text-small text-[var(--ink-muted)]">
            {statusMessage || 'Querying Google indexes for public ATS company boards. This typically takes 10–25s.'}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-data text-small text-[var(--accent)] font-medium">
            {seconds}s elapsed
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={onCancel}
            className="h-7 text-small border border-[var(--border)] hover:bg-[var(--surface-hover)] text-[var(--ink)]"
          >
            Cancel
          </Button>
        </div>
      </div>

      {/* Two-Line Skeleton Rows matching the exact anatomy of real results */}
      <div className="flex flex-col divide-y divide-[var(--border-subtle)]" aria-label="Loading job listings">
        {[...Array(6)].map((_, i) => (
          <div
            key={i}
            className="py-5 px-4 sm:px-6 flex items-center justify-between gap-4 animate-pulse"
          >
            {/* Left: Two-line role & company skeleton */}
            <div className="flex flex-col gap-2 flex-1 min-w-0">
              {/* Line 1: Role title skeleton */}
              <div
                className="h-4.5 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]"
                style={{ width: `${45 + (i % 3) * 18}%` }}
              />

              {/* Line 2: Company monogram + name skeleton */}
              <div className="flex items-center gap-2">
                <div className="size-4 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] shrink-0" />
                <div
                  className="h-3.5 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]"
                  style={{ width: `${120 + (i % 2) * 40}px` }}
                />
                <span className="text-[var(--border-strong)]">·</span>
                <div
                  className="h-3.5 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]"
                  style={{ width: '90px' }}
                />
              </div>
            </div>

            {/* Right: Work model & date skeleton */}
            <div className="flex items-center gap-2.5 shrink-0">
              <div className="h-5 w-16 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] hidden sm:block" />
              <div className="h-4 w-12 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]" />
              <div className="h-3.5 w-14 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] hidden sm:block" />
            </div>
          </div>
        ))}
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
    <div className="w-full py-16 flex items-center justify-center">
      <Empty className="max-w-md p-8 border border-[var(--border)] bg-[var(--surface)]">
        <EmptyMedia variant="icon" className="bg-[var(--surface-subtle)] text-[var(--ink-muted)]">
          <AlertCircle className="size-5" />
        </EmptyMedia>
        <EmptyHeader>
          <EmptyTitle className="text-title text-[var(--ink)]">
            No job postings matched your criteria
          </EmptyTitle>
          <EmptyDescription className="text-small text-[var(--ink-muted)]">
            We searched target ATS platforms but found no open positions matching your keyword and filters.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent className="flex flex-row flex-wrap items-center justify-center gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onWidenDateRange}
            className="text-small border-[var(--border-strong)] hover:bg-[var(--surface-hover)]"
          >
            <Calendar className="size-3.5 mr-1 text-[var(--ink-muted)]" />
            <span>Widen date range</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onClearFilters}
            className="text-small border-[var(--border-strong)] hover:bg-[var(--surface-hover)]"
          >
            <span>Clear filters</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onNewSearch}
            className="text-small border-[var(--border-strong)] hover:bg-[var(--surface-hover)]"
          >
            <span>New search</span>
          </Button>
        </EmptyContent>
      </Empty>
    </div>
  );
};

interface ErrorStateProps {
  message?: string;
  isRateLimited?: boolean;
  onRetry: () => void;
  onEditSearch?: () => void;
  onNewSearch?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  message,
  isRateLimited,
  onRetry,
  onEditSearch,
  onNewSearch,
}) => {
  return (
    <div className="w-full py-16 flex items-center justify-center">
      <Empty className="max-w-md p-8 border border-[var(--border)] bg-[var(--surface)]">
        <EmptyMedia variant="icon" className="bg-[var(--surface-subtle)] text-[var(--destructive)]">
          <AlertTriangle className="size-5" />
        </EmptyMedia>
        <EmptyHeader>
          <EmptyTitle className="text-title text-[var(--ink)]">
            {isRateLimited ? 'Search rate limit reached' : 'Search request could not be completed'}
          </EmptyTitle>
          <EmptyDescription className="text-small text-[var(--ink-muted)]">
            {message || 'The search pipeline encountered an unexpected issue while fetching postings. Please try again.'}
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent className="flex flex-row flex-wrap items-center justify-center gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="text-small border-[var(--border-strong)] hover:bg-[var(--surface-hover)]"
          >
            <RefreshCw className="size-3.5 mr-1" />
            <span>Retry search</span>
          </Button>

          {onEditSearch && (
            <Button
              variant="outline"
              size="sm"
              onClick={onEditSearch}
              className="text-small border-[var(--border-strong)] hover:bg-[var(--surface-hover)]"
            >
              <Edit2 className="size-3.5 mr-1" />
              <span>Edit search</span>
            </Button>
          )}

          {onNewSearch && (
            <Button
              variant="outline"
              size="sm"
              onClick={onNewSearch}
              className="text-small border-[var(--border-strong)] hover:bg-[var(--surface-hover)]"
            >
              <span>New search</span>
            </Button>
          )}
        </EmptyContent>
      </Empty>
    </div>
  );
};
