import React from 'react';
import { ArrowRight } from 'lucide-react';
import { ALL_PLATFORMS, type PlatformCategory } from '../lib/constants';
import { routeToPath, type AppRoute } from '../lib/router';

interface SourcesPageProps {
  onNavigate: (route: AppRoute) => void;
  onSearchPlatforms: (platformIds: string[]) => void;
}

const GROUPS: Array<{
  category: PlatformCategory;
  heading: string;
  subtitle: string;
  modeTag: string;
}> = [
  {
    category: 'monitored_ats',
    heading: 'Monitored ATS platforms (9)',
    subtitle: 'Public company career boards polled periodically via native JSON/XML/HTML adapters and checked directly during search.',
    modeTag: 'monitored + fallback',
  },
  {
    category: 'enterprise_ats',
    heading: 'Enterprise ATS fallback (1)',
    subtitle: 'Workday career tenants surfaced via web search fallback when monitored ATS results need broader reach.',
    modeTag: 'on-demand fallback',
  },
  {
    category: 'nigerian_board',
    heading: 'Nigerian job boards (3)',
    subtitle: 'Scraped directly in parallel, with detail-page enrichment resolving ATS links, corporate mailto domains, and verified employer marks.',
    modeTag: 'direct scrape',
  },
];

export const SourcesPage: React.FC<SourcesPageProps> = ({ onNavigate, onSearchPlatforms }) => {
  const handleLinkClick = (route: AppRoute) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    onNavigate(route);
  };

  return (
    <div className="w-full">
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Thirteen verified sources.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Nine monitored ATS engines, Workday fallback discovery, and three Nigerian boards. Eight
            near-zero-yield legacy ATS hosts were retired instead of inflating platform counts.
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
                    <h2 className="text-title font-semibold text-[var(--ink)]">{group.heading}</h2>
                    <p className="text-sm text-[var(--ink-muted)] mt-1.5 max-w-[62ch]">
                      {group.subtitle}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onSearchPlatforms(items.map((p) => p.id))}
                    className="h-9 px-3.5 inline-flex items-center gap-1.5 text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer shrink-0 w-fit"
                    style={{ borderRadius: 0 }}
                  >
                    <span>Search this group</span>
                    <ArrowRight className="size-3.5 text-[var(--ink-muted)]" aria-hidden="true" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {items.map((platform) => (
                    <div
                      key={platform.id}
                      className="border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col justify-between gap-4"
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
                          className="h-8 px-3 inline-flex items-center text-xs font-medium border border-[var(--border)] bg-[var(--bg)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer"
                          style={{ borderRadius: 0 }}
                        >
                          Search {platform.id}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}

          <div className="pt-8 border-t border-[var(--border)] flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-[var(--ink-muted)]">
              Want to inspect everything together or toggle individual boards in the drawer?
            </p>
            <a
              href={routeToPath('search')}
              onClick={handleLinkClick('search')}
              className="h-10 px-5 inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-opacity cursor-pointer"
              style={{ backgroundColor: 'var(--accent)', borderRadius: 0 }}
            >
              <span>Start searching</span>
              <ArrowRight className="size-4" aria-hidden="true" />
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
