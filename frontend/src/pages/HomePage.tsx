import React from 'react';
import { ArrowRight } from 'lucide-react';
import { ALL_PLATFORMS, type PlatformCategory } from '../lib/constants';
import { routeToPath, type AppRoute } from '../lib/router';

interface HomePageProps {
  onNavigate: (route: AppRoute) => void;
}

const SOURCE_GROUP_META: Array<{ category: PlatformCategory; title: string; detail: string }> = [
  {
    category: 'monitored_ats',
    title: 'Monitored ATS boards',
    detail: 'Nine public hiring engines polled on a schedule and matched locally before live queries run.',
  },
  {
    category: 'enterprise_ats',
    title: 'Enterprise ATS fallback',
    detail: 'Large Workday career tenants queried on demand when monitored matches are sparse.',
  },
  {
    category: 'nigerian_board',
    title: 'Nigerian job boards',
    detail: 'Three local boards parsed for verified descriptions, external apply links, and company marks.',
  },
];

export const HomePage: React.FC<HomePageProps> = ({ onNavigate }) => {
  const handleLinkClick = (route: AppRoute) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    onNavigate(route);
  };

  return (
    <div className="w-full">
      {/* Calm Editorial Hero */}
      <section className="py-16 sm:py-24 border-b border-[var(--border)]">
        <div className="page-shell">
          <div className="max-w-3xl">
            <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
              Jobs straight from the company.
            </h1>
            <p className="text-lead text-[var(--ink-muted)] mt-5 max-w-[58ch] leading-relaxed">
              Real openings from company career pages and verified Nigerian job boards.
              Monitored company boards answer first, work arrangement stays separate from country rules,
              and unknown fields stay blank instead of guessed.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <a
                href={routeToPath('search')}
                onClick={handleLinkClick('search')}
                className="h-10 px-5 inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-opacity cursor-pointer select-none"
                style={{ backgroundColor: 'var(--accent)', borderRadius: 0 }}
              >
                <span>Start searching</span>
                <ArrowRight className="size-4" aria-hidden="true" />
              </a>
              <a
                href={routeToPath('product')}
                onClick={handleLinkClick('product')}
                className="h-10 px-5 inline-flex items-center text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
                style={{ borderRadius: 0 }}
              >
                Read how it works
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Core Guarantees Strip */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12">
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Direct employer links</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Every role resolves to the company career page or primary application destination rather
                than looping you through scraper syndication chains.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Honest work &amp; country rules</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Remote, hybrid, and on-site labels are kept distinct from country eligibility, which is
                checked explicitly for the country you pick.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Freshness without guesswork</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Stale listings drop below recent roles behind a clear divider. Missing compensation or
                ambiguous arrangements remain cleanly blank.
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
              <h2 className="text-title font-semibold text-[var(--ink)]">Where we search</h2>
              <p className="text-sm text-[var(--ink-muted)] mt-2 max-w-[60ch]">
                Ten active applicant tracking engines and three Nigerian boards, chosen for structured
                data quality rather than inflated source counts.
              </p>
            </div>
            <a
              href={routeToPath('sources')}
              onClick={handleLinkClick('sources')}
              className="h-9 px-3.5 inline-flex items-center gap-1.5 text-sm font-medium border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors w-fit shrink-0"
              style={{ borderRadius: 0 }}
            >
              <span>Inspect all 13 sources</span>
              <ArrowRight className="size-3.5 text-[var(--ink-muted)]" aria-hidden="true" />
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
            <h2 className="text-lg font-semibold text-[var(--ink)]">Ready to filter direct openings?</h2>
            <p className="text-sm text-[var(--ink-muted)]">
              No sign-up wall, no saved-search emails unless you ask, keyboard navigation built in.
            </p>
          </div>
          <a
            href={routeToPath('search')}
            onClick={handleLinkClick('search')}
            className="h-10 px-5 inline-flex items-center gap-2 text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors w-fit shrink-0"
            style={{ borderRadius: 0 }}
          >
            <span>Open search workspace</span>
            <ArrowRight className="size-4 text-[var(--ink-muted)]" aria-hidden="true" />
          </a>
        </div>
      </section>
    </div>
  );
};
