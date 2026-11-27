import React from 'react';
import { ArrowRight } from 'lucide-react';
import { ALL_PLATFORMS, type PlatformCategory } from '../lib/constants';
import { routeToPath, type AppRoute } from '../lib/router';

interface SourcesPageProps {
  onNavigate: (route: AppRoute) => void;
  onSearchPlatforms: (platformIds: string[]) => void;
  onStartNewSearch?: () => void;
}

const GROUPS: Array<{
  category: PlatformCategory;
  heading: string;
  subtitle: string;
  modeTag: string;
}> = [
  {
    category: 'monitored_ats',
    heading: 'Company hiring platforms',
    subtitle: 'These platforms power career pages used by employers. Supported employer boards are checked regularly, with coverage changing as boards are discovered and verified.',
    modeTag: 'updated regularly',
  },
  {
    category: 'enterprise_ats',
    heading: 'Enterprise hiring portal',
    subtitle: 'Workday-hosted listings are searched separately from the employer boards we check regularly.',
    modeTag: 'checked live',
  },
  {
    category: 'nigerian_board',
    heading: 'Selected job boards',
    subtitle: 'We also search selected job boards to bring more opportunities into the same workspace.',
    modeTag: 'selected board',
  },
];

export const SourcesPage: React.FC<SourcesPageProps> = ({
  onNavigate,
  onSearchPlatforms,
  onStartNewSearch,
}) => {
  const handleStartClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    if (onStartNewSearch) {
      onStartNewSearch();
    } else {
      onNavigate('search');
    }
  };

  return (
    <div className="w-full">
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl bp-fade-up">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Where Bottom Pot searches
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Bottom Pot searches 10 hiring platforms and 3 selected job boards. Hiring platforms host
            career pages for individual employers, so one platform can connect to many different
            companies.
          </p>
        </div>
      </section>

      <section className="py-14">
        <div className="page-shell flex flex-col gap-12">
          {GROUPS.map((group) => {
            const items = ALL_PLATFORMS.filter((p) => p.category === group.category);
            return (
              <div key={group.category} className="flex flex-col gap-5">
                <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-[var(--border)] pb-4">
                  <div>
                    <h2 className="text-title font-semibold text-[var(--ink)]">
                      {group.heading} ({items.length})
                    </h2>
                    <p className="text-sm text-[var(--ink-muted)] mt-1.5 max-w-[62ch]">
                      {group.subtitle}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onSearchPlatforms(items.map((p) => p.id))}
                    className="group h-9 px-3.5 rounded-md inline-flex items-center gap-1.5 text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer shrink-0 w-fit"
                  >
                    <span>Search this group</span>
                    <ArrowRight className="size-3.5 text-[var(--ink-muted)] group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {items.map((platform) => (
                    <div
                      key={platform.id}
                      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col justify-between gap-4"
                    >
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-[var(--ink)]">
                            {platform.name}
                          </span>
                          <span className="font-mono text-xs lowercase text-[var(--ink-subtle)]">
                            {platform.id}
                          </span>
                        </div>
                        <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
                          {platform.description}
                        </p>
                      </div>

                      <div className="flex items-center justify-between pt-3 border-t border-[var(--border-subtle)]">
                        <span className="font-mono text-[11px] lowercase text-[var(--ink-subtle)]">
                          {group.modeTag}
                        </span>
                        <button
                          type="button"
                          onClick={() => onSearchPlatforms([platform.id])}
                          className="h-8 px-3 rounded-md inline-flex items-center text-xs font-medium border border-[var(--border)] bg-[var(--bg)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
                        >
                          Search {platform.name}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}

          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-subtle)] p-5 text-sm text-[var(--ink-muted)] leading-relaxed">
            The number of hiring platforms is not the same as the number of employer career boards.
            We add supported employer boards as they are discovered and verified. Coverage and
            source availability can change over time.
          </div>

          <div className="pt-8 border-t border-[var(--border)] flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-[var(--ink-muted)]">
              Ready to search across these sources?
            </p>
            <a
              href={routeToPath('search')}
              onClick={handleStartClick}
              className="group h-10 px-5 rounded-md inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-[opacity,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
              style={{ backgroundColor: 'var(--accent)' }}
            >
              <span>Search jobs</span>
              <ArrowRight className="size-4 group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
