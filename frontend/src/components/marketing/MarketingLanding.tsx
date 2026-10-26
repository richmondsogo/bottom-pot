import React, { useState } from 'react';
import type { SearchParams } from '../../types';
import type { RecentSearchPreset } from '../../lib/urlState';
import { ALL_PLATFORMS } from '../../lib/constants';
import { HeroPortalSection } from './HeroPortalSection';
import { SampleResultsSection } from './SampleResultsSection';
import { WhyDifferentSection } from './WhyDifferentSection';
import { WhereWeSearchSection } from './WhereWeSearchSection';
import { EditorialManifesto } from './EditorialManifesto';

export interface MarketingLandingProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onLaunchWorkspace: () => void;
  onLaunchMock?: () => void;
  onQuickSearch: (query: string, workModel?: 'any' | 'remote' | 'hybrid' | 'in_person', location?: string) => void;
  onSearchPlatforms: (platformIds: string[]) => void;
  onOpenCommand: () => void;
  searchParams?: SearchParams;
  setSearchParams?: React.Dispatch<React.SetStateAction<SearchParams>>;
  selectedPlatforms?: string[];
  setSelectedPlatforms?: (platforms: string[]) => void;
  onSubmit?: (e: React.FormEvent) => void;
  recentSearches?: RecentSearchPreset[];
  onSelectRecentSearch?: (preset: RecentSearchPreset) => void;
}

export const MarketingLanding: React.FC<MarketingLandingProps> = ({
  theme,
  onToggleTheme,
  onLaunchWorkspace,
  onQuickSearch,
  onSearchPlatforms,
  searchParams: externalSearchParams,
  setSearchParams: externalSetSearchParams,
  selectedPlatforms: externalSelectedPlatforms,
  setSelectedPlatforms: externalSetSelectedPlatforms,
  onSubmit: externalOnSubmit,
  recentSearches = [],
  onSelectRecentSearch,
}) => {
  // Local fallback state if not passed from parent
  const [internalSearchParams, setInternalSearchParams] = useState<SearchParams>({
    keywords: '',
    location: '',
    workModel: 'any',
    postAge: '7',
    includeNigerian: true,
    deepScrape: false,
  });

  const [internalSelectedPlatforms, setInternalSelectedPlatforms] = useState<string[]>(
    () => ALL_PLATFORMS.map((p) => p.id)
  );

  const searchParams = externalSearchParams ?? internalSearchParams;
  const setSearchParams = externalSetSearchParams ?? setInternalSearchParams;
  const selectedPlatforms = externalSelectedPlatforms ?? internalSelectedPlatforms;
  const setSelectedPlatforms = externalSetSelectedPlatforms ?? setInternalSelectedPlatforms;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (externalOnSubmit) {
      externalOnSubmit(e);
    } else {
      onLaunchWorkspace();
    }
  };


  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg)] text-[var(--ink)]">
      {/* 1. New Hero Using Glyph Portal (Wordmark zoom, opening frame with logo & links, revealed search form) */}
      <HeroPortalSection
        theme={theme}
        onToggleTheme={onToggleTheme}
        searchParams={searchParams}
        setSearchParams={setSearchParams}
        onSubmit={handleSubmit}
        selectedPlatforms={selectedPlatforms}
        setSelectedPlatforms={setSelectedPlatforms}
        onQuickSearch={onQuickSearch}
        recentSearches={recentSearches}
        onSelectRecentSearch={onSelectRecentSearch}
      />

      {/* 2. Example Table Intro ("Here's what a search looks like") */}
      <SampleResultsSection />

      {/* 3. Why It's Different (Three plain columns, hairline-separated, no cards) */}
      <WhyDifferentSection />

      {/* 4. Where We Search (Derived platform count, clean monogram grid) */}
      <WhereWeSearchSection onSearchPlatforms={onSearchPlatforms} />

      {/* 5. Editorial Manifesto, Final CTA ("Start searching") & Calm Footer */}
      <EditorialManifesto
        onStartSearching={onLaunchWorkspace}
        onTryExample={() => onQuickSearch('React engineer', 'remote', '')}
      />
    </div>
  );
};
