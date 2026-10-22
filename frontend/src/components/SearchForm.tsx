import React, { useState } from 'react';
import type { SearchParams } from '../types';
import { ALL_PLATFORMS, ROLE_SUGGESTIONS } from '../lib/constants';
import { Search, ChevronDown, ChevronUp, Check, SlidersHorizontal } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from './ui/collapsible';

interface SearchFormProps {
  searchParams: SearchParams;
  setSearchParams: React.Dispatch<React.SetStateAction<SearchParams>>;
  onSubmit: (e: React.FormEvent) => void;
  selectedPlatforms: string[];
  setSelectedPlatforms: (platforms: string[]) => void;
}

export const SearchForm: React.FC<SearchFormProps> = ({
  searchParams,
  setSearchParams,
  onSubmit,
  selectedPlatforms,
  setSelectedPlatforms,
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
    <div className="w-full flex flex-col pt-12 pb-24 sm:pt-16 sm:pb-32">
      {/* Editorial Hero: Left-aligned, Brian Lovin calm style */}
      <div className="mb-12 text-left">
        <h1 className="text-display mb-4 max-w-3xl">
          Find the signal behind the noise.
        </h1>
        <p className="text-lead max-w-2xl leading-relaxed text-[var(--ink-muted)]">
          Search public applicant tracking systems directly for fresh software and engineering postings.
          No aggregators, no ghost jobs.
        </p>
      </div>

      {/* Main Search Form: Open, airy, borderless form with generous breathing room */}
      <div className="w-full max-w-3xl mb-20">
        <form onSubmit={onSubmit} className="flex flex-col gap-8">
          {/* Primary Field: Role or keyword */}
          <div className="flex flex-col gap-2.5">
            <label
              htmlFor="keywords-input"
              className="text-small font-medium text-[var(--ink)]"
            >
              Role or keyword
            </label>
            <div className="relative flex items-center">
              <Search
                className="absolute left-4 size-5 text-[var(--ink-muted)] pointer-events-none"
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
                className="h-14 !pl-12 !pr-4 text-base sm:text-lg text-[var(--ink)] placeholder:text-[var(--ink-subtle)] border-[var(--border-strong)] bg-[var(--surface)] focus-visible:border-[var(--accent)] shadow-none"
              />
            </div>

            {/* Suggestions: Quiet inline text buttons with generous wrapping and padding */}
            <div className="flex flex-wrap items-center gap-2 pt-2 text-small text-[var(--ink-muted)]">
              <span className="mr-1 text-[var(--ink-subtle)]">Try:</span>
              {ROLE_SUGGESTIONS.map((role) => (
                <button
                  key={role}
                  type="button"
                  onClick={() => setSearchParams({ ...searchParams, keywords: role })}
                  className="px-3 py-1 text-small bg-transparent hover:bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink)] transition-colors cursor-pointer select-none"
                >
                  {role}
                </button>
              ))}
            </div>
          </div>

          {/* Secondary Row: Location and Work Model side-by-side with generous gap */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="flex flex-col gap-2">
              <label
                htmlFor="location-input"
                className="text-small font-medium text-[var(--ink)]"
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
                className="h-11 px-3.5 text-base text-[var(--ink)] placeholder:text-[var(--ink-subtle)] border-[var(--border)] bg-[var(--surface)] focus-visible:border-[var(--accent)] shadow-none"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label
                htmlFor="work-model-select"
                className="text-small font-medium text-[var(--ink)]"
              >
                Work model
              </label>
              <select
                id="work-model-select"
                name="workModel"
                aria-label="Work model"
                value={searchParams.workModel}
                onChange={(e) =>
                  setSearchParams({ ...searchParams, workModel: e.target.value })
                }
                className="h-11 w-full px-3.5 text-base bg-[var(--surface)] border border-[var(--border)] text-[var(--ink)] outline-none focus-visible:border-[var(--accent)] focus-visible:ring-2 focus-visible:ring-[var(--accent)] cursor-pointer"
              >
                <option value="any">Any work model</option>
                <option value="remote">Remote only</option>
                <option value="onsite">Exclude remote (In-person / Hybrid)</option>
              </select>
            </div>
          </div>

          {/* More Filters Disclosure */}
          <Collapsible open={showMoreFilters} onOpenChange={setShowMoreFilters}>
            <div className="flex items-center justify-between pt-1">
              <CollapsibleTrigger
                aria-label="More filters"
                className="flex items-center gap-2.5 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-[var(--border)] px-3.5 h-9 text-small font-medium transition-colors cursor-pointer select-none"
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

            <CollapsibleContent className="p-6 bg-[var(--surface)] border border-[var(--border)] mt-4 flex flex-col gap-6">
              {/* Recency and Nigerian boards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div className="flex flex-col gap-2">
                  <label htmlFor="post-age-select" className="text-small font-medium text-[var(--ink)]">
                    Posted within
                  </label>
                  <select
                    id="post-age-select"
                    name="postAge"
                    value={searchParams.postAge}
                    onChange={(e) =>
                      setSearchParams({ ...searchParams, postAge: e.target.value })
                    }
                    className="h-10 w-full px-3 text-small bg-transparent border border-[var(--border)] text-[var(--ink)] outline-none focus-visible:border-[var(--accent)] cursor-pointer"
                  >
                    <option value="1">Past 24 hours</option>
                    <option value="3">Past 3 days</option>
                    <option value="7">Past 7 days (default)</option>
                    <option value="14">Past 14 days</option>
                    <option value="30">Past 30 days</option>
                  </select>
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
                    <span className="text-small text-[var(--ink)]">
                      Include Nigerian boards (Jobberman, MyJobMag)
                    </span>
                  </label>
                </div>
              </div>

              {/* Platforms Multi-selection */}
              <div className="flex flex-col gap-3 pt-3 border-t border-[var(--border-subtle)]">
                <div className="flex items-center justify-between">
                  <span className="text-small font-medium text-[var(--ink)]">
                    Target ATS platforms ({selectedPlatforms.length} of {ALL_PLATFORMS.length} selected)
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={selectAllPlatforms}
                      className="text-caption text-[var(--accent)] hover:underline"
                    >
                      Select all
                    </button>
                    <span className="text-[var(--border-strong)]">·</span>
                    <button
                      type="button"
                      onClick={selectNonePlatforms}
                      className="text-caption text-[var(--ink-muted)] hover:underline"
                    >
                      Select none
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
                  {ALL_PLATFORMS.map((platform) => {
                    const isSelected = selectedPlatforms.includes(platform.id);
                    return (
                      <button
                        key={platform.id}
                        type="button"
                        onClick={() => togglePlatform(platform.id)}
                        className={`flex items-center justify-between px-3 py-2 text-small border transition-colors text-left ${
                          isSelected
                            ? 'border-[var(--accent)] bg-[var(--accent-tint)] text-[var(--ink)] font-medium'
                            : 'border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] hover:bg-[var(--surface-hover)]'
                        }`}
                      >
                        <span>{platform.name}</span>
                        {isSelected && <Check className="size-3.5 text-[var(--accent)]" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* Form Actions: Primary Search Button with clear spacing */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 pt-4">
            <span className="text-small text-[var(--ink-subtle)] hidden sm:inline">
              Press Enter or click Search to stream verified results
            </span>
            <Button
              type="submit"
              className="w-full sm:w-auto h-12 px-8 font-medium text-base transition-opacity hover:opacity-95 cursor-pointer ml-auto"
              style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
            >
              <Search className="size-4.5 mr-2" style={{ color: '#FFFFFF' }} aria-hidden="true" />
              <span style={{ color: '#FFFFFF' }}>Search ATS platforms</span>
            </Button>
          </div>
        </form>
      </div>

      {/* How Bottom Pot Works: 3-item spacious list (Brian Lovin style) */}
      <div className="w-full mb-20 text-left border-t border-[var(--border)] pt-16">
        <h2 className="text-title mb-8 font-semibold text-[var(--ink)]">How Bottom Pot works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10 lg:gap-14">
          <div className="flex flex-col gap-2">
            <h3 className="text-body font-semibold text-[var(--ink)]">
              Direct ATS querying
            </h3>
            <p className="text-small text-[var(--ink-muted)] leading-relaxed">
              Searches primary company career boards (Greenhouse, Lever, Ashby, Workable) directly without aggregators.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <h3 className="text-body font-semibold text-[var(--ink)]">
              Verified postings only
            </h3>
            <p className="text-small text-[var(--ink-muted)] leading-relaxed">
              Every listing connects to a canonical ATS application link. Expired and phantom postings are omitted.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <h3 className="text-body font-semibold text-[var(--ink)]">
              Transparent metadata
            </h3>
            <p className="text-small text-[var(--ink-muted)] leading-relaxed">
              Strict classification for remote, hybrid, and on-site roles with source evidence and exact timestamps.
            </p>
          </div>
        </div>
      </div>

      {/* Supported Platforms Line */}
      <div className="w-full pt-8 border-t border-[var(--border-subtle)] text-left">
        <p className="text-caption text-[var(--ink-subtle)]">
          Supported platforms: Greenhouse · Lever · Ashby · Workable · Recruitee · BambooHR · SmartRecruiters · Jobberman · MyJobMag
        </p>
      </div>
    </div>
  );
};
