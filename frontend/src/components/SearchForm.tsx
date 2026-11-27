import React, { useState, useEffect, useRef } from 'react';
import type { SearchParams } from '../types';
import type { RecentSearchPreset } from '../lib/urlState';
import { ALL_PLATFORMS } from '../lib/constants';
import { areAllNigerianSelected, toggleNigerianPlatforms } from '../lib/nigerianPlatforms';
import { Search, ChevronDown, ChevronUp, Check, SlidersHorizontal, Bookmark, MapPin, Clock } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { CountryCombobox } from './CountryCombobox';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from './ui/collapsible';
import { PromptInput, PromptInputField, PromptInputActions } from './prompt-kit/prompt-input';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from './ui/select';

const POST_AGE_OPTIONS = [
  { value: '1', label: 'Past 24 hours' },
  { value: '3', label: 'Past 3 days' },
  { value: '7', label: 'Past 7 days' },
  { value: '14', label: 'Past 14 days' },
  { value: '30', label: 'Past 30 days' },
];

interface SearchFormProps {
  searchParams: SearchParams;
  setSearchParams: React.Dispatch<React.SetStateAction<SearchParams>>;
  onSubmit: (e: React.FormEvent) => void;
  selectedPlatforms: string[];
  setSelectedPlatforms: (platforms: string[]) => void;
  applicantCountry?: string;
  onChangeApplicantCountry?: (code: string) => void;
  recentSearches?: RecentSearchPreset[];
  onSelectRecentSearch?: (preset: RecentSearchPreset) => void;
  onClearRecentSearches?: () => void;
  savedCount?: number;
  onOpenSavedShortlist?: () => void;
  variant?: 'default' | 'embedded';
  autoFocus?: boolean;
  mode?: 'user' | 'admin';
}

export const SearchForm: React.FC<SearchFormProps> = ({
  searchParams,
  setSearchParams,
  onSubmit,
  selectedPlatforms,
  setSelectedPlatforms,
  applicantCountry = '',
  onChangeApplicantCountry,
  recentSearches = [],
  onSelectRecentSearch,
  onClearRecentSearches,
  savedCount = 0,
  onOpenSavedShortlist,
  variant = 'default',
  autoFocus,
  mode = 'user',
}) => {
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const keywordInputRef = useRef<HTMLInputElement>(null);
  const shouldAutoFocus = autoFocus ?? variant !== 'embedded';

  // Focus keyword field only when enabled and on fine pointer (desktop / mouse) devices
  useEffect(() => {
    if (!shouldAutoFocus) return;
    if (typeof window !== 'undefined' && window.matchMedia('(pointer: fine)').matches) {
      keywordInputRef.current?.focus({ preventScroll: true });
    }
  }, [shouldAutoFocus]);

  const togglePlatform = (id: string) => {
    if (selectedPlatforms.includes(id)) {
      setSelectedPlatforms(selectedPlatforms.filter((p) => p !== id));
    } else {
      setSelectedPlatforms([...selectedPlatforms, id]);
    }
  };

  const selectAllPlatforms = () => {
    setSelectedPlatforms(ALL_PLATFORMS.map((p) => p.id));
  };

  const selectNonePlatforms = () => {
    setSelectedPlatforms([]);
  };

  // Active secondary filters count for the badge
  const activeSecondaryCount =
    (searchParams.location.trim() ? 1 : 0) +
    (searchParams.postAge !== '7' ? 1 : 0) +
    (selectedPlatforms.length !== ALL_PLATFORMS.length ? 1 : 0);

  const activeFilterSummaryParts: string[] = [];
  if (searchParams.location.trim()) {
    activeFilterSummaryParts.push(`Location: ${searchParams.location.trim()}`);
  }
  if (searchParams.postAge !== '7') {
    const ageLabel =
      POST_AGE_OPTIONS.find((opt) => opt.value === searchParams.postAge)?.label ??
      `Past ${searchParams.postAge} days`;
    activeFilterSummaryParts.push(`Posted: ${ageLabel}`);
  }
  if (selectedPlatforms.length !== ALL_PLATFORMS.length) {
    activeFilterSummaryParts.push(
      `Sources: ${selectedPlatforms.length} of ${ALL_PLATFORMS.length}`
    );
  }

  const handleResetFilters = () => {
    setSearchParams((prev) => ({
      ...prev,
      location: '',
      postAge: '7',
    }));
    setSelectedPlatforms(ALL_PLATFORMS.map((p) => p.id));
  };

  return (
    <div className={`w-full flex flex-col ${variant === 'embedded' ? '' : 'pt-16 pb-24 sm:pt-20 sm:pb-32 max-md:pt-4 max-md:pb-12'}`}>
      {/* Centered Hero: Admin vs User presentation */}
      {variant !== 'embedded' && (
        mode === 'admin' ? (
          <div className="hero-region text-center mx-auto mb-10 sm:mb-12 max-w-3xl">
            <h1 className="text-display text-center tracking-tight">
              Find the signal behind the noise.
            </h1>
            <p className="text-lead max-w-[60ch] mx-auto text-center leading-relaxed text-[var(--ink-muted)] mt-4 sm:mt-5">
              Search public applicant tracking systems directly for fresh software and engineering postings.
              No aggregators, no ghost jobs.
            </p>
          </div>
        ) : (
          <div className="hero-region text-center mx-auto mb-8 sm:mb-10 max-w-3xl bp-fade-up">
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[var(--ink)]">
              What role are you looking for?
            </h1>
            <p className="text-sm text-[var(--ink-muted)] mt-2">
              Search by job title, skill or keyword. Choose where you can work from, then refine by
              location and work arrangement.
            </p>
          </div>
        )
      )}

      {/* Main Search Prompt Composer */}
      <div className={`search-form-card bp-fade-up bp-delay-1 w-full ${variant === 'embedded' ? '' : 'max-w-[760px] mx-auto'}`}>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <Collapsible open={showMoreFilters} onOpenChange={setShowMoreFilters} className="flex flex-col gap-4">
            <PromptInput className="border-[var(--border-strong)] bg-[var(--surface)]">
              {/* Top Row: Role or keyword (~65% desktop) + Country (~35% desktop) split by 1px vertical hairline */}
              <div
                data-testid="search-top-row"
                className={
                  onChangeApplicantCountry
                    ? 'grid grid-cols-1 md:grid-cols-[minmax(0,65fr)_minmax(0,35fr)] md:items-stretch'
                    : 'flex flex-col'
                }
              >
                <div className="relative flex flex-col justify-center px-4 py-3 max-md:px-3.5 max-md:pt-2.5 max-md:pb-1.5 min-w-0">
                  <label
                    htmlFor="keywords-input"
                    className="text-xs font-medium text-[var(--ink-muted)] block select-none mb-1 max-md:mb-0"
                  >
                    Role or keyword
                  </label>
                  <div className="relative flex items-center min-w-0">
                    <Search
                      className="size-4.5 max-md:size-4 text-[var(--ink-muted)] shrink-0 mr-2.5 pointer-events-none"
                      aria-hidden="true"
                    />
                    <PromptInputField
                      ref={keywordInputRef}
                      id="keywords-input"
                      name="keywords"
                      type="text"
                      required
                      value={searchParams.keywords}
                      onChange={(e) =>
                        setSearchParams({ ...searchParams, keywords: e.target.value })
                      }
                      placeholder="e.g. Backend Engineer, Data Analyst, Product Designer"
                      aria-label="Role or keyword"
                      className="px-0 py-1 h-9 max-md:h-11 text-[15px] md:text-lg font-medium min-w-0"
                    />
                  </div>
                </div>

                {/* Selectable Applicant Country ("Where can you work from?") */}
                {onChangeApplicantCountry && (
                  <div className="px-4 py-3 max-md:px-3.5 max-md:pt-2.5 max-md:pb-1.5 border-t border-[var(--border-subtle)] md:border-t-0 md:border-l md:border-[var(--border-subtle)] flex flex-col justify-center gap-1 max-md:gap-0 bg-transparent min-w-0">
                    <label
                      htmlFor="form-applicant-country-select"
                      className="text-xs font-medium text-[var(--ink-muted)] block select-none truncate"
                    >
                      Where can you work from?
                    </label>
                    <div className="w-full min-w-0">
                      <CountryCombobox
                        align="end"
                        flushMobile
                        value={applicantCountry}
                        onChange={onChangeApplicantCountry}
                        idPrefix="form-applicant-country"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Attached Action Dock: Work model & Filters (50/50 row on mobile) + Primary Search CTA */}
              <PromptInputActions className="p-3 sm:p-3.5">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-2.5 w-full">
                  <div className="grid grid-cols-2 gap-2 w-full md:flex md:items-center md:w-auto">
                    {/* Work Model (50% on mobile, auto on desktop) */}
                    <div className="relative flex items-center w-full md:w-auto min-w-0">
                      <label htmlFor="work-model-select" className="sr-only">
                        Work arrangement
                      </label>
                      <Select
                        value={searchParams.workModel}
                        onValueChange={(val) =>
                          setSearchParams({ ...searchParams, workModel: val || 'any' })
                        }
                      >
                        <SelectTrigger
                          id="work-model-trigger"
                          aria-label="Work arrangement"
                          className="data-[size=default]:h-10 sm:data-[size=default]:h-9 max-md:data-[size=default]:h-11 px-3 max-md:px-2.5 text-sm max-md:text-[13px] border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] w-full md:w-auto md:min-w-[140px] justify-between shadow-none"
                        >
                          <SelectValue placeholder="Any arrangement">
                            {searchParams.workModel === 'remote' ? (
                              'Remote only'
                            ) : searchParams.workModel === 'onsite' ? (
                              <>
                                Exclude remote
                                <span className="max-md:hidden"> (hybrid or in-person)</span>
                              </>
                            ) : (
                              'Any arrangement'
                            )}
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent align="start">
                          <SelectItem value="any">Any arrangement</SelectItem>
                          <SelectItem value="remote">Remote only</SelectItem>
                          <SelectItem value="onsite">Exclude remote (hybrid or in-person)</SelectItem>
                        </SelectContent>
                      </Select>
                      <select
                        id="work-model-select"
                        name="workModel"
                        aria-label="Work arrangement"
                        value={searchParams.workModel}
                        onChange={(e) =>
                          setSearchParams({ ...searchParams, workModel: e.target.value })
                        }
                        className="sr-only"
                        tabIndex={-1}
                      >
                        <option value="any">Any arrangement</option>
                        <option value="remote">Remote only</option>
                        <option value="onsite">Exclude remote (hybrid or in-person)</option>
                      </select>
                    </div>

                    {/* Filters Trigger (50% on mobile, auto on desktop) */}
                    <div className="w-full md:w-auto min-w-0">
                      <CollapsibleTrigger
                        aria-label="More filters"
                        className={`flex items-center justify-center md:justify-start gap-1.5 rounded-md border px-3 max-md:px-2.5 h-10 md:h-9 max-md:h-11 text-sm max-md:text-[13px] font-medium outline-none focus-visible:border-[var(--accent)] transition-[background-color,border-color,color,transform] duration-140 ease-out active:scale-[0.98] cursor-pointer select-none w-full md:w-auto min-w-0 ${
                          showMoreFilters || activeSecondaryCount > 0
                            ? 'bg-[var(--surface-raised)] border-[var(--ink)] text-[var(--ink)] hover:bg-[var(--surface-hover)]'
                            : 'bg-[var(--surface)] border-[var(--border)] text-[var(--ink)] hover:bg-[var(--surface-hover)]'
                        }`}
                      >
                        <SlidersHorizontal
                          className={`size-3.5 shrink-0 ${
                            showMoreFilters || activeSecondaryCount > 0
                              ? 'text-[var(--ink)]'
                              : 'text-[var(--ink-muted)]'
                          }`}
                          aria-hidden="true"
                        />
                        <span>Filters</span>
                        {activeSecondaryCount > 0 && (
                          <Badge
                            variant="secondary"
                            className="px-1.5 py-0 text-[11px] bg-[var(--surface)] text-[var(--ink)] border border-[var(--border)] shrink-0"
                          >
                            {activeSecondaryCount}
                          </Badge>
                        )}
                        {showMoreFilters ? (
                          <ChevronUp className="size-3.5 shrink-0 text-[var(--ink)]" />
                        ) : (
                          <ChevronDown
                            className={`size-3.5 shrink-0 ${
                              activeSecondaryCount > 0
                                ? 'text-[var(--ink)]'
                                : 'text-[var(--ink-muted)]'
                            }`}
                          />
                        )}
                      </CollapsibleTrigger>
                    </div>
                  </div>

                  {/* Row 4 on mobile: Search jobs full width, 44px tall (h-11). Desktop: md:w-auto, 36px tall (md:h-9) */}
                  <Button
                    type="submit"
                    className="w-full md:w-auto h-11 md:h-9 px-5 font-medium text-sm transition-[background-color,opacity,transform] duration-140 ease-out active:scale-[0.98] hover:opacity-95 cursor-pointer select-none shrink-0 motion-reduce:transform-none motion-reduce:transition-none"
                    style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
                  >
                    <Search className="size-3.5 mr-1.5 text-white" aria-hidden="true" />
                    <span>Search jobs</span>
                  </Button>
                </div>
              </PromptInputActions>
            </PromptInput>

            {/* Expandable Advanced Filters Drawer */}
            <CollapsibleContent
              keepMounted
              data-testid="filters-drawer"
              className="p-4 sm:p-5 rounded-lg bg-[var(--surface)] border border-[var(--border)] mt-2 flex flex-col gap-4"
            >
              {/* Active Filters Summary + Reset */}
              <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[var(--border-subtle)]">
                <span
                  data-testid="filters-active-summary"
                  className="text-xs text-[var(--ink-muted)]"
                >
                  {activeFilterSummaryParts.length > 0
                    ? activeFilterSummaryParts.join(' · ')
                    : `All ${ALL_PLATFORMS.length} sources · Past 7 days`}
                </span>
                {activeSecondaryCount > 0 && (
                  <button
                    type="button"
                    onClick={handleResetFilters}
                    className="h-7 max-md:h-11 max-md:px-3 px-2.5 rounded-md text-xs font-medium text-[var(--ink)] border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] cursor-pointer select-none"
                  >
                    Reset filters
                  </button>
                )}
              </div>

              {/* Location (optional) */}
              <div className="flex flex-col gap-1.5 pb-3 border-b border-[var(--border-subtle)]">
                <label
                  htmlFor="location-input"
                  className="text-xs font-medium text-[var(--ink)]"
                >
                  Location (optional)
                </label>
                <div className="relative flex items-center w-full sm:max-w-sm">
                  <MapPin
                    className="absolute left-3 size-4 text-[var(--ink-subtle)] pointer-events-none"
                    aria-hidden="true"
                  />
                  <Input
                    id="location-input"
                    name="location"
                    type="text"
                    value={searchParams.location}
                    onChange={(e) =>
                      setSearchParams({ ...searchParams, location: e.target.value })
                    }
                    placeholder="e.g. Lagos, London, Berlin"
                    aria-label="Location (optional)"
                    className="h-9 max-md:h-11 !pl-9 pr-3 text-sm text-[var(--ink)] placeholder:text-[var(--ink-subtle)] border-[var(--border)] bg-[var(--bg)] focus-visible:border-[var(--accent)] w-full shadow-none"
                  />
                </div>
                <p className="text-xs text-[var(--ink-subtle)]">
                  Leave blank to search across locations.
                </p>
              </div>
              {/* Posted Within (Post-age Chips) */}
              <div className="flex flex-col gap-2">
                <label className="text-xs font-medium text-[var(--ink)]">
                  Posted within
                </label>
                <div
                  className="platform-chips-grid grid grid-cols-2 sm:grid-cols-5 gap-2 pt-0.5 max-md:flex max-md:flex-wrap"
                  role="radiogroup"
                  aria-label="Posted within timeframe"
                >
                  {POST_AGE_OPTIONS.map((opt) => {
                    const isSelected = searchParams.postAge === opt.value;
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        role="radio"
                        aria-checked={isSelected}
                        onClick={() => setSearchParams({ ...searchParams, postAge: opt.value })}
                        className={`post-age-chip flex items-center justify-center px-2.5 h-9 max-md:h-11 max-md:px-3.5 max-md:whitespace-nowrap rounded-md text-xs sm:text-sm border transition-[background-color,border-color,transform] duration-140 ease-out active:scale-[0.98] cursor-pointer select-none ${
                          isSelected
                            ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                            : 'border-[var(--border)] bg-transparent text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
                        }`}
                      >
                        <span className="truncate max-md:overflow-visible max-md:text-clip">{opt.label}</span>
                      </button>
                    );
                  })}
                </div>
                <select
                  id="post-age-select"
                  name="postAge"
                  value={searchParams.postAge}
                  onChange={(e) =>
                    setSearchParams({ ...searchParams, postAge: e.target.value })
                  }
                  className="sr-only"
                  tabIndex={-1}
                  aria-hidden="true"
                >
                  <option value="1">Past 24 hours</option>
                  <option value="3">Past 3 days</option>
                  <option value="7">Past 7 days</option>
                  <option value="14">Past 14 days</option>
                  <option value="30">Past 30 days</option>
                </select>
              </div>

              {/* Checkboxes: Nigerian Boards (derived) */}
              <div className="pt-1">
                <label className="flex items-center gap-2.5 h-10 max-md:h-11 cursor-pointer select-none w-fit">
                  <input
                    type="checkbox"
                    id="nigerian-boards-check"
                    name="includeNigerianBoards"
                    checked={areAllNigerianSelected(selectedPlatforms)}
                    onChange={(e) =>
                      setSelectedPlatforms(toggleNigerianPlatforms(selectedPlatforms, e.target.checked))
                    }
                    className="size-4 accent-[var(--accent)] rounded-sm"
                  />
                  <span className="text-xs sm:text-sm text-[var(--ink)]">
                    Include Nigerian job boards
                  </span>
                </label>
              </div>

              {/* Target Hiring Platforms Multi-Select */}
              <div className="flex flex-col gap-2 pt-2.5 border-t border-[var(--border-subtle)]">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-[var(--ink)]">
                    Sources selected ({selectedPlatforms.length} of {ALL_PLATFORMS.length})
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={selectAllPlatforms}
                      className="h-8 max-md:h-11 px-3 rounded-md text-xs text-[var(--accent)] border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] cursor-pointer"
                    >
                      Select all
                    </button>
                    <button
                      type="button"
                      onClick={selectNonePlatforms}
                      className="h-8 max-md:h-11 px-3 rounded-md text-xs text-[var(--ink-muted)] border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] cursor-pointer"
                    >
                      Select none
                    </button>
                  </div>
                </div>

                <div className="platform-chips-grid grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                  {ALL_PLATFORMS.map((platform) => {
                    const isSelected = selectedPlatforms.includes(platform.id);
                    return (
                      <button
                        key={platform.id}
                        type="button"
                        onClick={() => togglePlatform(platform.id)}
                        className={`platform-chip-btn flex items-center justify-between px-3 h-9 max-md:h-11 rounded-md text-xs sm:text-sm border transition-[background-color,border-color,transform] duration-140 ease-out active:scale-[0.98] text-left cursor-pointer ${
                          isSelected
                            ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                            : 'border-[var(--border)] bg-transparent text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
                        }`}
                      >
                        <span className="truncate">{platform.name}</span>
                        {isSelected && <Check className="size-3.5 text-[var(--accent)] shrink-0 ml-1.5" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* Shortlist Footer Banner */}
          {savedCount > 0 && onOpenSavedShortlist && (
            <div className="flex items-center justify-between gap-3 pt-3 border-t border-[var(--border-subtle)] text-xs text-[var(--ink-muted)]">
              <span className="flex items-center gap-1.5">
                <Bookmark className="size-3.5 text-[var(--ink)]" aria-hidden="true" />
                <span>
                  <strong className="font-semibold text-[var(--ink)]">{savedCount}</strong> saved{' '}
                  {savedCount === 1 ? 'job' : 'jobs'} in your shortlist
                </span>
              </span>
              <button
                type="button"
                onClick={onOpenSavedShortlist}
                className="h-8 max-md:h-11 px-3 rounded-md text-xs font-medium border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink)] transition-colors cursor-pointer select-none"
              >
                View shortlist
              </button>
            </div>
          )}
        </form>

        {/* Quiet /app pre-search utility strip: verified source caption + conditional recent searches */}
        {variant !== 'embedded' && (
          <div className="mt-4 flex flex-col gap-3">
            <p
              data-testid="search-scope-caption"
              className="text-xs text-[var(--ink-subtle)] text-center"
            >
              Search company career pages and selected job boards. No account needed.
            </p>

            {recentSearches.length > 0 && onSelectRecentSearch && (
              <div
                data-testid="recent-searches-strip"
                className="pt-3 border-t border-[var(--border-subtle)] flex flex-col gap-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-[var(--ink-subtle)]">
                    Recent searches
                  </span>
                  {onClearRecentSearches && (
                    <button
                      type="button"
                      onClick={onClearRecentSearches}
                      aria-label="Clear recent searches"
                      className="h-8 max-md:h-11 max-md:min-w-11 px-3 rounded-md text-xs text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
                    >
                      Clear
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {recentSearches.map((preset) => {
                    const detailParts: string[] = [];
                    if (preset.location) detailParts.push(preset.location);
                    if (preset.workModel === 'remote') detailParts.push('Remote');
                    else if (preset.workModel === 'onsite') detailParts.push('In-person / Hybrid');
                    const label =
                      detailParts.length > 0
                        ? `${preset.keywords} · ${detailParts.join(' · ')}`
                        : preset.keywords;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        data-testid="recent-search-chip"
                        onClick={() => onSelectRecentSearch(preset)}
                        className="h-8 max-md:h-11 max-md:min-w-11 px-3 rounded-md text-xs border border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none inline-flex items-center gap-1.5 max-w-full"
                      >
                        <Clock className="size-3 text-[var(--ink-subtle)] shrink-0" aria-hidden="true" />
                        <span className="truncate">{label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* How Bottom Pot Works: 3 columns, visible only in admin mode */}
      {variant !== 'embedded' && mode === 'admin' && (
        <div className="w-full mt-20 sm:mt-24 border-t border-[var(--border)] pt-12 sm:pt-16">
          <h2 className="text-title mb-6 font-semibold text-[var(--ink)]">How Bottom Pot works</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12">
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-[var(--ink)]">
                Direct career page search
              </h3>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Searches primary company career boards (Greenhouse, Lever, Ashby, Workable) directly without aggregators.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-[var(--ink)]">
                Verified postings only
              </h3>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Every listing connects to a canonical ATS application link. Expired and phantom postings are omitted.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-[var(--ink)]">
                Transparent metadata
              </h3>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Strict classification for remote, hybrid, and on-site roles with source evidence and exact timestamps.
              </p>
            </div>
          </div>

          {/* Supported Platforms Line: 24px below, muted, same type size */}
          <div className="mt-8 pt-6 border-t border-[var(--border-subtle)]">
            <p className="text-xs text-[var(--ink-subtle)]">
              Supported platforms: Greenhouse · Lever · Ashby · Workable · Recruitee · SmartRecruiters · Teamtailor · Personio · Pinpoint · Workday · Jobberman · MyJobMag · HotNigerianJobs
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
