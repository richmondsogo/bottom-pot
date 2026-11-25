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
    title: 'Company career pages',
    detail: 'Nine hiring platforms refreshed regularly so open roles show up fast.',
  },
  {
    category: 'enterprise_ats',
    title: 'Enterprise career portals',
    detail: 'Large global employers checked live when your search needs wider reach.',
  },
  {
    category: 'nigerian_board',
    title: 'Nigerian job boards',
    detail: 'Three local boards cleaned up with full descriptions, company logos, and direct apply links.',
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
              Find live jobs you can actually apply to.
            </h1>
            <p className="text-lead text-[var(--ink-muted)] mt-5 max-w-[58ch] leading-relaxed">
              Search 13 company hiring boards and Nigerian job sites in one place. Every listing
              links straight to the employer&apos;s application page, with real posting dates and
              clear country eligibility.
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
                How it works
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
              <h2 className="text-sm font-semibold text-[var(--ink)]">Apply on the company&apos;s own site</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Every link goes straight to the employer&apos;s career page. You skip middleman
                portals and extra sign-up forms.
              </p>
            </div>
            <div className="flex flex-col gap-2 bp-fade-up bp-delay-2">
              <h2 className="text-sm font-semibold text-[var(--ink)]">See if your country qualifies first</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Pick where you can work from before you open a listing. Remote work style stays
                separate from country restrictions, so you spot closed doors immediately.
              </p>
            </div>
            <div className="flex flex-col gap-2 bp-fade-up bp-delay-3">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Real dates and honest blanks</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Roles from the last 90 days stay at the top, and older postings sit beneath a divider.
                Missing salaries stay blank instead of showing guesses.
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
                13 sources picked for direct apply links and accurate dates.
              </p>
            </div>
            <a
              href={routeToPath('sources')}
              onClick={handleLinkClick('sources')}
              className="group h-9 px-3.5 inline-flex items-center gap-1.5 text-sm font-medium border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] w-fit shrink-0"
              style={{ borderRadius: 0 }}
            >
              <span>See all 13 sources</span>
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
            <h2 className="text-lg font-semibold text-[var(--ink)]">Start searching without an account.</h2>
            <p className="text-sm text-[var(--ink-muted)]">
              Save roles to a private shortlist, browse by keyboard, and export to CSV or JSON in one click.
            </p>
          </div>
          <a
            href={routeToPath('search')}
            onClick={handleStartClick}
            className="group h-10 px-5 inline-flex items-center gap-2 text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] w-fit shrink-0"
            style={{ borderRadius: 0 }}
          >
            <span>Open search</span>
            <ArrowRight className="size-4 text-[var(--ink-muted)] group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
          </a>
        </div>
      </section>
    </div>
  );
};
