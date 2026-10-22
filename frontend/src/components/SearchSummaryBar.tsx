import React from 'react';
import type { SearchParams, DoneMetrics } from '../types';
import { Edit2, RotateCcw, MoreHorizontal, Download, Trash2, Info } from 'lucide-react';
import { Button } from './ui/button';
import { Popover, PopoverTrigger, PopoverContent } from './ui/popover';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from './ui/dropdown-menu';

interface SearchSummaryBarProps {
  searchParams: SearchParams;
  totalResults: number;
  metrics: DoneMetrics | null;
  savedTimestamp: number | null;
  onEditSearch: () => void;
  onNewSearch: () => void;
  onRunAgain: () => void;
  onClearSaved: () => void;
  onDownloadCsv?: () => void;
  onDownloadJson?: () => void;
}

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

export const SearchSummaryBar: React.FC<SearchSummaryBarProps> = ({
  searchParams,
  totalResults,
  metrics,
  savedTimestamp,
  onEditSearch,
  onNewSearch,
  onRunAgain,
  onClearSaved,
  onDownloadCsv,
  onDownloadJson,
}) => {
  const parts: string[] = [];
  if (searchParams.keywords) parts.push(searchParams.keywords);
  if (searchParams.location) parts.push(searchParams.location);
  if (searchParams.workModel === 'remote') parts.push('Remote');
  else if (searchParams.workModel === 'onsite') parts.push('Onsite/Hybrid');
  parts.push(`Last ${searchParams.postAge}d`);

  const platformCount = metrics?.providers_searched?.length || 18;
  const durationSec = metrics ? (metrics.search_time_ms / 1000).toFixed(1) + 's' : null;
  const savedAgo = formatSavedAgo(savedTimestamp);

  return (
    <div
      className="search-summary-bar status-strip sticky top-[var(--header-height)] z-20 w-full border-b border-[var(--border)] bg-[var(--bg)] py-3.5 transition-colors"
      style={{ backdropFilter: 'none' }}
    >
      <div className="page-shell flex flex-wrap items-center justify-between gap-4">
        {/* Single Quiet Summary Line */}
        <div className="flex items-center gap-2.5 text-small text-[var(--ink-muted)] overflow-hidden">
          <span className="font-semibold text-[var(--ink)] truncate max-w-[280px] sm:max-w-none">
            {searchParams.keywords || 'All roles'}
          </span>
          <span className="text-[var(--border-strong)]">·</span>
          <span>Last {searchParams.postAge}d</span>
          <span className="text-[var(--border-strong)]">·</span>
          <span className="font-medium text-[var(--ink)]">
            {totalResults} {totalResults === 1 ? 'posting' : 'postings'} from {platformCount} {platformCount === 1 ? 'platform' : 'platforms'}
          </span>

          {savedAgo && (
            <>
              <span className="text-[var(--border-strong)]">·</span>
              <span className="text-[var(--ink-subtle)]">{savedAgo}</span>
            </>
          )}

          {/* Search Details Popover */}
          <Popover>
            <PopoverTrigger
              type="button"
              className="inline-flex items-center gap-1.5 text-xs text-[var(--ink-muted)] hover:text-[var(--ink)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] border border-[var(--border)] h-8 px-3 ml-1.5 cursor-pointer transition-colors"
              title="View search metrics & cache details"
            >
              <span>Details</span>
              <Info className="size-3 text-[var(--ink-subtle)]" aria-hidden="true" />
            </PopoverTrigger>
            <PopoverContent
              className="w-72 p-4 text-small bg-[var(--surface)] border border-[var(--border)] shadow-none"
              align="start"
            >
              <div className="flex flex-col gap-2.5">
                <span className="font-semibold text-small text-[var(--ink)] border-b border-[var(--border-subtle)] pb-1.5">
                  Search Telemetry
                </span>
                <div className="grid grid-cols-2 gap-2 text-caption">
                  <span className="text-[var(--ink-muted)]">Search duration:</span>
                  <span className="text-data text-right">{durationSec || '—'}</span>
                  <span className="text-[var(--ink-muted)]">Serper queries:</span>
                  <span className="text-data text-right">{metrics?.serper_queries_used ?? '—'}</span>
                  <span className="text-[var(--ink-muted)]">Cache status:</span>
                  <span className="text-data text-right">
                    {metrics?.cached ? 'Cache hit' : 'Live / Fresh'}
                  </span>
                  <span className="text-[var(--ink-muted)]">Platforms searched:</span>
                  <span className="text-data text-right">{platformCount}</span>
                </div>
              </div>
            </PopoverContent>
          </Popover>
        </div>

        {/* Action Controls: ONE Primary Edit Search + ONE Overflow Menu */}
        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={onEditSearch}
            className="h-9 text-sm px-3.5 border-[var(--border)] hover:bg-[var(--surface-hover)] text-[var(--ink)]"
          >
            <Edit2 className="size-3.5 mr-1.5 text-[var(--ink-muted)]" aria-hidden="true" />
            <span>Edit search</span>
          </Button>

          {/* Overflow Actions Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger
              className="h-9 w-9 p-2 inline-flex items-center justify-center border border-[var(--border)] hover:bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)] cursor-pointer select-none"
              title="More actions"
              aria-label="More actions"
            >
              <MoreHorizontal className="size-4" aria-hidden="true" />
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-52 bg-[var(--surface)] border border-[var(--border)] shadow-none"
            >
              <DropdownMenuItem onClick={onRunAgain} className="cursor-pointer">
                <RotateCcw className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                <span>Run again</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onNewSearch} className="cursor-pointer">
                <Edit2 className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                <span>New search</span>
              </DropdownMenuItem>

              <DropdownMenuSeparator />

              {onDownloadCsv && (
                <DropdownMenuItem id="downloadBtn" onClick={onDownloadCsv} className="cursor-pointer">
                  <Download className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                  <span>Download CSV</span>
                </DropdownMenuItem>
              )}
              {onDownloadJson && (
                <DropdownMenuItem id="downloadJsonBtn" onClick={onDownloadJson} className="cursor-pointer">
                  <Download className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                  <span>Download JSON</span>
                </DropdownMenuItem>
              )}

              {savedTimestamp && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={onClearSaved}
                    className="cursor-pointer text-[var(--destructive)] focus:text-[var(--destructive)]"
                  >
                    <Trash2 className="size-3.5 mr-2" />
                    <span>Clear saved results</span>
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
};
