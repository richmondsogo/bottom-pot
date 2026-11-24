import React from 'react';
import { ArrowRight } from 'lucide-react';
import { routeToPath, type AppRoute } from '../lib/router';

interface AboutPageProps {
  onNavigate: (route: AppRoute) => void;
  onStartNewSearch?: () => void;
}

const RULES = [
  {
    name: 'Direct application links',
    detail: 'Every role takes you straight to the company career page rather than through middleman sign-up walls.',
  },
  {
    name: 'Empty beats invented',
    detail: 'When a hiring team omits salary or keeps attendance vague, that field stays blank instead of showing a guess.',
  },
  {
    name: 'Country honesty',
    detail: 'Location restrictions are kept separate from remote tags and checked clearly for whichever country you choose.',
  },
  {
    name: 'Zero account walls',
    detail: 'Your shortlist, application stages, filters, and CSV/JSON exports live right in your browser without a login barrier.',
  },
  {
    name: 'Quality over volume',
    detail: 'Thirteen reliable hiring engines and Nigerian boards are maintained cleanly rather than padding counts with stale sources.',
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
            Why Bottom Pot exists.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Finding good work takes enough energy on its own. Candidates shouldn’t have to verify whether
            an opening still exists, decode vague remote badges, or click through three redirects before
            seeing the real application form.
          </p>
        </div>
      </section>

      <section className="py-14 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl flex flex-col gap-5 text-body text-[var(--ink-muted)] leading-relaxed">
          <p>
            Most mainstream job sites mirror listings from the same company career pages anyway—often
            dropping compensation details, blurring the real posting date, or labeling a country-locked
            role as open everywhere until page two of the form.
          </p>
          <p>
            Bottom Pot flips that experience around. It looks straight at company hiring pages alongside
            Nigeria’s local job boards, keeps work arrangement separate from country rules, and shows
            exact timestamps and supporting context so you know whether a role is worth applying to
            before opening twenty tabs.
          </p>
        </div>
      </section>

      <section className="py-14">
        <div className="page-shell max-w-3xl flex flex-col gap-8">
          <h2 className="text-title font-semibold text-[var(--ink)]">Five promises we keep</h2>
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
              How a search works
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
