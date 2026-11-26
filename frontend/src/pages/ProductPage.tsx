import React from 'react';
import { ArrowRight } from 'lucide-react';
import { routeToPath, type AppRoute } from '../lib/router';

interface ProductPageProps {
  onNavigate: (route: AppRoute) => void;
  onStartNewSearch?: () => void;
}

const GUARANTEES = [
  {
    title: 'Work style and country rules stay separate',
    body: 'Remote, hybrid, and in-person tags describe how the team works. Pick your country to check whether you can apply, rather than relying on IP guesses.',
  },
  {
    title: 'Fresh roles stay at the top',
    body: 'Openings from the last 90 days appear first in date order. Anything older drops below an "Older postings" divider so evergreen listings never look brand new.',
  },
  {
    title: 'Honest company details',
    body: 'Logos come from the hiring company, and missing pay or unclear work policies stay blank instead of showing invented numbers.',
  },
  {
    title: 'Private shortlist in your browser',
    body: 'Save roles, track each application stage, browse by keyboard, and export your shortlist to CSV or JSON without creating an account.',
  },
];

export const ProductPage: React.FC<ProductPageProps> = ({ onNavigate, onStartNewSearch }) => {
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
      {/* Intro */}
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl bp-fade-up">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Skip dead links and surprise location rules.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Most job searches burn hours on expired listings, misleading remote tags, and sign-up
            loops. Bottom Pot pulls openings straight from company hiring pages so you see what is
            actually open to you.
          </p>
        </div>
      </section>

      {/* How a Search Runs */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <div>
            <h2 className="text-title font-semibold text-[var(--ink)]">
              How a search runs
            </h2>
            <p className="text-sm text-[var(--ink-muted)] mt-2 max-w-[62ch]">
              Tracked company boards answer first, and a live pass fills in niche roles.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2.5 bp-fade-up bp-delay-1">
              <span className="font-mono text-xs text-[var(--ink-subtle)]">step 01 · fast matches</span>
              <h3 className="text-base font-semibold text-[var(--ink)]">
                Tracked company boards and Nigerian sites answer first
              </h3>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Your search checks tracked company career pages and Nigerian job boards at the same
                time. Results stream into the table as soon as the first matches arrive.
              </p>
            </div>

            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2.5 bp-fade-up bp-delay-2">
              <span className="font-mono text-xs text-[var(--ink-subtle)]">step 02 · wider reach</span>
              <h3 className="text-base font-semibold text-[var(--ink)]">
                Live search fills in rare or specialized roles
              </h3>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                If tracked employers return too few matches, a wider live pass finds additional company
                career pages and links straight to each team&apos;s application form.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Four Verification Guarantees */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <h2 className="text-title font-semibold text-[var(--ink)]">What every listing shows</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {GUARANTEES.map((item) => (
              <div
                key={item.title}
                className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2"
              >
                <h3 className="text-sm font-semibold text-[var(--ink)]">{item.title}</h3>
                <p className="text-sm text-[var(--ink-muted)] leading-relaxed">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Workspace Workflow */}
      <section className="py-14">
        <div className="page-shell flex flex-col gap-8">
          <div className="max-w-3xl">
            <h2 className="text-title font-semibold text-[var(--ink)]">
              Built for reviewing lots of roles quickly
            </h2>
            <p className="text-sm text-[var(--ink-muted)] mt-3 leading-relaxed">
              Click any row to read the full posting in a side panel without losing your place.
              Filter with <kbd className="font-mono text-xs px-1 rounded-sm border border-[var(--border)]">/</kbd>,
              step rows with <kbd className="font-mono text-xs px-1 rounded-sm border border-[var(--border)]">j</kbd> /{' '}
              <kbd className="font-mono text-xs px-1 rounded-sm border border-[var(--border)]">k</kbd>, save roles
              with <kbd className="font-mono text-xs px-1 rounded-sm border border-[var(--border)]">s</kbd>, and keep
              your shortlist right in your browser.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <a
              href={routeToPath('search')}
              onClick={handleStartClick}
              className="group h-10 px-5 rounded-md inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-[opacity,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
              style={{ backgroundColor: 'var(--accent)' }}
            >
              <span>Start searching</span>
              <ArrowRight className="size-4 group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
            </a>
            <a
              href={routeToPath('sources')}
              onClick={handleLinkClick('sources')}
              className="h-10 px-5 rounded-md inline-flex items-center text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
            >
              See all 13 sources
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
