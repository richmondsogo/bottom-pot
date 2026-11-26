import React, { useState } from 'react';
import type { SearchParams, DoneMetrics } from '../types';
import { ALL_PLATFORMS } from '../lib/constants';
import {
  Search,
  MapPin,
  Edit2,
  Plus,
  RotateCcw,
  MoreHorizontal,
  Download,
  Trash2,
  Info,
  Link2,
  Cpu,
  ChevronDown,
  Check,
  SlidersHorizontal,
  X,
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Popover, PopoverTrigger, PopoverContent } from './ui/popover';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from './ui/select';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from './ui/dropdown-menu';

export interface CompactSearchBarProps {
  searchParams: SearchParams;
  setSearchParams: React.Dispatch<React.SetStateAction<SearchParams>>;
  onSubmit: (e: React.FormEvent) => void;
  selectedPlatforms: string[];
  setSelectedPlatforms: (platforms: string[]) => void;
  defaultEditing?: boolean;
  isStreaming?: boolean;
  onCancelSearch?: () => void;
  totalResults: number;
  filteredCount?: number;
  onlySavedJobs?: boolean;
  mode?: 'user' | 'admin';
  metrics: DoneMetrics | null;
  savedTimestamp: number | null;
  isTelemetryOpen?: boolean;
  onToggleTelemetry?: () => void;
  onEditSearch: () => void;
  onNewSearch: () => void;
  onRunAgain: () => void;
  onClearSaved: () => void;
  onDownloadCsv?: () => void;
  onDownloadJson?: () => void;
  onCopyShareLink?: () => void;
}

export const CompactSearchBar: React.FC<CompactSearchBarProps> = ({
  searchParams,
  setSearchParams,
  onSubmit,
  selectedPlatforms,
  setSelectedPlatforms,
  defaultEditing = false,
  isStreaming = false,
  onCancelSearch,
  totalResults,
  filteredCount,
  onlySavedJobs,
  mode = 'user',
  metrics,
  savedTimestamp,
  isTelemetryOpen,
  onToggleTelemetry,
  onEditSearch,
  onNewSearch,
  onRunAgain,
  onClearSaved,
  onDownloadCsv,
  onDownloadJson,
  onCopyShareLink,
}) => {
  const [isEditingQuery, setIsEditingQuery] = useState(defaultEditing);
  const platformCount = metrics?.providers_searched?.length || ALL_PLATFORMS.length;
  const durationSec = metrics?.search_time_ms ? `${(metrics.search_time_ms / 1000).toFixed(1)}s` : null;
  const queryLabel = searchParams.keywords || 'All roles';
  const trimmedKeywords = searchParams.keywords.trim();
  const isFiltered = filteredCount != null && filteredCount !== totalResults;
  const visibleCount = filteredCount ?? totalResults;

  let summaryText: string;
  if (onlySavedJobs) {
    summaryText = isFiltered
      ? `${filteredCount} of ${totalResults} saved ${totalResults === 1 ? 'role' : 'roles'}`
      : `${totalResults} saved ${totalResults === 1 ? 'role' : 'roles'}`;
  } else if (!trimmedKeywords) {
    summaryText = isFiltered
      ? `${filteredCount} of ${totalResults} open ${totalResults === 1 ? 'role' : 'roles'}`
      : `${totalResults} open ${totalResults === 1 ? 'role' : 'roles'}`;
  } else {
    summaryText = isFiltered
      ? `${filteredCount} of ${totalResults} ${totalResults === 1 ? 'role' : 'roles'} · ${trimmedKeywords}`
      : `${totalResults} ${totalResults === 1 ? 'role' : 'roles'} · ${trimmedKeywords}`;
  }

  const scopeNotes: string[] = [];
  if (searchParams.location.trim()) {
    scopeNotes.push(searchParams.location.trim());
  }
  if (searchParams.workModel === 'remote') {
    scopeNotes.push('Remote only');
  } else if (searchParams.workModel === 'onsite') {
    scopeNotes.push('Exclude remote');
  }
  if (searchParams.postAge !== '7') {
    scopeNotes.push(`Past ${searchParams.postAge}d`);
  }

  const togglePlatform = (id: string) => {
    if (selectedPlatforms.includes(id)) {
      setSelectedPlatforms(selectedPlatforms.filter((p) => p !== id));
    } else {
      setSelectedPlatforms([...selectedPlatforms, id]);
    }
  };

  const handleInlineSubmit = (e: React.FormEvent) => {
    setIsEditingQuery(false);
    onSubmit(e);
  };

  return (
    <div
      className={`search-summary-bar ${mode === 'admin' ? 'status-strip ' : ''}sticky top-[var(--header-height)] z-20 w-full border-b border-[var(--border)] bg-[var(--bg)] py-3 max-md:py-1.5 transition-colors`}
      style={{ backdropFilter: 'none' }}
    >
      <div className="page-shell flex flex-col gap-3 max-md:gap-2">
        {/* Primary Sticky Bar: Clear Result Context + Immediate New Search / Edit / Export */}
        <div className="flex flex-wrap items-center justify-between gap-3 max-md:flex-nowrap max-md:gap-2">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-small text-[var(--ink-muted)] min-w-0 max-md:flex-1 max-md:flex-nowrap max-md:overflow-hidden">
            {mode === 'admin' ? (
              <>
                <span className="font-semibold text-[var(--ink)] truncate max-w-[240px] sm:max-w-none">
                  {queryLabel}
                </span>
                <span className="text-[var(--border-strong)]">·</span>
                <span>Last {searchParams.postAge}d</span>
                <span className="text-[var(--border-strong)]">·</span>
                <span className="font-medium text-[var(--ink)]">
                  {totalResults} {totalResults === 1 ? 'posting' : 'postings'} from {platformCount}{' '}
                  {platformCount === 1 ? 'platform' : 'platforms'}
                </span>

                <Popover>
                  <PopoverTrigger
                    type="button"
                    className="inline-flex items-center gap-1.5 rounded-md text-xs text-[var(--ink-muted)] hover:text-[var(--ink)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] border border-[var(--border)] h-8 px-3 ml-1 cursor-pointer transition-colors"
                    title="View search metrics & cache details"
                  >
                    <span>Details</span>
                    <Info className="size-3 text-[var(--ink-subtle)]" aria-hidden="true" />
                  </PopoverTrigger>
                  <PopoverContent className="w-72 p-4 text-small" align="start">
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

                {onToggleTelemetry && (
                  <button
                    type="button"
                    onClick={onToggleTelemetry}
                    className={`inline-flex items-center gap-1.5 rounded-md text-xs border h-8 px-3 cursor-pointer transition-colors font-mono select-none ${
                      isTelemetryOpen
                        ? 'bg-[var(--accent)] text-[var(--accent-foreground)] border-[var(--accent)] font-semibold'
                        : 'text-[var(--ink-muted)] hover:text-[var(--ink)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] border-[var(--border)]'
                    }`}
                    title="Toggle live ATS telemetry & provider cards"
                    aria-expanded={isTelemetryOpen}
                  >
                    <Cpu className="size-3" aria-hidden="true" />
                    <span>Telemetry ({platformCount})</span>
                  </button>
                )}
              </>
            ) : (
              <>
                <span
                  data-testid="results-summary-text"
                  className="font-medium text-[var(--ink)] max-md:truncate"
                >
                  {summaryText}
                </span>
                {scopeNotes.length > 0 && (
                  <span className="text-xs text-[var(--ink-subtle)] truncate max-md:hidden">
                    · {scopeNotes.join(' · ')}
                  </span>
                )}
              </>
            )}

            {isStreaming && (
              <>
                <span className="text-[var(--border-strong)]">·</span>
                <span
                  data-testid="streaming-indicator"
                  className="inline-flex items-center gap-1.5 text-xs font-mono text-[var(--ink-muted)]"
                >
                  <span className="size-1.5 bg-[var(--accent)] bp-live-dot shrink-0" aria-hidden="true" />
                  <span>Checking more sources…</span>
                </span>
              </>
            )}

            {metrics?.partial && (
              <>
                <span className="text-[var(--border-strong)]">·</span>
                <span
                  data-testid="partial-results-notice"
                  className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-xs font-mono text-[var(--ink-muted)] bg-[var(--surface-subtle)] border border-[var(--border)]"
                >
                  Results may be incomplete
                </span>
              </>
            )}
          </div>

          {/* Primary Actions: New search always prominent right beside Edit search & Export */}
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 w-full sm:w-auto max-w-full min-w-0 max-md:w-auto max-md:flex-nowrap max-md:shrink-0">
            {isStreaming && onCancelSearch && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onCancelSearch}
                className="h-8 px-2.5 sm:px-3 text-xs border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] cursor-pointer shrink-0 max-md:h-11 max-md:min-w-11"
              >
                <X className="size-3.5 mr-1" aria-hidden="true" />
                <span>Stop</span>
              </Button>
            )}

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onNewSearch}
              className="h-8 text-xs px-2 sm:px-3 border-[var(--border-strong)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink)] font-medium cursor-pointer max-md:h-11 max-md:min-w-11"
            >
              <Plus className="size-3.5 mr-1 sm:mr-1.5 text-[var(--ink-muted)]" aria-hidden="true" />
              <span>New search</span>
            </Button>

            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-expanded={isEditingQuery}
              onClick={() => setIsEditingQuery((prev) => !prev)}
              className={`h-8 text-xs px-2 sm:px-3 max-md:hidden border cursor-pointer ${
                isEditingQuery
                  ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                  : 'border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink)]'
              }`}
            >
              <Edit2 className="size-3.5 mr-1 sm:mr-1.5 text-[var(--ink-muted)]" aria-hidden="true" />
              <span>Edit search</span>
            </Button>

            {(onDownloadCsv || onDownloadJson) && (
              <DropdownMenu>
                <DropdownMenuTrigger
                  className="h-8 text-xs px-2 sm:px-3 max-md:hidden rounded-md inline-flex items-center justify-center gap-1 border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink)] cursor-pointer select-none transition-colors"
                  aria-label="Export results"
                >
                  <Download className="size-3.5 mr-0.5 sm:mr-1 text-[var(--ink-muted)]" aria-hidden="true" />
                  <span>Export</span>
                  <ChevronDown className="hidden sm:inline size-3 ml-0.5 text-[var(--ink-subtle)]" aria-hidden="true" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  {onDownloadCsv && (
                    <DropdownMenuItem id="downloadBtn" onClick={onDownloadCsv}>
                      <Download className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                      <span>Download CSV ({visibleCount})</span>
                    </DropdownMenuItem>
                  )}
                  {onDownloadJson && (
                    <DropdownMenuItem id="downloadJsonBtn" onClick={onDownloadJson}>
                      <Download className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                      <span>Download JSON ({visibleCount})</span>
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}

            <DropdownMenu>
              <DropdownMenuTrigger
                className="h-8 w-8 max-md:size-11 p-2 rounded-md inline-flex items-center justify-center border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)] cursor-pointer select-none transition-colors"
                title="More actions"
                aria-label="More actions"
              >
                <MoreHorizontal className="size-4" aria-hidden="true" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuItem className="md:hidden" onClick={() => setIsEditingQuery((prev) => !prev)}>
                  <Edit2 className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                  <span>Edit search</span>
                </DropdownMenuItem>
                {onDownloadCsv && (
                  <DropdownMenuItem className="md:hidden" onClick={onDownloadCsv}>
                    <Download className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                    <span>Download CSV ({visibleCount})</span>
                  </DropdownMenuItem>
                )}
                {onDownloadJson && (
                  <DropdownMenuItem className="md:hidden" onClick={onDownloadJson}>
                    <Download className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                    <span>Download JSON ({visibleCount})</span>
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem onClick={onRunAgain}>
                  <RotateCcw className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                  <span>Run search again</span>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={onEditSearch}>
                  <SlidersHorizontal className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                  <span>Full search form</span>
                </DropdownMenuItem>
                {onCopyShareLink && (
                  <DropdownMenuItem onClick={onCopyShareLink}>
                    <Link2 className="size-3.5 mr-2 text-[var(--ink-muted)]" />
                    <span>Copy shareable link</span>
                  </DropdownMenuItem>
                )}

                {savedTimestamp && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      variant="destructive"
                      onClick={onClearSaved}
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

        {/* Collapsible Inline Query Editor (disclosed smoothly on demand) */}
        {isEditingQuery && (
          <div className="bp-inline-reveal pt-2.5 border-t border-[var(--border-subtle)]">
            <form onSubmit={handleInlineSubmit} className="flex flex-wrap items-center gap-2">
              <div className="relative flex-1 min-w-[200px]">
                <label htmlFor="compact-keywords-input" className="sr-only">
                  Role or keyword
                </label>
                <Search
                  className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--ink-subtle)] pointer-events-none"
                  aria-hidden="true"
                />
                <Input
                  id="compact-keywords-input"
                  name="compactKeywords"
                  type="text"
                  required
                  value={searchParams.keywords}
                  onChange={(e) => setSearchParams({ ...searchParams, keywords: e.target.value })}
                  placeholder="Role or keyword"
                  aria-label="Role or keyword"
                  className="h-9 max-md:h-11 !pl-9 pr-3 text-sm bg-[var(--surface)] border-[var(--border)] text-[var(--ink)]"
                />
              </div>

              <div className="relative w-full sm:w-48">
                <label htmlFor="compact-location-input" className="sr-only">
                  City or hub (optional)
                </label>
                <MapPin
                  className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--ink-subtle)] pointer-events-none"
                  aria-hidden="true"
                />
                <Input
                  id="compact-location-input"
                  name="compactLocation"
                  type="text"
                  value={searchParams.location}
                  onChange={(e) => setSearchParams({ ...searchParams, location: e.target.value })}
                  placeholder="City or hub (optional)"
                  aria-label="City or hub (optional)"
                  className="h-9 max-md:h-11 !pl-9 pr-3 text-sm bg-[var(--surface)] border-[var(--border)] text-[var(--ink)]"
                />
              </div>

              <Select
                value={searchParams.workModel}
                onValueChange={(val) => setSearchParams({ ...searchParams, workModel: val || 'any' })}
              >
                <SelectTrigger
                  id="compact-workmodel-trigger"
                  aria-label="Search work arrangement"
                  className="h-9 max-md:data-[size=default]:h-11 px-3 text-sm min-w-[140px]"
                >
                  <SelectValue placeholder="Any work model">
                    {searchParams.workModel === 'remote'
                      ? 'Remote only'
                      : searchParams.workModel === 'onsite'
                      ? 'Exclude remote'
                      : 'Any work model'}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent align="start">
                  <SelectItem value="any">Any work model</SelectItem>
                  <SelectItem value="remote">Remote only</SelectItem>
                  <SelectItem value="onsite">Exclude remote (In-person / Hybrid)</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={searchParams.postAge}
                onValueChange={(val) => setSearchParams({ ...searchParams, postAge: val || '7' })}
              >
                <SelectTrigger
                  id="compact-postage-trigger"
                  aria-label="Search timeframe"
                  className="h-9 max-md:data-[size=default]:h-11 px-3 text-sm min-w-[120px]"
                >
                  <SelectValue placeholder="Past 7d">
                    {searchParams.postAge === '1'
                      ? 'Past 24h'
                      : searchParams.postAge === '3'
                      ? 'Past 3d'
                      : searchParams.postAge === '14'
                      ? 'Past 14d'
                      : searchParams.postAge === '30'
                      ? 'Past 30d'
                      : 'Past 7d'}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent align="start">
                  <SelectItem value="1">Past 24 hours</SelectItem>
                  <SelectItem value="3">Past 3 days</SelectItem>
                  <SelectItem value="7">Past 7 days</SelectItem>
                  <SelectItem value="14">Past 14 days</SelectItem>
                  <SelectItem value="30">Past 30 days</SelectItem>
                </SelectContent>
              </Select>

              <Popover>
                <PopoverTrigger
                  type="button"
                  id="compact-sources-trigger"
                  className="h-9 max-md:h-11 px-3 rounded-md inline-flex items-center gap-1.5 text-sm border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink)] cursor-pointer select-none whitespace-nowrap"
                >
                  <SlidersHorizontal className="size-3.5 text-[var(--ink-muted)]" aria-hidden="true" />
                  <span>
                    Sources ({selectedPlatforms.length}/{ALL_PLATFORMS.length})
                  </span>
                </PopoverTrigger>
                <PopoverContent align="start" className="w-[min(22rem,calc(100vw-2rem))] p-3">
                  <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2">
                    <span className="text-xs font-medium text-[var(--ink)]">
                      Target sources ({selectedPlatforms.length}/{ALL_PLATFORMS.length})
                    </span>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => setSelectedPlatforms(ALL_PLATFORMS.map((p) => p.id))}
                        className="h-8 px-3 rounded-md text-xs text-[var(--ink)] border border-[var(--border)] hover:bg-[var(--surface-hover)] cursor-pointer"
                      >
                        All
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedPlatforms([])}
                        className="h-8 px-3 rounded-md text-xs text-[var(--ink-muted)] border border-[var(--border)] hover:bg-[var(--surface-hover)] cursor-pointer"
                      >
                        None
                      </button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 max-h-60 overflow-y-auto pt-1">
                    {ALL_PLATFORMS.map((platform) => {
                      const isSelected = selectedPlatforms.includes(platform.id);
                      return (
                        <button
                          key={platform.id}
                          type="button"
                          onClick={() => togglePlatform(platform.id)}
                          className={`flex items-center justify-between px-3 h-9 rounded-md text-xs border text-left cursor-pointer ${
                            isSelected
                              ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                              : 'border-[var(--border)] bg-transparent text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
                          }`}
                        >
                          <span className="truncate">{platform.name}</span>
                          {isSelected && <Check className="size-3 text-[var(--accent)] shrink-0 ml-1" />}
                        </button>
                      );
                    })}
                  </div>
                </PopoverContent>
              </Popover>

              <Button
                type="submit"
                className="h-9 max-md:h-11 px-4 text-sm font-medium text-white hover:opacity-95 cursor-pointer shrink-0"
                style={{ backgroundColor: 'var(--accent)' }}
              >
                <Search className="size-3.5 mr-1.5 text-white" aria-hidden="true" />
                <span>Update search</span>
              </Button>

              <Button
                type="button"
                variant="ghost"
                onClick={() => setIsEditingQuery(false)}
                className="h-9 max-md:h-11 px-3 text-xs text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] cursor-pointer shrink-0"
              >
                Cancel
              </Button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};
