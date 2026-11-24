import React from 'react';
import { ArrowRight } from 'lucide-react';
import { routeToPath, type AppRoute } from '../lib/router';

interface AboutPageProps {
  onNavigate: (route: AppRoute) => void;
}

const RULES = [
  {
    name: 'Direct links only',
    detail: 'Results point to the employer career page or primary listing rather than intermediate aggregator redirects.',
  },
  {
    name: 'Blank beats wrong',
    detail: 'Missing salaries, unclear work models, and unknown company domains stay blank instead of showing guesses.',
  },
  {
    name: 'Explicit country eligibility',
    detail: 'Location restrictions are separated from remote labels and checked on the backend for the country you select.',
  },
  {
    name: 'Zero account walls',
    detail: 'Saved roles, stage tracking, filters, and CSV/JSON exports stay in your browser with no sign-up barrier.',
  },
  {
    name: 'Honest platform scope',
    detail: 'Ten ATS engines and three Nigerian boards are maintained actively rather than keeping dead scrapers on the roster.',
  },
];

export const AboutPage: React.FC<AboutPageProps> = ({ onNavigate }) => {
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
            Why Bottom Pot exists.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Finding engineering and product work shouldn&rsquo;t feel like sorting through mirrored
            re-posts, ghost listings from last year, and &ldquo;Worldwide&rdquo; roles that reject your
            country on page two of the application.
          </p>
        </div>
      </section>

      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-5 text-body text-[var(--ink-muted)] leading-relaxed">
          <p>
            Most mainstream job boards index each other. By the time a candidate clicks Apply, the link
            often traces back to a company&rsquo;s public Greenhouse, Lever, Ashby, Workable, or Workday
            board anyway—except with the salary stripped out, the real posting date buried, or regional
            work-authorization rules blurred into a single Remote tag.
          </p>
          <p>
            Bottom Pot reverses that flow. It keeps a steady index of public company boards alongside
            Nigeria&rsquo;s local hiring boards, normalizes timestamps and work arrangements on the backend,
            and surfaces evidence right in the row inspector so you can tell why a role is marked eligible,
            restricted, fresh, or stale before you open twenty tabs.
          </p>
        </div>
      </section>

      <section className="py-14">
        <div className="page-shell max-w-3xl flex flex-col gap-8">
          <h2 className="text-title font-semibold text-[var(--ink)]">Five rules we keep</h2>
          <div className="divide-y divide-[var(--border)] border border-[var(--border)] bg-[var(--surface)]">
            {RULES.map((rule) => (
              <div key={rule.name} className="p-5 flex flex-col sm:flex-row sm:items-baseline gap-2 sm:gap-6">
                <span className="text-sm font-semibold text-[var(--ink)] sm:w-52 shrink-0">
                  {rule.name}
                </span>
                <span className="text-sm text-[var(--ink-muted)] leading-relaxed">{rule.detail}</span>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <a
              href={routeToPath('search')}
              onClick={handleLinkClick('search')}
              className="h-10 px-5 inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-opacity cursor-pointer"
              style={{ backgroundColor: 'var(--accent)', borderRadius: 0 }}
            >
              <span>Start searching</span>
              <ArrowRight className="size-4" aria-hidden="true" />
            </a>
            <a
              href={routeToPath('product')}
              onClick={handleLinkClick('product')}
              className="h-10 px-5 inline-flex items-center text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer"
              style={{ borderRadius: 0 }}
            >
              Explore product architecture
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
