import React from 'react';
import { MarketingHeader } from './MarketingHeader';
import { HeroSection } from './HeroSection';
import { HeroInteractiveStage } from './HeroInteractiveStage';
import { SignalMetricsStrip } from './SignalMetricsStrip';
import { BentoFeatureGrid } from './BentoFeatureGrid';
import { AtsPlatformMatrix } from './AtsPlatformMatrix';
import { EditorialManifesto } from './EditorialManifesto';

interface MarketingLandingProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onLaunchWorkspace: () => void;
  onLaunchMock: () => void;
  onQuickSearch: (query: string, workModel?: 'any' | 'remote' | 'hybrid' | 'in_person', location?: string) => void;
  onSearchPlatforms: (platformIds: string[]) => void;
  onOpenCommand: () => void;
}

export const MarketingLanding: React.FC<MarketingLandingProps> = ({
  theme,
  onToggleTheme,
  onLaunchWorkspace,
  onLaunchMock,
  onQuickSearch,
  onSearchPlatforms,
  onOpenCommand,
}) => {
  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg)] text-[var(--ink)]">
      {/* 1. Architectural Header */}
      <MarketingHeader
        theme={theme}
        onToggleTheme={onToggleTheme}
        onOpenCommand={onOpenCommand}
        onLaunchWorkspace={onLaunchWorkspace}
      />

      {/* 2. Hero Section with Headline, Lead, CTAs & Quick Search */}
      <HeroSection
        onLaunchWorkspace={onLaunchWorkspace}
        onLaunchMock={onLaunchMock}
        onQuickSearch={onQuickSearch}
      />

      {/* 3. Midday Signature Tabbed Interactive Product Stage */}
      <HeroInteractiveStage
        onOpenWorkspace={onLaunchWorkspace}
        onOpenCommand={onOpenCommand}
      />

      {/* 4. 4-Column Proof & Metrics Strip */}
      <SignalMetricsStrip />

      {/* 5. 2x2 Architectural Bento Feature Grid with Live Micro-UIs */}
      <BentoFeatureGrid />

      {/* 6. 18+ ATS Coverage Matrix Grid */}
      <AtsPlatformMatrix
        onSearchPlatforms={onSearchPlatforms}
      />

      {/* 7. Editorial Manifesto & Full-Width Footer CTA */}
      <EditorialManifesto
        onLaunchWorkspace={onLaunchWorkspace}
        onLaunchMock={onLaunchMock}
      />
    </div>
  );
};
