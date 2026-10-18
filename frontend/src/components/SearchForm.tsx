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
    <div className="w-full flex flex-col pt-8 pb-16">
      {/* Editorial Hero: Left-aligned, Brian Lovin calm style */}
      <div className="mb-10 text-left">
        <h1 className="text-display mb-3">
          Find the signal behind the noise.
        </h1>
        <p className="text-lead max-w-[62ch]">
          Search public applicant tracking systems directly for fresh software and engineering postings.
          No aggregators, no ghost jobs.
        </p>
      </div>

      {/* Main Search Form: Borderless or clean hairline panel */}
      <div className="w-full border border-[var(--border)] bg-[var(--surface)] p-6 sm:p-8 mb-16">
        <form onSubmit={onSubmit} className="flex flex-col gap-6">
          {/* Primary Field: Role or keyword */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="keywords-input"
              className="text-small font-medium text-[var(--ink)]"
            >
              Role or keyword
            </label>
            <div className="relative flex items-center">
              <Search
                className="absolute left-3 size-4 text-[var(--ink-muted)] pointer-events-none"
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
                className="pl-9 h-11 text-base text-[var(--ink)] placeholder:text-[var(--ink-subtle)] border-[var(--border-strong)] focus-visible:border-[var(--accent)]"
              />
            </div>

            {/* Suggestions: Quiet inline text buttons with balanced wrapping */}
            <div className="flex flex-wrap items-center gap-1.5 pt-1 text-caption text-[var(--ink-muted)]">
              <span className="mr-1">Try:</span>
              {ROLE_SUGGESTIONS.map((role) => (
                <button
                  key={role}
                  type="button"
                  onClick={() => setSearchParams({ ...searchParams, keywords: role })}
                  className="px-2 py-0.5 text-caption bg-[var(--surface-subtle)] hover:bg-[var(--surface-hover)] border border-[var(--border)] transition-colors cursor-pointer"
                  style={{ color: 'var(--ink)' }}
                >
                  {role}
                </button>
              ))}
            </div>
          </div>

          {/* Secondary Row: Location and Work Model side-by-side */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
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
                className="h-9 text-small text-[var(--ink)] placeholder:text-[var(--ink-subtle)] border-[var(--border)] focus-visible:border-[var(--accent)]"
              />
            </div>

            <div className="flex flex-col gap-1.5">
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
                className="h-9 w-full px-2.5 text-small bg-transparent border border-[var(--border)] text-[var(--ink)] outline-none focus-visible:border-[var(--accent)] focus-visible:ring-2 focus-visible:ring-[var(--accent)] cursor-pointer"
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
                className="flex items-center gap-2 text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] border border-[var(--border)] px-3 h-8 text-small font-medium transition-colors cursor-pointer select-none"
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

            <CollapsibleContent className="pt-4 mt-3 border-t border-[var(--border-subtle)] flex flex-col gap-5">
              {/* Recency and Nigerian boards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
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
                    className="h-9 w-full px-2.5 text-small bg-transparent border border-[var(--border)] text-[var(--ink)] outline-none focus-visible:border-[var(--accent)]"
                  >
                    <option value="1">Past 24 hours</option>
                    <option value="3">Past 3 days</option>
                    <option value="7">Past 7 days (default)</option>
                    <option value="14">Past 14 days</option>
                    <option value="30">Past 30 days</option>
                  </select>
                </div>

                <div className="flex flex-col justify-end">
                  <label className="flex items-center gap-2.5 h-9 cursor-pointer select-none">
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
              <div className="flex flex-col gap-2 pt-2 border-t border-[var(--border-subtle)]">
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

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                  {ALL_PLATFORMS.map((platform) => {
                    const isSelected = selectedPlatforms.includes(platform.id);
                    return (
                      <button
                        key={platform.id}
                        type="button"
                        onClick={() => togglePlatform(platform.id)}
                        className={`flex items-center justify-between px-2.5 py-1.5 text-small border transition-colors text-left ${
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

          {/* Form Actions: Primary Search Button */}
          <div className="flex items-center justify-between pt-2">
            <span className="text-caption text-[var(--ink-subtle)] hidden sm:inline">
              Press Enter or click Search to stream verified results
            </span>
            <Button
              type="submit"
              className="w-full sm:w-auto h-10 px-6 font-medium text-small transition-opacity hover:opacity-95 cursor-pointer ml-auto"
              style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
            >
              <Search className="size-4 mr-2" style={{ color: '#FFFFFF' }} aria-hidden="true" />
              <span style={{ color: '#FFFFFF' }}>Search ATS platforms</span>
            </Button>
          </div>
        </form>
      </div>

      {/* How Bottom Pot Works: 3-item quiet list (Brian Lovin style) */}
      <div className="w-full mb-16 text-left">
        <h2 className="text-title mb-6">How Bottom Pot works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 border-t border-[var(--border)] pt-6">
          <div className="flex flex-col gap-1.5">
            <h3 className="text-body font-semibold text-[var(--ink)]">
              Direct ATS querying
            </h3>
            <p className="text-small text-[var(--ink-muted)]">
              Searches primary company career boards (Greenhouse, Lever, Ashby, Workable) directly without aggregators.
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <h3 className="text-body font-semibold text-[var(--ink)]">
              Verified postings only
            </h3>
            <p className="text-small text-[var(--ink-muted)]">
              Every listing connects to a canonical ATS application link. Expired and phantom postings are omitted.
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <h3 className="text-body font-semibold text-[var(--ink)]">
              Transparent metadata
            </h3>
            <p className="text-small text-[var(--ink-muted)]">
              Strict classification for remote, hybrid, and on-site roles with source evidence and exact timestamps.
            </p>
          </div>
        </div>
      </div>

      {/* Supported Platforms Line */}
      <div className="w-full pt-4 border-t border-[var(--border-subtle)] text-center sm:text-left">
        <p className="text-caption text-[var(--ink-subtle)]">
          Supported platforms: Greenhouse · Lever · Ashby · Workable · Recruitee · BambooHR · SmartRecruiters · Jobberman · MyJobMag
        </p>
      </div>
    </div>
  );
};
