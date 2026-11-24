import React from 'react';
import { ArrowRight } from 'lucide-react';
import { ALL_PLATFORMS, type PlatformCategory } from '../lib/constants';
import { routeToPath, type AppRoute } from '../lib/router';

interface HomePageProps {
  onNavigate: (route: AppRoute) => void;
  onStartNewSearch?: () => void;
}

const SOURCE_GROUP_META: Array<{ category: PlatformCategory; title: string; detail: string }> = [
  {
    category: 'monitored_ats',
    title: 'Direct company career pages',
    detail: 'Nine company hiring engines kept fresh so matching roles appear immediately when you search.',
  },
  {
    category: 'enterprise_ats',
    title: 'Large enterprise careers',
    detail: 'Global enterprise hiring portals checked on demand whenever your search needs wider reach.',
  },
  {
    category: 'nigerian_board',
    title: 'Nigerian job boards',
    detail: 'Three local boards cleaned up to keep real company logos, full details, and direct apply links.',
  },
];

export const HomePage: React.FC<HomePageProps> = ({ onNavigate, onStartNewSearch }) => {
  const handleLinkClick = (route: AppRoute) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    onNavigate(route);
  };

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
      {/* Calm Editorial Hero */}
      <section className="py-16 sm:py-24 border-b border-[var(--border)]">
        <div className="page-shell">
          <div className="max-w-3xl bp-fade-up">
            <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
              Jobs straight from the company.
            </h1>
            <p className="text-lead text-[var(--ink-muted)] mt-5 max-w-[58ch] leading-relaxed">
              Real openings pulled directly from company hiring pages and trusted Nigerian job boards.
              No stale re-posts, no sign-up walls, and clear country rules before you open an application.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <a
                href={routeToPath('search')}
                onClick={handleStartClick}
                className="group h-10 px-5 inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-[opacity,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none cursor-pointer select-none"
                style={{ backgroundColor: 'var(--accent)', borderRadius: 0 }}
              >
                <span>Start searching</span>
                <ArrowRight className="size-4 group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
              </a>
              <a
                href={routeToPath('product')}
                onClick={handleLinkClick('product')}
                className="h-10 px-5 inline-flex items-center text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none cursor-pointer select-none"
                style={{ borderRadius: 0 }}
              >
                How a search works
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Core Guarantees Strip */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12">
            <div className="flex flex-col gap-2 bp-fade-up bp-delay-1">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Apply at the source</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Every click takes you straight to the company’s own career page instead of sending you
                through recycled listings or third-party account prompts.
              </p>
            </div>
            <div className="flex flex-col gap-2 bp-fade-up bp-delay-2">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Know where you can apply</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Remote, hybrid, and on-site work styles stay separate from country restrictions. Pick
                where you live and filter out closed doors in one click.
              </p>
            </div>
            <div className="flex flex-col gap-2 bp-fade-up bp-delay-3">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Real dates, honest details</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Listings older than 90 days move cleanly beneath a divider. Missing salaries and vague
                work policies stay blank instead of being guessed.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Where We Search Summary */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <h2 className="text-title font-semibold text-[var(--ink)]">Where your search looks</h2>
              <p className="text-sm text-[var(--ink-muted)] mt-2 max-w-[60ch]">
                Thirteen verified hiring sources chosen for accuracy and clean application links rather
                than inflated source counts.
              </p>
            </div>
            <a
              href={routeToPath('sources')}
              onClick={handleLinkClick('sources')}
              className="group h-9 px-3.5 inline-flex items-center gap-1.5 text-sm font-medium border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] w-fit shrink-0"
              style={{ borderRadius: 0 }}
            >
              <span>Inspect all 13 sources</span>
              <ArrowRight className="size-3.5 text-[var(--ink-muted)] group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
            </a>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {SOURCE_GROUP_META.map((group) => {
              const items = ALL_PLATFORMS.filter((p) => p.category === group.category);
              return (
                <div
                  key={group.category}
                  className="border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col gap-4"
                >
                  <div className="flex flex-col gap-1.5">
                    <h3 className="text-sm font-semibold text-[var(--ink)]">
                      {group.title} ({items.length})
                    </h3>
                    <p className="text-xs text-[var(--ink-muted)] leading-relaxed">{group.detail}</p>
                  </div>
                  <div className="flex flex-wrap gap-2 pt-2 border-t border-[var(--border-subtle)]">
                    {items.map((item) => (
                      <span
                        key={item.id}
                        className="font-mono text-xs lowercase px-2 py-1 border border-[var(--border-subtle)] bg-[var(--bg)] text-[var(--ink-muted)]"
                      >
                        {item.id}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Quiet Editorial Closing Band */}
      <section className="py-14">
        <div className="page-shell flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="flex flex-col gap-1.5">
            <h2 className="text-lg font-semibold text-[var(--ink)]">Search without creating an account.</h2>
            <p className="text-sm text-[var(--ink-muted)]">
              Fast keyboard browsing, private local shortlist, and instant spreadsheet export built in.
            </p>
          </div>
          <a
            href={routeToPath('search')}
            onClick={handleStartClick}
            className="group h-10 px-5 inline-flex items-center gap-2 text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] w-fit shrink-0"
            style={{ borderRadius: 0 }}
          >
            <span>Open search workspace</span>
            <ArrowRight className="size-4 text-[var(--ink-muted)] group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
          </a>
        </div>
      </section>
    </div>
  );
};
