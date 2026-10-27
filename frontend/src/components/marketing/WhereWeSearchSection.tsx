import React from 'react';
import { ALL_PLATFORMS } from '../../lib/constants';

interface WhereWeSearchSectionProps {
  onSearchPlatforms?: (platformIds: string[]) => void;
}

// Generate short 2-character monogram for each platform
function getMonogram(name: string): string {
  const clean = name.replace(/\(NG\)/g, '').trim();
  const parts = clean.split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return clean.slice(0, 2).toUpperCase();
}

export const WhereWeSearchSection: React.FC<WhereWeSearchSectionProps> = ({
  onSearchPlatforms,
}) => {
  // Highlighted platforms from prompt: Greenhouse, Lever, Ashby, Workable
  const namedGlobalIds = ['greenhouse', 'lever', 'ashby', 'workable'];
  // Nigerian platforms
  const nigerianPlatformIds = ['jobberman', 'myjobmag'];

  // Dynamically derive N (platforms beyond the 4 named global and 2 Nigerian boards)
  const remainingPlatformsCount = ALL_PLATFORMS.filter(
    (p) => !namedGlobalIds.includes(p.id) && !nigerianPlatformIds.includes(p.id)
  ).length;

  return (
    <section id="where-we-search" className="py-20 sm:py-28 bg-[var(--bg)] border-b border-[var(--border)]">
      <div className="page-shell">
        {/* Section Intro */}
        <div className="max-w-2xl mb-12 sm:mb-16">
          <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[var(--ink)]">
            Where we search.
          </h2>
          <p className="text-sm sm:text-base text-[var(--ink-muted)] mt-2 font-sans leading-relaxed">
            Greenhouse, Lever, Ashby, Workable and {remainingPlatformsCount} more hiring platforms, plus Nigerian job boards.
          </p>
        </div>

        {/* Platform Grid: Plain text and monograms only, no URL patterns, no fidelity tiers, no selector controls */}
        <div className="border border-[var(--border)] bg-[var(--surface)] grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 divide-x divide-y divide-[var(--border)]">
          {ALL_PLATFORMS.map((platform) => {
            const monogram = getMonogram(platform.name);
            const isNigerian = nigerianPlatformIds.includes(platform.id) || platform.name.includes('(NG)');

            return (
              <div
                key={platform.id}
                onClick={() => onSearchPlatforms?.([platform.id])}
                className="p-4 sm:p-5 flex items-center gap-3 hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none group"
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSearchPlatforms?.([platform.id]);
                  }
                }}
                aria-label={`Search roles on ${platform.name}`}
              >
                {/* Clean square monogram */}
                <span className="w-7 h-7 shrink-0 border border-[var(--border)] bg-[var(--surface-raised)] text-[var(--ink-muted)] group-hover:text-[var(--ink)] group-hover:border-[var(--border-strong)] font-mono text-[11px] font-medium flex items-center justify-center transition-colors">
                  {monogram}
                </span>

                <div className="min-w-0">
                  <div className="text-xs sm:text-sm font-medium text-[var(--ink)] truncate">
                    {platform.name.replace(' (NG)', '')}
                  </div>
                  {isNigerian && (
                    <div className="text-[10px] font-mono text-[var(--ink-subtle)]">
                      Nigeria
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
