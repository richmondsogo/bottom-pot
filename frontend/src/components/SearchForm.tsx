import React, { useState } from 'react';
import type { SearchParams } from '../types';
import type { RecentSearchPreset } from '../lib/urlState';
import { ALL_PLATFORMS, ROLE_SUGGESTIONS } from '../lib/constants';
import { Search, ChevronDown, ChevronUp, Check, SlidersHorizontal, Bookmark, MapPin } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from './ui/collapsible';
import { PromptSuggestion } from './prompt-kit/prompt-suggestion';
import { PromptInput, PromptInputField, PromptInputActions } from './prompt-kit/prompt-input';
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
  variant?: 'default' | 'embedded';
  mode?: 'user' | 'admin';
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
  variant = 'default',
  mode = 'user',
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
    <div className={`w-full flex flex-col ${variant === 'embedded' ? '' : 'pt-16 pb-24 sm:pt-20 sm:pb-32'}`}>
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
          <div className="hero-region text-center mx-auto mb-8 sm:mb-10 max-w-3xl">
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[var(--ink)]">
              Search jobs
            </h1>
          </div>
        )
      )}

      {/* Main Search Prompt Composer */}
      <div className={`search-form-card w-full ${variant === 'embedded' ? '' : 'max-w-[760px] mx-auto'}`}>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <Collapsible open={showMoreFilters} onOpenChange={setShowMoreFilters} className="flex flex-col gap-4">
            <PromptInput className="border-[var(--border-strong)] bg-[var(--surface)]">
              {/* Top Prompt Input Area: Role or Keyword */}
              <div className="relative flex flex-col pt-1">
                <label
                  htmlFor="keywords-input"
                  className="px-4 pt-2.5 pb-0.5 text-xs font-medium text-[var(--ink-muted)] block select-none"
                >
                  Role or keyword
                </label>
                <div className="relative flex items-center px-4 pb-2.5">
                  <Search
                    className="size-4.5 text-[var(--ink-muted)] shrink-0 mr-3 pointer-events-none"
                    aria-hidden="true"
                  />
                  <PromptInputField
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
                    className="px-0 py-1 text-base sm:text-lg font-medium"
                  />
                </div>
              </div>

              {/* Attached Bottom Action Dock */}
              <PromptInputActions>
                <div className="flex flex-wrap items-center gap-2">
                  {/* Inline Location Field with MapPin */}
                  <div className="relative flex items-center">
                    <label htmlFor="location-input" className="sr-only">
                      Location or country
                    </label>
                    <div className="relative flex items-center">
                      <MapPin
                        className="absolute left-2.5 size-3.5 text-[var(--ink-subtle)] pointer-events-none"
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
                        placeholder="Location"
                        aria-label="Location or country"
                        className="h-8 pl-8 pr-2.5 text-xs sm:text-sm text-[var(--ink)] placeholder:text-[var(--ink-subtle)] border-[var(--border)] bg-[var(--surface)] focus-visible:border-[var(--accent)] w-32 sm:w-44 shadow-none"
                        style={{ borderRadius: 0 }}
                      />
                    </div>
                  </div>

                  {/* Inline Work Model Selector */}
                  <div className="relative flex items-center">
                    <label htmlFor="work-model-select" className="sr-only">
                      Work model
                    </label>
                    <Select
                      value={searchParams.workModel}
                      onValueChange={(val) =>
                        setSearchParams({ ...searchParams, workModel: val || 'any' })
                      }
                    >
                      <SelectTrigger
                        id="work-model-trigger"
                        aria-label="Choose work arrangement"
                        className="h-8 px-2.5 text-xs sm:text-sm border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] w-auto min-w-[110px] shadow-none"
                        style={{ borderRadius: 0 }}
                      >
                        <SelectValue placeholder="Any work model">
                          {searchParams.workModel === 'remote'
                            ? 'Remote only'
                            : searchParams.workModel === 'onsite'
                            ? 'Onsite / Hybrid'
                            : 'Any model'}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent align="start" style={{ borderRadius: 0 }}>
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

                  {/* More Filters Trigger Inside Action Dock */}
                  <CollapsibleTrigger
                    aria-label="More filters"
                    className="flex items-center gap-1.5 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-[var(--border)] px-2.5 h-8 text-xs font-medium transition-[background-color,border-color,color,transform] duration-140 ease-out active:scale-[0.98] cursor-pointer select-none"
                    style={{ borderRadius: 0 }}
                  >
                    <SlidersHorizontal className="size-3" aria-hidden="true" />
                    <span>Filters</span>
                    {activeSecondaryCount > 0 && (
                      <Badge variant="secondary" className="px-1 py-0 text-[10px] bg-[var(--surface-subtle)]" style={{ borderRadius: 0 }}>
                        {activeSecondaryCount}
                      </Badge>
                    )}
                    {showMoreFilters ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                  </CollapsibleTrigger>
                </div>

                {/* Primary Search Submit Button with Restrained Motion */}
                <Button
                  type="submit"
                  className="h-8 sm:h-9 px-4 sm:px-5 font-medium text-xs sm:text-sm transition-[background-color,opacity,transform] duration-140 ease-out active:scale-[0.98] hover:opacity-95 cursor-pointer select-none shrink-0 motion-reduce:transform-none motion-reduce:transition-none"
                  style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF', borderRadius: 0 }}
                >
                  <Search className="size-3.5 mr-1.5 text-white" aria-hidden="true" />
                  <span>Search jobs</span>
                </Button>
              </PromptInputActions>
            </PromptInput>

            {/* Quick Suggestions & Recents (PromptSuggestion) */}
            <div className="flex flex-col gap-1.5 pt-2">
              <div className="flex flex-wrap items-center gap-1.5 text-sm text-[var(--ink-muted)]">
                <span className="mr-0.5 text-xs text-[var(--ink-subtle)]">Try:</span>
                {ROLE_SUGGESTIONS.map((role) => (
                  <PromptSuggestion
                    key={role}
                    type="button"
                    onClick={() => setSearchParams({ ...searchParams, keywords: role })}
                  >
                    {role}
                  </PromptSuggestion>
                ))}
              </div>

              {recentSearches.length > 0 && onSelectRecentSearch && (
                <div className="flex flex-wrap items-center gap-1.5 text-sm text-[var(--ink-muted)]">
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
                      <PromptSuggestion
                        key={preset.id}
                        type="button"
                        onClick={() => onSelectRecentSearch(preset)}
                        className="border-dashed"
                      >
                        {label}
                      </PromptSuggestion>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Expandable Advanced Filters Drawer */}
            <CollapsibleContent
              keepMounted
              className="p-4 sm:p-5 bg-[var(--surface)] border border-[var(--border)] mt-2.5 flex flex-col gap-4"
              style={{ borderRadius: 0 }}
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="post-age-trigger" className="text-xs font-medium text-[var(--ink)]">
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
                        className="h-8.5 w-full px-3 text-xs sm:text-sm"
                        style={{ borderRadius: 0 }}
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
                      <SelectContent align="start" style={{ borderRadius: 0 }}>
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
                  <label className="flex items-center gap-2.5 h-8.5 cursor-pointer select-none">
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
                    <span className="text-xs sm:text-sm text-[var(--ink)]">
                      Include Nigerian boards (Jobberman, MyJobMag)
                    </span>
                  </label>
                </div>
              </div>

              <div className="flex flex-col gap-2 pt-2.5 border-t border-[var(--border-subtle)]">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-[var(--ink)]">
                    Target hiring platforms ({selectedPlatforms.length} of {ALL_PLATFORMS.length} selected)
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
                        className={`platform-chip-btn flex items-center justify-between px-3 h-8 text-xs sm:text-sm border transition-[background-color,border-color,transform] duration-140 ease-out active:scale-[0.98] text-left cursor-pointer ${
                          isSelected
                            ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                            : 'border-[var(--border)] bg-transparent text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
                        }`}
                        style={{ borderRadius: 0 }}
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
                  You have <strong className="font-semibold text-[var(--ink)]">{savedCount}</strong> saved{' '}
                  {savedCount === 1 ? 'posting' : 'postings'} in your shortlist
                </span>
              </span>
              <button
                type="button"
                onClick={onOpenSavedShortlist}
                className="h-7 px-2.5 text-xs font-medium border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink)] transition-colors cursor-pointer select-none"
                style={{ borderRadius: 0 }}
              >
                View shortlist
              </button>
            </div>
          )}
        </form>
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
              Supported platforms: Greenhouse · Lever · Ashby · Workable · Recruitee · BambooHR · SmartRecruiters · Jobberman · MyJobMag
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
