import React from 'react';
import type { SearchParams } from '../../types';
import type { RecentSearchPreset } from '../../lib/urlState';
import { HeroPortalSection } from './HeroPortalSection';
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
  onOpenCommand?: () => void;
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
}) => {
  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg)] text-[var(--ink)]">
      {/* 1. Hero Using Glyph Portal (Wordmark zoom, opening frame with logo & links, revealed search CTA) */}
      <HeroPortalSection
        theme={theme}
        onToggleTheme={onToggleTheme}
        onStartSearching={onLaunchWorkspace}
        onQuickSearch={onQuickSearch}
      />

      {/* 2. Why It's Different (Three plain columns, hairline-separated, no cards) */}
      <WhyDifferentSection />

      {/* 3. Where We Search (Derived platform count, clean monogram grid) */}
      <WhereWeSearchSection onSearchPlatforms={onSearchPlatforms} />

      {/* 4. Editorial Manifesto, Final CTA ("Start searching") & Calm Footer */}
      <EditorialManifesto
        onStartSearching={onLaunchWorkspace}
        onTryExample={() => onQuickSearch('React engineer', 'remote', '')}
      />
    </div>
  );
};
