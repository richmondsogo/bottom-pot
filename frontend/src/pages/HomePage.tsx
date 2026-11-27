import React from 'react';
import { ArrowRight } from 'lucide-react';
import { ALL_PLATFORMS, type PlatformCategory } from '../lib/constants';
import { routeToPath, type AppRoute } from '../lib/router';
import { SearchForm } from '../components/SearchForm';
import type { SearchParams } from '../types';

interface HomePageProps {
  onNavigate: (route: AppRoute) => void;
  onStartNewSearch?: () => void;
  searchParams?: SearchParams;
  setSearchParams?: React.Dispatch<React.SetStateAction<SearchParams>>;
  onSearchSubmit?: (e: React.FormEvent) => void;
  selectedPlatforms?: string[];
  setSelectedPlatforms?: (platforms: string[]) => void;
  applicantCountry?: string;
  onChangeApplicantCountry?: (code: string) => void;
  savedCount?: number;
  onOpenSavedShortlist?: () => void;
}

const DEFAULT_SEARCH_PARAMS: SearchParams = {
  keywords: '',
  location: '',
  workModel: 'any',
  postAge: '7',
};
const DEFAULT_PLATFORMS = ALL_PLATFORMS.map((p) => p.id);
const NOOP = () => {};
const NOOP_SUBMIT = (e: React.FormEvent) => {
  e.preventDefault();
};

const SOURCE_GROUP_META: Array<{ category: PlatformCategory; title: string; detail: string }> = [
  {
    category: 'monitored_ats',
    title: 'Company hiring platforms',
    detail: 'These platforms power career pages used by employers. Supported employer boards are checked regularly, with coverage changing as boards are discovered and verified.',
  },
  {
    category: 'enterprise_ats',
    title: 'Enterprise hiring portal',
    detail: 'Workday-hosted listings are searched separately from the employer boards we check regularly.',
  },
  {
    category: 'nigerian_board',
    title: 'Selected job boards',
    detail: 'We also search selected job boards to bring more opportunities into the same workspace.',
  },
];

export const HomePage: React.FC<HomePageProps> = ({
  onNavigate,
  onStartNewSearch,
  searchParams,
  setSearchParams,
  onSearchSubmit,
  selectedPlatforms,
  setSelectedPlatforms,
  applicantCountry = '',
  onChangeApplicantCountry,
  savedCount = 0,
  onOpenSavedShortlist,
}) => {
  const effectiveSearchParams = searchParams ?? DEFAULT_SEARCH_PARAMS;
  const effectiveSetSearchParams = setSearchParams ?? NOOP;
  const effectiveOnSubmit = onSearchSubmit ?? NOOP_SUBMIT;
  const effectiveSelectedPlatforms = selectedPlatforms ?? DEFAULT_PLATFORMS;
  const effectiveSetSelectedPlatforms = setSelectedPlatforms ?? NOOP;

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
      <section className="pt-8 pb-14 sm:pt-12 sm:pb-16 md:py-20 border-b border-[var(--border)]">
        <div className="page-shell">
          <div className="max-w-[760px] mx-auto flex flex-col items-start md:items-center text-left md:text-center bp-fade-up">
            <h1 className="text-display max-md:!text-[1.75rem] max-md:!leading-[1.18] font-semibold tracking-tight text-[var(--ink)] text-balance">
              Find jobs you can actually apply to.
            </h1>
            <p className="text-lead max-md:!text-[15px] max-md:!leading-[1.6] text-[var(--ink-muted)] mt-3 md:mt-5 max-w-[58ch] md:mx-auto leading-relaxed">
              Search company career pages and selected job boards in one place. Check the work
              setup and whether your country appears eligible before opening the original listing.
            </p>
            <div className="mt-6 md:mt-8 w-full text-left">
              <SearchForm
                variant="embedded"
                autoFocus={false}
                searchParams={effectiveSearchParams}
                setSearchParams={effectiveSetSearchParams}
                onSubmit={effectiveOnSubmit}
                selectedPlatforms={effectiveSelectedPlatforms}
                setSelectedPlatforms={effectiveSetSelectedPlatforms}
                applicantCountry={applicantCountry}
                onChangeApplicantCountry={onChangeApplicantCountry}
                savedCount={savedCount}
                onOpenSavedShortlist={onOpenSavedShortlist}
              />
            </div>
            <div className="mt-5 md:mt-5 flex justify-start md:justify-center w-full">
              <a
                href={routeToPath('product')}
                onClick={handleLinkClick('product')}
                className="group inline-flex items-center gap-1.5 text-sm font-medium text-[var(--ink-muted)] hover:text-[var(--ink)] underline underline-offset-4 decoration-[var(--border-strong)] hover:decoration-[var(--ink)] transition-colors cursor-pointer select-none"
              >
                <span>How it works</span>
                <ArrowRight className="size-3.5 group-hover:translate-x-0.5 transition-transform duration-140 ease-out motion-reduce:transform-none" aria-hidden="true" />
              </a>
            </div>
            <p className="mt-2.5 text-xs text-[var(--ink-subtle)] w-full text-left md:text-center">
              No account needed. Save jobs and organise your shortlist in your browser.
            </p>
          </div>
        </div>
      </section>

      {/* Core Guarantees Strip */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12">
            <div className="flex flex-col gap-2 bp-fade-up bp-delay-1">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Search with a purpose</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Start with a role, skill or keyword. Narrow the results with the filters that matter
                to you.
              </p>
            </div>
            <div className="flex flex-col gap-2 bp-fade-up bp-delay-2">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Know where you stand</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Remote does not always mean worldwide. Check the listed work arrangement and see
                whether the available information indicates that your country is eligible.
              </p>
            </div>
            <div className="flex flex-col gap-2 bp-fade-up bp-delay-3">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Go to the original listing</h2>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Review the details available in Bottom Pot, then continue to the employer&apos;s
                original job listing or application page.
              </p>
            </div>
          </div>
          <p className="mt-8 pt-6 border-t border-[var(--border-subtle)] text-xs text-[var(--ink-muted)] leading-relaxed">
            Posting dates and salary details appear when available. Missing information is left
            unknown, not guessed.
          </p>
        </div>
      </section>

      {/* Where We Search Summary */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <h2 className="text-title font-semibold text-[var(--ink)]">
                More places to search. One focused workspace.
              </h2>
              <p className="text-sm text-[var(--ink-muted)] mt-2 max-w-[60ch]">
                Search company career pages and selected job boards together, without moving between
                sites.
              </p>
            </div>
            <a
              href={routeToPath('sources')}
              onClick={handleLinkClick('sources')}
              className="group h-9 max-md:h-11 px-3.5 rounded-md inline-flex items-center gap-1.5 text-sm font-medium border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none w-fit shrink-0"
            >
              <span>Explore our sources</span>
              <ArrowRight className="size-3.5 text-[var(--ink-muted)] group-hover:translate-x-0.5 transition-transform duration-140 ease-out motion-reduce:transform-none" aria-hidden="true" />
            </a>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {SOURCE_GROUP_META.map((group) => {
              const items = ALL_PLATFORMS.filter((p) => p.category === group.category);
              return (
                <div
                  key={group.category}
                  className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col gap-4"
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
                        className="font-mono text-xs lowercase px-2 py-1 rounded-sm border border-[var(--border-subtle)] bg-[var(--bg)] text-[var(--ink-muted)]"
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
            <h2 className="text-lg font-semibold text-[var(--ink)]">Make your next search count.</h2>
            <p className="text-sm text-[var(--ink-muted)]">
              Find opportunities worth a closer look, review the details and keep the ones you want
              to follow up on.
            </p>
            <p className="text-xs text-[var(--ink-subtle)] mt-1">
              Free to use. No account required.
            </p>
          </div>
          <a
            href={routeToPath('search')}
            onClick={handleStartClick}
            className="group h-10 max-md:h-11 px-5 rounded-md inline-flex items-center gap-2 text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] motion-reduce:transform-none w-fit shrink-0"
          >
            <span>Search jobs</span>
            <ArrowRight className="size-4 text-[var(--ink-muted)] group-hover:translate-x-0.5 transition-transform duration-140 ease-out motion-reduce:transform-none" aria-hidden="true" />
          </a>
        </div>
      </section>
    </div>
  );
};
