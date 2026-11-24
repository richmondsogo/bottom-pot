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
    body: 'Whether a team works remotely, hybrid, or in person is kept cleanly apart from where you are legally allowed to apply. Select your country to see what actually applies to you—never guessed from your IP.',
  },
  {
    title: 'Fresh roles stay at the top',
    body: 'Openings from the last 90 days appear first in clear chronological order. Anything older moves beneath an "Older postings" divider so long-running evergreen roles never disguise themselves as new.',
  },
  {
    title: 'Real company details, nothing fabricated',
    body: 'Employer logos come straight from the hiring company rather than generic placeholder graphics. If compensation is missing or workplace terms are unclear, the field stays blank.',
  },
  {
    title: 'Your shortlist belongs only to you',
    body: 'Save roles, track your progress from saved to offer, navigate quickly from your keyboard, or export your filtered shortlist cleanly as CSV or JSON without signing up.',
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
            A quieter, more honest way to find work.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Most job sites optimize for clicks over clarity: expired openings left live for traffic,
            regional roles stamped as remote, and real application links hidden behind sign-up prompts.
            Bottom Pot reads straight from where companies actually publish openings.
          </p>
        </div>
      </section>

      {/* How a Search Works */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <div>
            <h2 className="text-title font-semibold text-[var(--ink)]">
              What happens when you press search
            </h2>
            <p className="text-sm text-[var(--ink-muted)] mt-2 max-w-[62ch]">
              Fast direct company matches arrive first, with wider search filling in rare or specialized roles.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2.5 bp-fade-up bp-delay-1">
              <span className="font-mono text-xs text-[var(--ink-subtle)]">step 01 · fast matches</span>
              <h3 className="text-base font-semibold text-[var(--ink)]">
                Tracked company boards &amp; Nigerian job sources answer first
              </h3>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                Your search starts across tracked company career pages and Nigeria’s top job boards in
                parallel. As soon as the first batch arrives, roles appear directly in the table while
                remaining sources finish checking.
              </p>
            </div>

            <div className="border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2.5 bp-fade-up bp-delay-2">
              <span className="font-mono text-xs text-[var(--ink-subtle)]">step 02 · wider reach</span>
              <h3 className="text-base font-semibold text-[var(--ink)]">
                Additional company career pages fill any thin spots
              </h3>
              <p className="text-sm text-[var(--ink-muted)] leading-relaxed">
                When niche searches bring back too few roles from tracked employers, a broader live
                pass brings in newly spotted company hiring pages and links them directly to the team’s
                application destination.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Four Verification Guarantees */}
      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell flex flex-col gap-8">
          <h2 className="text-title font-semibold text-[var(--ink)]">What you can rely on in every row</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {GUARANTEES.map((item) => (
              <div
                key={item.title}
                className="border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-2"
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
              Built for focus when reviewing dozens of roles
            </h2>
            <p className="text-sm text-[var(--ink-muted)] mt-3 leading-relaxed">
              Every listing opens in a calm side reader so you never lose your spot in the table.
              Filter instantly with <kbd className="font-mono text-xs px-1 border border-[var(--border)]">/</kbd>,
              step rows with <kbd className="font-mono text-xs px-1 border border-[var(--border)]">j</kbd> /{' '}
              <kbd className="font-mono text-xs px-1 border border-[var(--border)]">k</kbd>, bookmark favorites
              with <kbd className="font-mono text-xs px-1 border border-[var(--border)]">s</kbd>, and keep
              every application step saved quietly in your browser.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <a
              href={routeToPath('search')}
              onClick={handleStartClick}
              className="group h-10 px-5 inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-[opacity,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
              style={{ backgroundColor: 'var(--accent)', borderRadius: 0 }}
            >
              <span>Start searching</span>
              <ArrowRight className="size-4 group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
            </a>
            <a
              href={routeToPath('sources')}
              onClick={handleLinkClick('sources')}
              className="h-10 px-5 inline-flex items-center text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
              style={{ borderRadius: 0 }}
            >
              View supported sources
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
