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
          <div className="text-sm font-medium text-[var(--ink)]">
            Searching ATS platforms
          </div>
          <div className="text-xs text-[var(--ink-muted)]">
            {statusMessage || 'Querying Google indexes for public ATS company boards.'}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="font-mono text-xs tabular-nums text-[var(--ink-muted)]">
            {seconds}s elapsed
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={onCancel}
            className="h-8 px-3 text-xs border border-[var(--border)] hover:bg-[var(--surface-hover)] text-[var(--ink)] cursor-pointer"
          >
            Cancel
          </Button>
        </div>
      </div>

      {/* Desktop table skeleton matching ResultsTable columns and padding */}
      <div className="hidden md:block w-full overflow-x-auto">
        <table
          className="results-table w-full border-collapse"
          style={{ tableLayout: 'fixed' }}
          aria-label="Loading job listings"
        >
          <colgroup>
            <col style={{ width: 'auto', minWidth: '260px' }} />
            <col style={{ width: '240px' }} />
            <col style={{ width: '220px' }} />
            <col style={{ width: '120px' }} />
            <col style={{ width: '100px' }} />
          </colgroup>

          <thead>
            <tr className="border-b border-[var(--border)] text-left text-xs font-medium text-[var(--ink-muted)]">
              <th scope="col" className="py-3 px-3.5 font-medium select-none">Role</th>
              <th scope="col" className="py-3 px-3.5 font-medium select-none">Company</th>
              <th scope="col" className="py-3 px-3.5 font-medium select-none">Location</th>
              <th scope="col" className="py-3 px-3.5 font-medium select-none">Work model</th>
              <th scope="col" className="py-3 px-3.5 font-medium select-none">Posted</th>
            </tr>
          </thead>

          <tbody>
            {[...Array(6)].map((_, i) => (
              <tr
                key={i}
                className="border-b border-[var(--border-subtle)] animate-pulse"
              >
                {/* Role skeleton */}
                <td className="py-3.5 px-3.5 align-middle">
                  <div
                    className="h-4 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]"
                    style={{ width: `${55 + (i % 3) * 15}%` }}
                  />
                </td>

                {/* Company skeleton: Monogram tile + company name */}
                <td className="py-3.5 px-3.5 align-middle">
                  <div className="flex items-center gap-2.5">
                    <div className="size-7 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] shrink-0" />
                    <div className="flex flex-col gap-1.5 flex-1 min-w-0">
                      <div
                        className="h-3.5 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]"
                        style={{ width: `${90 + (i % 2) * 35}px` }}
                      />
                      <div className="h-2.5 w-12 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]" />
                    </div>
                  </div>
                </td>

                {/* Location skeleton */}
                <td className="py-3.5 px-3.5 align-middle">
                  <div
                    className="h-3.5 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]"
                    style={{ width: '110px' }}
                  />
                </td>

                {/* Work model skeleton */}
                <td className="py-3.5 px-3.5 align-middle">
                  <div className="h-5 w-16 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]" />
                </td>

                {/* Posted date skeleton */}
                <td className="py-3.5 px-3.5 align-middle">
                  <div className="h-3.5 w-12 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile card skeleton */}
      <div className="block md:hidden flex flex-col divide-y divide-[var(--border-subtle)]">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="py-3 px-1 flex flex-col gap-2 animate-pulse">
            <div
              className="h-4 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]"
              style={{ width: `${65 + (i % 3) * 12}%` }}
            />
            <div className="flex items-center gap-2">
              <div className="size-6 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] shrink-0" />
              <div className="h-3.5 w-24 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]" />
              <span className="text-[var(--border-strong)]">·</span>
              <div className="h-3.5 w-16 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]" />
            </div>
            <div className="flex items-center justify-between pt-1">
              <div className="h-4 w-14 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]" />
              <div className="h-3.5 w-12 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]" />
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
