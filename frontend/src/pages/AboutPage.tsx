import React from 'react';
import { ArrowRight } from 'lucide-react';
import { routeToPath, type AppRoute } from '../lib/router';

interface AboutPageProps {
  onNavigate: (route: AppRoute) => void;
  onStartNewSearch?: () => void;
}

const RULES = [
  {
    name: 'Direct apply links',
    detail: 'Every listing sends you straight to the company career page without middleman portals.',
  },
  {
    name: 'Blank beats guessed',
    detail: 'If a company leaves out salary or work policy, the field stays empty instead of showing an estimate.',
  },
  {
    name: 'Clear country rules',
    detail: 'Location limits stay separate from remote badges and update for whichever country you pick.',
  },
  {
    name: 'No account needed',
    detail: 'Your shortlist, application stages, filters, and CSV or JSON exports stay private in your browser.',
  },
  {
    name: 'Reliable sources only',
    detail: 'We maintain 13 dependable career platforms and Nigerian boards instead of padding the count with stale feeds.',
  },
];

export const AboutPage: React.FC<AboutPageProps> = ({ onNavigate, onStartNewSearch }) => {
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
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl bp-fade-up">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Built for people tired of dead job links.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Looking for work already takes enough energy. You should not have to check if a posting
            is still open, guess what &ldquo;remote&rdquo; means, or click through three portals
            before reaching the application form.
          </p>
        </div>
      </section>

      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-5 text-body text-[var(--ink-muted)] leading-relaxed">
          <p>
            Most job sites copy listings from the same company career pages. Along the way, pay
            bands disappear, posting dates get fuzzy, and country-locked jobs stay labeled remote
            until page two of the form.
          </p>
          <p>
            Bottom Pot reads straight from company hiring pages and Nigerian job boards instead.
            Work style stays separate from country rules, posting dates stay honest, and every apply
            button takes you directly to the employer.
          </p>
        </div>
      </section>

      <section className="py-14">
        <div className="page-shell max-w-3xl flex flex-col gap-8">
          <h2 className="text-title font-semibold text-[var(--ink)]">Five rules we stick to</h2>
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
              onClick={handleStartClick}
              className="group h-10 px-5 inline-flex items-center gap-2 text-sm font-medium text-white hover:opacity-95 transition-[opacity,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
              style={{ backgroundColor: 'var(--accent)', borderRadius: 0 }}
            >
              <span>Start searching</span>
              <ArrowRight className="size-4 group-hover:translate-x-0.5 transition-transform duration-140 ease-out" aria-hidden="true" />
            </a>
            <a
              href={routeToPath('product')}
              onClick={handleLinkClick('product')}
              className="h-10 px-5 inline-flex items-center text-sm font-medium border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97] cursor-pointer"
              style={{ borderRadius: 0 }}
            >
              How it works
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
