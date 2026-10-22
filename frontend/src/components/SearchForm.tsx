import React, { useState } from 'react';
import type { SearchParams } from '../types';
import type { RecentSearchPreset } from '../lib/urlState';
import { ALL_PLATFORMS, ROLE_SUGGESTIONS } from '../lib/constants';
import { Search, ChevronDown, ChevronUp, Check, SlidersHorizontal, Bookmark } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from './ui/collapsible';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from './ui/select';

interface SearchFormProps {
  searchParams: SearchParams;
  setSearchParams: React.Dispatch<React.SetStateAction<SearchParams>>;
  onSubmit: (e: React.FormEvent) => void;
  selectedPlatforms: string[];
  setSelectedPlatforms: (platforms: string[]) => void;
  recentSearches?: RecentSearchPreset[];
  onSelectRecentSearch?: (preset: RecentSearchPreset) => void;
  savedCount?: number;
  onOpenSavedShortlist?: () => void;
}

export const SearchForm: React.FC<SearchFormProps> = ({
  searchParams,
  setSearchParams,
  onSubmit,
  selectedPlatforms,
  setSelectedPlatforms,
  recentSearches = [],
  onSelectRecentSearch,
  savedCount = 0,
  onOpenSavedShortlist,
}) => {
  const [showMoreFilters, setShowMoreFilters] = useState(false);

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
    (searchParams.postAge !== '7' ? 1 : 0) +
    (!searchParams.includeNigerian ? 1 : 0) +
    (selectedPlatforms.length !== ALL_PLATFORMS.length ? 1 : 0);

  return (
    <div className="w-full flex flex-col pt-16 pb-24 sm:pt-20 sm:pb-32">
      {/* Centered Hero: Headline + Lead of max ~60ch with explicit rhythm */}
      <div className="hero-region text-center mx-auto mb-10 sm:mb-12 max-w-3xl">
        <h1 className="text-display text-center tracking-tight">
          Find the signal behind the noise.
        </h1>
        <p className="text-lead max-w-[60ch] mx-auto text-center leading-relaxed text-[var(--ink-muted)] mt-4 sm:mt-5">
          Search public applicant tracking systems directly for fresh software and engineering postings.
          No aggregators, no ghost jobs.
        </p>
      </div>

      {/* Main Search Form: Centered Framed Panel (~720-780px) */}
      <div className="search-form-card w-full max-w-[760px] mx-auto border border-[var(--border)] bg-[var(--surface)] p-6 sm:p-8">
        <form onSubmit={onSubmit} className="flex flex-col gap-5 sm:gap-6">
          {/* Primary Field: Role or keyword */}
          <div className="flex flex-col gap-2">
            <label
              htmlFor="keywords-input"
              className="text-sm font-medium text-[var(--ink)]"
            >
              Role or keyword
            </label>
            <div className="relative flex items-center">
              <Search
                className="absolute left-3.5 size-4 text-[var(--ink-muted)] pointer-events-none"
                aria-hidden="true"
              />
              <Input
                id="keywords-input"
                name="keywords"
                type="text"
                required
                value={searchParams.keywords}
                onChange={(e) =>
                  setSearchParams({ ...searchParams, keywords: e.target.value })
                }
                placeholder="e.g. Backend Engineer, Systems, Full Stack"
                aria-label="Role or keyword"
                className="h-10 pl-10 pr-3 text-sm text-[var(--ink)] placeholder:text-[var(--ink-subtle)] border-[var(--border-strong)] bg-[var(--surface)] focus-visible:border-[var(--accent)] shadow-none"
              />
            </div>

            {/* Suggestions: Small square text-buttons with 6px 10px padding and 8px gaps */}
            <div className="flex flex-wrap items-center gap-2 pt-1 text-sm text-[var(--ink-muted)]">
              <span className="mr-0.5 text-xs text-[var(--ink-subtle)]">Try:</span>
              {ROLE_SUGGESTIONS.map((role) => (
                <button
                  key={role}
                  type="button"
                  onClick={() => setSearchParams({ ...searchParams, keywords: role })}
                  className="h-8 px-3 text-xs sm:text-sm inline-flex items-center bg-[var(--surface)] hover:bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink)] transition-[background-color,border-color,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer select-none"
                >
                  {role}
                </button>
              ))}
            </div>

            {recentSearches.length > 0 && onSelectRecentSearch && (
              <div className="flex flex-wrap items-center gap-2 pt-0.5 text-sm text-[var(--ink-muted)]">
                <span className="mr-0.5 text-xs text-[var(--ink-subtle)]">Recent:</span>
                {recentSearches.map((preset) => {
                  const label = [
                    preset.keywords,
                    preset.location || null,
                    preset.workModel === 'remote' ? 'Remote' : null,
                  ]
                    .filter(Boolean)
                    .join(' · ');
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => onSelectRecentSearch(preset)}
                      className="h-8 px-3 text-xs sm:text-sm inline-flex items-center bg-[var(--surface-subtle)] hover:bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink)] transition-[background-color,border-color,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer select-none"
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Secondary Row: Location and Work Model side-by-side (40px high, 12px padding) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div className="flex flex-col gap-2">
              <label
                htmlFor="location-input"
                className="text-sm font-medium text-[var(--ink)]"
              >
                Location or country
              </label>
              <Input
                id="location-input"
                name="location"
                type="text"
                value={searchParams.location}
                onChange={(e) =>
                  setSearchParams({ ...searchParams, location: e.target.value })
                }
                placeholder="e.g. Nigeria, London, Europe"
                aria-label="Location or country"
                className="h-10 px-3 text-sm text-[var(--ink)] placeholder:text-[var(--ink-subtle)] border-[var(--border)] bg-[var(--surface)] focus-visible:border-[var(--accent)] shadow-none"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label
                htmlFor="work-model-select"
                className="text-sm font-medium text-[var(--ink)]"
              >
                Work model
              </label>
              <div className="relative">
                <Select
                  value={searchParams.workModel}
                  onValueChange={(val) =>
                    setSearchParams({ ...searchParams, workModel: val || 'any' })
                  }
                >
                  <SelectTrigger
                    id="work-model-trigger"
                    aria-label="Choose work arrangement"
                    className="h-10 w-full px-3 text-sm"
                  >
                    <SelectValue placeholder="Any work model">
                      {searchParams.workModel === 'remote'
                        ? 'Remote only'
                        : searchParams.workModel === 'onsite'
                        ? 'Exclude remote (In-person / Hybrid)'
                        : 'Any work model'}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent align="start">
                    <SelectItem value="any">Any work model</SelectItem>
                    <SelectItem value="remote">Remote only</SelectItem>
                    <SelectItem value="onsite">Exclude remote (In-person / Hybrid)</SelectItem>
                  </SelectContent>
                </Select>
                <select
                  id="work-model-select"
                  name="workModel"
                  aria-label="Work model"
                  value={searchParams.workModel}
                  onChange={(e) =>
                    setSearchParams({ ...searchParams, workModel: e.target.value })
                  }
                  className="sr-only"
                  tabIndex={-1}
                >
                  <option value="any">Any work model</option>
                  <option value="remote">Remote only</option>
                  <option value="onsite">Exclude remote (In-person / Hybrid)</option>
                </select>
              </div>
            </div>
          </div>

          {/* More Filters Disclosure */}
          <Collapsible open={showMoreFilters} onOpenChange={setShowMoreFilters}>
            <div className="flex items-center justify-between pt-0.5">
              <CollapsibleTrigger
                aria-label="More filters"
                className="flex items-center gap-2 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-[var(--border)] px-3 h-9 text-sm font-medium transition-[background-color,border-color,color,transform] duration-140 ease-out active:scale-[0.98] cursor-pointer select-none"
              >
                <SlidersHorizontal className="size-3.5" aria-hidden="true" />
                <span>More filters</span>
                {activeSecondaryCount > 0 && (
                  <Badge variant="secondary" className="px-1.5 py-0 text-[11px] bg-[var(--surface-subtle)]">
                    {activeSecondaryCount}
                  </Badge>
                )}
                {showMoreFilters ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
              </CollapsibleTrigger>
            </div>

            <CollapsibleContent className="p-5 sm:p-6 bg-[var(--surface)] border-t border-[var(--border)] mt-3 flex flex-col gap-5">
              {/* Recency and Nigerian boards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div className="flex flex-col gap-2">
                  <label htmlFor="post-age-trigger" className="text-sm font-medium text-[var(--ink)]">
                    Posted within
                  </label>
                  <div className="relative">
                    <Select
                      value={searchParams.postAge}
                      onValueChange={(val) =>
                        setSearchParams({ ...searchParams, postAge: val || '7' })
                      }
                    >
                      <SelectTrigger
                        id="post-age-trigger"
                        aria-label="Posted within timeframe"
                        className="h-10 w-full px-3 text-sm"
                      >
                        <SelectValue placeholder="Past 7 days (default)">
                          {searchParams.postAge === '1'
                            ? 'Past 24 hours'
                            : searchParams.postAge === '3'
                            ? 'Past 3 days'
                            : searchParams.postAge === '14'
                            ? 'Past 14 days'
                            : searchParams.postAge === '30'
                            ? 'Past 30 days'
                            : 'Past 7 days (default)'}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent align="start">
                        <SelectItem value="1">Past 24 hours</SelectItem>
                        <SelectItem value="3">Past 3 days</SelectItem>
                        <SelectItem value="7">Past 7 days (default)</SelectItem>
                        <SelectItem value="14">Past 14 days</SelectItem>
                        <SelectItem value="30">Past 30 days</SelectItem>
                      </SelectContent>
                    </Select>
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
                      <option value="7">Past 7 days (default)</option>
                      <option value="14">Past 14 days</option>
                      <option value="30">Past 30 days</option>
                    </select>
                  </div>
                </div>

                <div className="flex flex-col justify-end">
                  <label className="flex items-center gap-2.5 h-10 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      id="nigerian-boards-check"
                      name="includeNigerian"
                      checked={searchParams.includeNigerian}
                      onChange={(e) =>
                        setSearchParams({ ...searchParams, includeNigerian: e.target.checked })
                      }
                      className="size-4 accent-[var(--accent)]"
                    />
                    <span className="text-sm text-[var(--ink)]">
                      Include Nigerian boards (Jobberman, MyJobMag)
                    </span>
                  </label>
                </div>
              </div>

              {/* Platforms Multi-selection: 4 columns (2 mobile), 36px high, neutral selected state */}
              <div className="flex flex-col gap-2.5 pt-3 border-t border-[var(--border-subtle)]">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-[var(--ink)]">
                    Target ATS platforms ({selectedPlatforms.length} of {ALL_PLATFORMS.length} selected)
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={selectAllPlatforms}
                      className="text-xs text-[var(--accent)] hover:underline cursor-pointer"
                    >
                      Select all
                    </button>
                    <span className="text-[var(--border-strong)]">·</span>
                    <button
                      type="button"
                      onClick={selectNonePlatforms}
                      className="text-xs text-[var(--ink-muted)] hover:underline cursor-pointer"
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
                        className={`platform-chip-btn flex items-center justify-between px-3 h-9 text-sm border transition-[background-color,border-color,transform] duration-140 ease-out active:scale-[0.98] text-left cursor-pointer ${
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

          {/* Form Actions: Full-width green button with hint below */}
          <div className="flex flex-col gap-2.5 pt-2">
            <Button
              type="submit"
              className="w-full h-11 sm:h-12 px-6 font-medium text-sm sm:text-base transition-opacity hover:opacity-95 cursor-pointer"
              style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
            >
              <Search className="size-4 mr-2 text-white" aria-hidden="true" />
              <span>Search ATS platforms</span>
            </Button>
            <p className="text-xs text-[var(--ink-subtle)] text-center">
              Press Enter or click Search to stream verified results
            </p>
          </div>

          {savedCount > 0 && onOpenSavedShortlist && (
            <div className="flex items-center justify-between gap-3 pt-4 border-t border-[var(--border-subtle)] text-xs text-[var(--ink-muted)]">
              <span className="flex items-center gap-1.5">
                <Bookmark className="size-3.5 text-[var(--ink)]" aria-hidden="true" />
                <span>
                  You have <strong className="font-semibold text-[var(--ink)]">{savedCount}</strong> saved{' '}
                  {savedCount === 1 ? 'posting' : 'postings'} in your shortlist
                </span>
              </span>
              <button
                type="button"
                onClick={onOpenSavedShortlist}
                className="h-8 px-3 text-xs font-medium border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink)] transition-colors cursor-pointer select-none"
              >
                View shortlist
              </button>
            </div>
          )}
        </form>
      </div>

      {/* How Bottom Pot Works: 3 columns, section margin-top 64-96px, hairline above */}
      <div className="w-full mt-20 sm:mt-24 border-t border-[var(--border)] pt-12 sm:pt-16">
        <h2 className="text-title mb-6 font-semibold text-[var(--ink)]">How Bottom Pot works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12">
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold text-[var(--ink)]">
              Direct ATS querying
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
            Supported platforms: Greenhouse · Lever · Ashby · Workable · Recruitee · BambooHR · SmartRecruiters · Jobberman · MyJobMag
          </p>
        </div>
      </div>
    </div>
  );
};
